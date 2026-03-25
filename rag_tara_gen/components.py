# =============================================================================
# components.py — Config, ECU resolution, UUID post-processing, component setup
# =============================================================================

import json
import os
import re
import uuid as _uuid
from collections import Counter
from pathlib import Path

from haystack.components.embedders import (
    SentenceTransformersDocumentEmbedder,
    SentenceTransformersTextEmbedder,
)
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack_integrations.components.generators.google_ai import GoogleAIGeminiGenerator


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

BASE_PATH    = Path(__file__).parent / "datasets"
MITRE_MOBILE = BASE_PATH / "mobileattack.json"
MITRE_ICS    = BASE_PATH / "icsattack.json"
ATM_PATH     = BASE_PATH / "atm.json"
CAPEC_PATH   = BASE_PATH / "capec.xml"
CWE_PATH     = BASE_PATH / "cwec.xml"
ECU_PATH     = BASE_PATH / "dataecu.json"
ANNEX_PATH   = BASE_PATH / "annex.json"
CLAUSE_PATH  = BASE_PATH / "clauses"
REPORTS_PATH = BASE_PATH / "reports_db"

EMBED_MODEL      = "BAAI/bge-small-en-v1.5"
MAX_CHARS        = 1500
GEMINI_MODEL     = "gemini-2.5-flash-lite"
RETRIEVER_TOP_K  = 20

# Two-phase retrieval: threat docs go through semantic retriever,
# ECU/arch docs are pinned directly into the prompt.
THREAT_SOURCES = {
    "MITRE_MOBILE", "MITRE_ICS", "ATM", "CAPEC", "CWE", "ISO_21434", "ANNEX_F"
}
PINNED_SOURCES = {"ECU", "REPORTS_DB"}


# ─────────────────────────────────────────────────────────────────────────────
# ECU RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

_SUFFIX_WORDS = {
    "ecu", "system", "module", "interface", "controller", "unit",
    "network", "port", "server", "bus", "head", "vehicle", "automotive"
}

_ALIASES = {
    "obd":               "obd",
    "obd-ii":            "obd",
    "obd2":              "obd",
    "tcu":               "tcu",
    "telematics control":"tcu",
    "bcm":               "bcm",
    "ecm":               "ecm",
    "ivi":               "ivi",
    "eps":               "eps",
    "abs":               "abs",
    "bms":               "bms",
    "adas":              "adas",
}


def _acronym(text: str) -> str:
    skip      = {"the", "and", "for", "of", "a", "an", "or", "in", "on", "to", "/"}
    words     = [w.strip("()/-").lower() for w in text.replace("/", " ").split()]
    sig_words = [w for w in words if w and w not in skip]
    core      = [w for w in sig_words if w not in _SUFFIX_WORDS]
    chosen    = core if core else sig_words
    return "".join(w[0] for w in chosen if w)


def resolve_ecu(query: str, ecu_path=None) -> dict | None:
    """5-pass fuzzy-match query to a dataecu.json entry. Returns entry dict or None."""
    ecu_path = ecu_path or ECU_PATH
    with open(ecu_path, "r", encoding="utf-8") as f:
        ecu_db = json.load(f)
    q = query.lower().strip()

    # Pass 0: alias table
    for phrase, key in _ALIASES.items():
        if phrase in q and key in ecu_db:
            return ecu_db[key]
    # Pass 1: exact key or standalone word
    for key, entry in ecu_db.items():
        if key == q or f" {key} " in f" {q} ":
            return entry
    # Pass 2: full name substring
    for key, entry in ecu_db.items():
        if entry["name"].lower() in q:
            return entry
    # Pass 3a: exact acronym
    qa = _acronym(q)
    for key, entry in ecu_db.items():
        if qa and qa == key:
            return entry
    # Pass 3b: acronym prefix
    if len(qa) >= 2:
        for key, entry in ecu_db.items():
            if key.startswith(qa) and len(key) - len(qa) <= 1:
                return entry
    # Pass 4: word overlap
    for key, entry in ecu_db.items():
        name_words = [w.strip("()/-").lower() for w in entry["name"].replace("/", " ").split()]
        core       = [w for w in name_words if len(w) > 2 and w not in _SUFFIX_WORDS]
        if sum(1 for w in core if w in q) >= 2:
            return entry
    # Pass 5: key word in query
    for key, entry in ecu_db.items():
        if any(w in q for w in key.replace("_", " ").split() if len(w) > 3):
            return entry
    return None


def list_ecus(ecu_path=None) -> None:
    """Print all ECU keys and names from dataecu.json."""
    ecu_path = ecu_path or ECU_PATH
    with open(ecu_path, "r", encoding="utf-8") as f:
        ecu_db = json.load(f)
    print(f"\n{'Key':<20} {'Name'}")
    print("-" * 60)
    for key, entry in ecu_db.items():
        print(f"  {key:<18} {entry.get('name', '')}")
    print(f"\nTotal: {len(ecu_db)} ECU entries")


def build_enriched_query(user_query: str, ecu_entry: dict | None) -> str:
    if ecu_entry:
        return (
            f"{ecu_entry['name']}\n\n"
            f"AUTHORITATIVE ASSET LIST (from system dataecu specification) — "
            f"generate ONLY these assets, no others:\n"
            f"{ecu_entry['hint']}\n\n"
            f"All threat analysis, damage scenarios, and edges must reference "
            f"ONLY the assets listed above. Do NOT add any other components."
        )
    return user_query


# ─────────────────────────────────────────────────────────────────────────────
# POST-PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def stamp_uuids(obj: dict) -> dict:
    """Replace empty/placeholder id/_id/model_id fields with fresh uuid4 values."""
    ID_KEYS = {"id", "_id", "model_id"}

    def _bad(val):
        if not val:
            return True
        if isinstance(val, str) and (
            "PLACEHOLDER" in val or val.strip() == "" or val.startswith("<")
        ):
            return True
        return False

    def _walk(o):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if k in ID_KEYS and _bad(v):
                    o[k] = str(_uuid.uuid4())
                else:
                    _walk(v)
        elif isinstance(o, list):
            for item in o:
                _walk(item)

    _walk(obj)
    return obj


def crosslink_node_ids(obj: dict) -> dict:
    """Propagate stamped nodeIds into Derivations and cyberLosses by label-matching."""
    nodes = obj.get("assets", {}).get("template", {}).get("nodes", [])
    label_to_id = {
        n.get("data", {}).get("label", "").lower(): n.get("id")
        for n in nodes if n.get("id")
    }
    for d in obj.get("damage_scenarios", {}).get("Derivations", []):
        nid = d.get("nodeId", "")
        if not nid or str(nid).startswith("<") or "PLACEHOLDER" in str(nid):
            d["nodeId"] = label_to_id.get(d.get("asset", "").lower()) or str(_uuid.uuid4())
    for det in obj.get("damage_scenarios", {}).get("Details", []):
        for cl in det.get("cyberLosses", []):
            nid = cl.get("nodeId", "")
            if not nid or str(nid).startswith("<") or "PLACEHOLDER" in str(nid):
                cl["nodeId"] = label_to_id.get(cl.get("node", "").lower()) or str(_uuid.uuid4())
            if not cl.get("id") or str(cl.get("id", "")).startswith("<"):
                cl["id"] = str(_uuid.uuid4())
    return obj


def parse_and_fix(raw_text: str) -> dict | None:
    """Strip markdown fences, parse JSON, stamp UUIDs, crosslink nodeIds."""
    cleaned = re.sub(r"^```[a-z]*\n?", "", raw_text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip())
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON parse error: {e}")
        print(f"Raw output (first 500 chars):\n{cleaned[:500]}")
        return None
    return crosslink_node_ids(stamp_uuids(obj))


def print_summary(tara_json: dict) -> None:
    node_count  = len(tara_json.get("assets", {}).get("template", {}).get("nodes", []))
    edge_count  = len(tara_json.get("assets", {}).get("template", {}).get("edges", []))
    deriv_count = len(tara_json.get("damage_scenarios", {}).get("Derivations", []))
    ds_count    = len(tara_json.get("damage_scenarios", {}).get("Details", []))
    print(f"   Nodes          : {node_count}")
    print(f"   Edges          : {edge_count}")
    print(f"   Derivations    : {deriv_count}")
    print(f"   Damage details : {ds_count}")
    print("   IDs            : all stamped as uuid4")


# ─────────────────────────────────────────────────────────────────────────────
# TWO-PHASE CONTEXT ASSEMBLY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _find_reports_db_model_name(all_docs: list, ecu_entry: dict | None) -> str | None:
    """
    Scan REPORTS_DB docs to find which model name best matches the resolved
    ECU entry. E.g. 'BMS (Battery Management System)' → 'BatteryManagement'.
    Uses significant word overlap between the ECU name and the camelCase model.
    """
    if not ecu_entry:
        return None
    ecu_name = ecu_entry.get("name", "").lower()
    # Collect unique model names present in the REPORTS_DB
    model_names = set(
        d.meta.get("model", "")
        for d in all_docs
        if d.meta.get("source") == "REPORTS_DB" and d.meta.get("model")
    )
    for model in model_names:
        # Split camelCase (BatteryManagement → ['battery', 'management'])
        words = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', model).lower().split()
        significant = [w for w in words if len(w) > 3]
        if any(w in ecu_name for w in significant):
            return model
    return None


def build_pinned_docs(all_docs: list, ecu_entry: dict | None) -> tuple[list, str | None]:
    """
    Extract docs that must always appear in the prompt, regardless of retrieval.

    Pinning order (most important first):
      1. full_file chunk  — entire semantic architecture of the matched system
      2. ECU entry        — dataecu.json hint with authoritative asset list
      3. Other REPORTS_DB chunks — individual nodes, edges, derivations, details

    Returns:
        (pinned_docs, matched_model_name)
        matched_model_name is None when no REPORTS_DB reference exists for this system.
    """
    model_name = _find_reports_db_model_name(all_docs, ecu_entry)

    full_file_docs    = []
    ecu_doc           = []
    other_report_docs = []

    if model_name:
        for doc in all_docs:
            if (doc.meta.get("source") == "REPORTS_DB"
                    and doc.meta.get("model", "").lower() == model_name.lower()):
                if doc.meta.get("type") == "full_file":
                    full_file_docs.append(doc)
                else:
                    other_report_docs.append(doc)

    if ecu_entry:
        ecu_name = ecu_entry.get("name", "").lower()
        for doc in all_docs:
            if doc.meta.get("source") == "ECU" and ecu_name in doc.content.lower():
                ecu_doc.append(doc)
                break

    # full architecture first so LLM sees the complete picture before anything else
    pinned = full_file_docs + ecu_doc + other_report_docs

    if full_file_docs:
        print(f"  ✅ Full-file architecture chunk pinned for model: {model_name}")
    elif not pinned and ecu_entry:
        print("  ⚠️  No REPORTS_DB match — only ECU hint will be pinned")

    return pinned, model_name


# ─────────────────────────────────────────────────────────────────────────────
# HAYSTACK COMPONENT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_store(docs_subset: list, text_embedder=None):
    """
    Embed a list of documents and load into InMemoryDocumentStore.
    Optionally accepts an already-warmed text_embedder to reuse.
    Returns (store, text_embedder).
    """
    store        = InMemoryDocumentStore()
    doc_embedder = SentenceTransformersDocumentEmbedder(model=EMBED_MODEL)
    if text_embedder is None:
        text_embedder = SentenceTransformersTextEmbedder(model=EMBED_MODEL)
        text_embedder.warm_up()
    doc_embedder.warm_up()

    print(f"🔄 Embedding {len(docs_subset)} documents...")
    embedded = doc_embedder.run(documents=docs_subset)["documents"]
    store.write_documents(embedded)
    print(f"✅ {store.count_documents()} documents stored.")
    return store, text_embedder


def build_threat_store(all_docs: list, text_embedder=None):
    """
    Build a document store that contains ONLY threat-framework documents
    (MITRE, ATM, CAPEC, CWE, ISO 21434, Annex F).
    These are semantically distant from ECU architecture queries, so they
    need dedicated retrieval slots — isolated from ECU/REPORTS_DB docs.
    Returns (store, text_embedder).
    """
    threat_docs = [
        d for d in all_docs
        if d.meta.get("source") in THREAT_SOURCES
    ]
    print(f"\n📚 Threat-framework docs for retriever: {len(threat_docs)}")
    from collections import Counter
    dist = Counter(d.meta.get("source") for d in threat_docs)
    for src, cnt in sorted(dist.items()):
        print(f"   {src:<20}: {cnt}")
    return build_store(threat_docs, text_embedder)


def build_retriever(store):
    return InMemoryEmbeddingRetriever(document_store=store, top_k=RETRIEVER_TOP_K)


def build_generator():
    if "GOOGLE_API_KEY" not in os.environ:
        raise EnvironmentError(
            "❌ GOOGLE_API_KEY not set.\n"
            "   Windows : set GOOGLE_API_KEY=your-key-here\n"
            "   Linux   : export GOOGLE_API_KEY=your-key-here"
        )
    return GoogleAIGeminiGenerator(model=GEMINI_MODEL)
