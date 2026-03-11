"""
patch_tara_all.py  —  Apply all 6 patches to Tara_expo_v2.0.ipynb
Run from the rag_tara_gen directory (or anywhere; uses absolute NB_PATH).

Patches:
  1. Add `import uuid` to the Library Imports cell
  2. Rewrite ingest_reports_db (fix key casing, remove isAsset filter)
  3. Rewrite the full prompt template (schema fixes + REPORTS_DB isolation + dataecu hint rule)
  4. Rewrite JSON output cell (UUID stamping + crosslink_node_ids)
  5. (included in Patch 3) System-isolation wording & per-chunk REPORTS_DB tagging
  6. Add resolve_ecu() helper cell + enriched query injection in pipeline run cell
"""

import json
from pathlib import Path

NB_PATH = Path(r"c:\Users\Roysten\Desktop\FUCYTECH 8th sem\rag_develop\rag_fucy_test\rag_tara_gen\Tara_expo_v2.0.ipynb")

with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

cells = nb["cells"]

# ── helpers ──────────────────────────────────────────────────────────────────

def src(c):
    return "".join(c.get("source", []))

def find_cell(marker):
    for i, c in enumerate(cells):
        if marker in src(c):
            return i, c
    return None, None

def code_cell(source_str):
    """Create a new code cell dict."""
    lines = source_str.splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1].rstrip("\n")
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": lines,
    }

def md_cell(text):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [text],
    }

def set_source(cell, text):
    lines = text.splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1].rstrip("\n")
    cell["source"] = lines

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1 — add `import uuid` to Library Imports cell
# ─────────────────────────────────────────────────────────────────────────────
i, cell = find_cell("import os")
if cell and "import uuid" not in src(cell):
    new_lines = []
    for line in cell["source"]:
        new_lines.append(line)
        if line.strip() == "import re":
            sep = "\n" if line.endswith("\n") else ""
            new_lines.append("import uuid" + sep)
    cell["source"] = new_lines
    print(f"PATCH 1 OK : added 'import uuid' in cell {i}")
else:
    print("PATCH 1 skip: already present")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2 — rewrite ingest_reports_db
# ─────────────────────────────────────────────────────────────────────────────
i, cell = find_cell("def ingest_reports_db")
if cell:
    NEW_INGEST = '''\
def ingest_ecu(ecu_path):
    """Load ECU/system data JSON — one Document per ECU entry."""
    if not Path(ecu_path).exists():
        print(f"  ECU file not found: {ecu_path} — skipping.")
        return []
    with open(ecu_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    docs = []
    items = data.items() if isinstance(data, dict) else enumerate(data)
    for key, val in items:
        docs.append(Document(
            content=json.dumps(val, indent=2),
            meta={"source": "ECU", "title": str(key)}
        ))
    return docs


def _clean_node_for_text(node):
    """Extract readable label+description from a node dict."""
    data  = node.get("data", {})
    label = data.get("label", node.get("id", ""))
    desc  = data.get("description", "")
    props = node.get("properties", [])
    ntype = node.get("type", "component")
    return label, desc, props, ntype


def ingest_reports_db(reports_path):
    """
    Ingest TARA reference reports from reports_db/.

    CHUNKING STRATEGY:
      * Each named node (all components, not just isAsset=True) -> 1 Document
      * Each damage derivation entry                            -> 1 Document
      * Each damage detail entry                                -> 1 Document

    All named nodes are ingested so the retriever surfaces
    sub-components and interfaces as reference patterns.
    """
    docs = []
    path = Path(reports_path)
    if not path.exists():
        print(f"  Reports DB folder not found: {reports_path}")
        return docs

    for json_file in sorted(path.glob("*.json")):
        fname = json_file.name
        with open(json_file, "r", encoding="utf-8") as f:
            report = json.load(f)

        # Format A: direct {assets, damage_scenarios}  (infotainment_1.json)
        if "assets" in report and "damage_scenarios" in report:
            assets_block    = report["assets"]
            damage_block    = report["damage_scenarios"]
            model_name      = assets_block.get("model_id", fname.replace(".json", ""))
            nodes_list      = assets_block.get("template", {}).get("nodes", [])
            derivation_list = damage_block.get("Derivations") or damage_block.get("derivation") or []
            details_list    = damage_block.get("Details")      or damage_block.get("details")     or []

        # Format B: wrapped (bms_1.json) -- top-level key is "Damage_scenarios"
        elif "Assets" in report:
            a_block    = report["Assets"][0] if report.get("Assets") else {}
            model_name = report["Models"][0]["name"] if report.get("Models") else fname
            nodes_list = a_block.get("template", {}).get("nodes", [])
            ds_list    = (report.get("Damage_scenarios")
                          or report.get("DamageScenarios")
                          or [])
            d_block         = ds_list[0] if ds_list else {}
            derivation_list = d_block.get("Derivations") or d_block.get("derivation") or []
            details_list    = d_block.get("Details")      or d_block.get("details")     or []
        else:
            print(f"  Unrecognised format in {fname} — skipping.")
            continue

        # Chunk 1: All named nodes (isAsset filter removed)
        node_count = 0
        for node in nodes_list:
            label, desc, props, ntype = _clean_node_for_text(node)
            if not label or label.strip() == "":
                continue
            is_asset = node.get("isAsset", False)
            content = (
                f"Reference Component [{model_name}]: {label}\\n"
                f"Type: {ntype}  IsAsset: {is_asset}\\n"
                f"Description: {desc}\\n"
                f"Security Properties: {\\', \\'.join(props) if props else \\'N/A\\'}"
            )
            docs.append(Document(
                content=content,
                meta={"source": "REPORTS_DB", "file": fname,
                      "model": model_name, "type": "asset",
                      "is_asset": is_asset, "node_id": node.get("id", "")}
            ))
            node_count += 1

        # Chunk 2: Damage derivation entries
        deriv_count = 0
        for d in derivation_list:
            name  = d.get("name", "")
            asset = d.get("asset", "")
            loss  = d.get("loss", "")
            scene = d.get("damage_scene", "")
            if not name:
                continue
            content = (
                f"Reference Damage Derivation [{model_name}]:\\n"
                f"Threat/Weakness: {name}\\n"
                f"Affected Asset: {asset}\\n"
                f"Cyber Loss: {loss}\\n"
                f"Damage Scene: {scene}"
            )
            docs.append(Document(
                content=content,
                meta={"source": "REPORTS_DB", "file": fname,
                      "model": model_name, "type": "damage_derivation"}
            ))
            deriv_count += 1

        # Chunk 3: Damage detail entries
        detail_count = 0
        for det in details_list:
            dname   = det.get("Name", "")
            ddesc   = _truncate(det.get("Description", ""), 800)
            impacts = det.get("impacts", {})
            losses  = [(cl.get("name", ""), cl.get("node", ""))
                       for cl in det.get("cyberLosses", [])]
            if not dname:
                continue
            impact_str = "  ".join(f"{k}: {v}" for k, v in impacts.items() if v)
            loss_str   = ", ".join(f"{n} ({nd})" for n, nd in losses if n)
            content = (
                f"Reference Damage Scenario [{model_name}]: {dname}\\n"
                f"Description: {ddesc}\\n"
                f"Cyber Losses: {loss_str}\\n"
                f"Impact Ratings: {impact_str}"
            )
            docs.append(Document(
                content=content,
                meta={"source": "REPORTS_DB", "file": fname,
                      "model": model_name, "type": "damage_detail"}
            ))
            detail_count += 1

        print(f"  {fname}: {node_count} components | {deriv_count} derivations | {detail_count} details")

    print(f"\\nREPORTS_DB total chunks: {len(docs)}")
    return docs


print("ECU & Reports DB ingestion functions defined.")
'''
    set_source(cell, NEW_INGEST)
    print(f"PATCH 2 OK : rewrote ingest_reports_db in cell {i}")
else:
    print("PATCH 2 FAIL: ingest_reports_db cell not found")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3 + 5 — rewrite prompt template (schema + isolation + dataecu hint rule)
# ─────────────────────────────────────────────────────────────────────────────
i, cell = find_cell("STRICT OUTPUT FORMAT")
if cell:
    NEW_PROMPT = r'''template = """
You are an automotive cybersecurity analyst performing Threat Analysis and Risk Assessment (TARA)
according to ISO/SAE 21434 Clause 15.

Your task is to generate a system architecture model and cybersecurity damage scenarios
for the requested automotive ECU or system.

STRICT KNOWLEDGE RULES

- Use ONLY information relevant to the TARGET SYSTEM specified in the SYSTEM REQUEST below.
- Do NOT invent assets or components that are not part of the targeted system.
- If an AUTHORITATIVE ASSET LIST is provided in the request, generate EXACTLY those assets — no additions, no omissions.
  All damage scenarios, derivations, and edges must reference ONLY those listed assets.
- REPORTS_DB entries are structural EXAMPLES ONLY. Do NOT copy their node labels, scenario names, or IDs.
  They show the expected JSON shape, security property patterns, and derivation format.
  All generated content must be derived from the TARGET SYSTEM, not from any reference system (e.g. BMS).
- Do NOT reproduce BMS, Infotainment, or any other system's component names unless the TARGET SYSTEM matches exactly.
- Use realistic automotive architecture relevant to the TARGET SYSTEM only.
- Prefer knowledge retrieved from cybersecurity context (ISO 21434, CWE, CAPEC, MITRE, ATM).
- If information is missing, infer only common industry-standard components for the specified system.

Threat reasoning must follow:
CWE (root weakness) → CAPEC (attack pattern) → MITRE ATT&CK technique → ATM relevance → Damage Scenario

-------------------------------------------------

SYSTEM REQUEST:
{{question}}

CYBERSECURITY KNOWLEDGE CONTEXT:
{% for doc in documents %}
{% if doc.meta.source == "REPORTS_DB" %}
[REFERENCE-PATTERN-ONLY | structural example — do NOT copy node names or scenario content]
{% else %}
[{{ doc.meta.source }}{% if doc.meta.section_id is defined %} § {{ doc.meta.section_id }}{% endif %}{% if doc.meta.type is defined %} | {{ doc.meta.type }}{% endif %}]
{% endif %}
{{ doc.content }}
---
{% endfor %}

-------------------------------------------------

TASK

1. Identify the architecture of the requested system (use the AUTHORITATIVE ASSET LIST if provided).
2. Generate assets that belong strictly to the TARGET SYSTEM — no others.
3. Create architecture relationships (edges) between those assets.
4. Generate realistic cybersecurity damage scenarios referencing only the generated assets.
5. For each damage scenario derive an Impact Rating using SFOP categories.

-------------------------------------------------

IMPACT RATING SCALE

For every damage scenario derive cyber losses using SFOP categories:
Safety | Financial | Operational | Privacy

For each cyber loss assign: Negligible | Minor | Moderate | Major | Severe
Then derive an overall impact rating based on the highest impact.

-------------------------------------------------

STRICT OUTPUT FORMAT

Return ONLY valid JSON. Do not include explanations, markdown fences, or prose.
Start the response with '{'.

Return JSON exactly in this structure:

{
 "assets":{
   "_id":"",
   "user_id":"",
   "model_id":"",

   "template":{
      "nodes":[
         {
           "id":"",
           "type":"default",
           "parentId":"",
           "isAsset":true,
           "data":{
             "label":"",
             "description":"",
             "style":{"backgroundColor":"#dadada","borderColor":"gray","borderStyle":"solid","borderWidth":"2px","color":"black","fontFamily":"Inter","fontSize":"12px","fontWeight":500,"height":50,"width":150}
           },
           "properties":["Integrity","Confidentiality","Availability"],
           "style":{"width":150,"height":50},
           "position":{"x":0,"y":0},
           "positionAbsolute":{"x":0,"y":0},
           "width":150,
           "height":50
         }
      ],

      "edges":[
         {
           "id":"",
           "source":"<source node id>",
           "target":"<target node id>",
           "sourceHandle":"b",
           "targetHandle":"left",
           "type":"step",
           "animated":true,
           "markerEnd":{"color":"#64B5F6","height":18,"type":"arrowclosed","width":18},
           "markerStart":{"color":"#64B5F6","height":18,"orient":"auto-start-reverse","type":"arrowclosed","width":18},
           "style":{"end":true,"start":true,"stroke":"#808080","strokeDasharray":"0","strokeWidth":2},
           "properties":["Integrity"],
           "data":{"label":"","offset":0,"t":0.5}
         }
      ]
   }
 },

 "damage_scenarios":{
   "_id":"",
   "model_id":"",
   "type":"damage",

   "Derivations":[
      {
        "id":"","nodeId":"","task":"Threat Analysis",
        "name":"","loss":"","asset":"",
        "damage_scene":"","isChecked":false
      }
   ],

   "Details":[
      {
        "Name":"",
        "Description":"",
        "cyberLosses":[{"id":"","name":"","node":"","nodeId":"","isSelected":true,"is_risk_added":false}],
        "impacts":{"Financial Impact":"","Safety Impact":"","Operational Impact":"","Privacy Impact":""},
        "key":1,
        "_id":""
      }
   ]
 }
}

-------------------------------------------------

CONSTRAINTS

- Generate ONLY the assets listed in the AUTHORITATIVE ASSET LIST (if provided), or assets strictly belonging to the TARGET SYSTEM.
- Do NOT add components from other ECU systems.
- Damage scenarios must reference valid nodeId values from the nodes above.
- Impact rating must be derived from the damage scenario context.
- Use threat reasoning from CWE, MITRE, CAPEC, ATM — not from REPORTS_DB examples.

Return JSON only. Start the response with '{'.
"""

prompt_builder = PromptBuilder(
    template=template,
    required_variables=["documents", "question"]
)

print("✅ PromptBuilder initialized.")
'''
    set_source(cell, NEW_PROMPT)
    print(f"PATCH 3+5 OK : rewrote prompt template in cell {i}")
else:
    print("PATCH 3+5 FAIL: prompt template cell not found")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 4 — rewrite JSON output cell (UUID stamping + crosslink)
# ─────────────────────────────────────────────────────────────────────────────
i, cell = find_cell("raw_output = result")
if cell:
    NEW_OUTPUT = '''\
raw_output = result["llm"]["replies"][0]

# Strip any accidental markdown fences
cleaned = re.sub(r"^```[a-z]*\\n?", "", raw_output.strip(), flags=re.MULTILINE)
cleaned = re.sub(r"```$", "", cleaned.strip())

try:
    tara_json = json.loads(cleaned)
    print("✅ Valid JSON output parsed.")
except json.JSONDecodeError as e:
    print(f"⚠️  JSON parse error: {e}")
    print("Raw output (first 500 chars):")
    print(cleaned[:500])
    tara_json = None

# ── UUID STAMPING ────────────────────────────────────────────────────────────
# Replace empty / placeholder / hallucinated IDs with proper uuid4 values.
# ─────────────────────────────────────────────────────────────────────────────
def stamp_uuids(obj):
    """Walk the JSON tree and replace any id/_id/model_id that is empty,
    None, or a placeholder string with a fresh uuid4."""
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
                    o[k] = str(uuid.uuid4())
                else:
                    _walk(v)
        elif isinstance(o, list):
            for item in o:
                _walk(item)

    _walk(obj)
    return obj


def crosslink_node_ids(obj):
    """After node UUIDs are stamped, propagate real nodeId values into
    Derivations[].nodeId and Details[].cyberLosses[].nodeId by label-matching."""
    nodes = obj.get("assets", {}).get("template", {}).get("nodes", [])
    label_to_id = {
        n.get("data", {}).get("label", "").lower(): n.get("id")
        for n in nodes if n.get("id")
    }

    for d in obj.get("damage_scenarios", {}).get("Derivations", []):
        nid = d.get("nodeId", "")
        if not nid or str(nid).startswith("<") or "PLACEHOLDER" in str(nid):
            matched = label_to_id.get(d.get("asset", "").lower())
            d["nodeId"] = matched if matched else str(uuid.uuid4())

    for det in obj.get("damage_scenarios", {}).get("Details", []):
        for cl in det.get("cyberLosses", []):
            nid = cl.get("nodeId", "")
            if not nid or str(nid).startswith("<") or "PLACEHOLDER" in str(nid):
                matched = label_to_id.get(cl.get("node", "").lower())
                cl["nodeId"] = matched if matched else str(uuid.uuid4())
            if not cl.get("id") or str(cl.get("id", "")).startswith("<"):
                cl["id"] = str(uuid.uuid4())
    return obj


if tara_json:
    tara_json = stamp_uuids(tara_json)
    tara_json = crosslink_node_ids(tara_json)
    node_count  = len(tara_json.get("assets", {}).get("template", {}).get("nodes", []))
    edge_count  = len(tara_json.get("assets", {}).get("template", {}).get("edges", []))
    deriv_count = len(tara_json.get("damage_scenarios", {}).get("Derivations", []))
    ds_count    = len(tara_json.get("damage_scenarios", {}).get("Details", []))
    print(f"   Nodes         : {node_count}")
    print(f"   Edges         : {edge_count}")
    print(f"   Derivations   : {deriv_count}")
    print(f"   Damage details: {ds_count}")
    print("   IDs           : all IDs stamped as proper uuid4 values")
'''
    set_source(cell, NEW_OUTPUT)
    print(f"PATCH 4 OK : rewrote JSON output cell in cell {i}")
else:
    print("PATCH 4 FAIL: JSON output cell not found")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 6 — add resolve_ecu() helper cell + enriched pipeline run
# ─────────────────────────────────────────────────────────────────────────────

# Patch 6a: add resolve_ecu helper cell right after the user_query cell
i_query, cell_query = find_cell('user_query = "Battery Management System ECU"')
if i_query is not None:
    RESOLVE_ECU_MD = "### 13b. ECU Resolution from dataecu.json"
    RESOLVE_ECU_CODE = '''\
# ── Resolve the queried system against dataecu.json ──────────────────────────
# dataecu.json has 50 ECU/system entries, each with a curated `hint` field
# listing the EXACT expected assets for that system.  We match user_query to
# the closest entry and inject its hint as an authoritative constraint into the
# LLM prompt — so the LLM generates ONLY those assets and no others.
# ─────────────────────────────────────────────────────────────────────────────

def resolve_ecu(query, ecu_path=ECU_PATH):
    """
    Fuzzy-match query against dataecu.json keys and names.
    Returns the matched entry dict {name, type, hint} or None.
    """
    with open(ecu_path, "r", encoding="utf-8") as f:
        ecu_db = json.load(f)

    q = query.lower()

    # Exact key or full name match
    for key, entry in ecu_db.items():
        if key in q or entry["name"].lower() in q:
            return entry

    # Partial word match (words > 3 chars to avoid noise)
    for key, entry in ecu_db.items():
        words = key.replace("_", " ").split()
        if any(w in q for w in words if len(w) > 3):
            return entry

    return None

ecu_entry = resolve_ecu(user_query)
if ecu_entry:
    print(f"✅ Matched ECU  : {ecu_entry['name']}")
    print(f"   Type         : {ecu_entry['type']}")
    print(f"   Asset hint   : {ecu_entry['hint']}")
else:
    print("⚠️  No dataecu.json match found — will use open-ended generation.")
'''

    # Insert MD then code cell right after the user_query cell
    new_md   = md_cell(RESOLVE_ECU_MD)
    new_code = code_cell(RESOLVE_ECU_CODE)
    cells.insert(i_query + 1, new_md)
    cells.insert(i_query + 2, new_code)
    print(f"PATCH 6a OK: inserted resolve_ecu cells after cell {i_query}")
else:
    print("PATCH 6a FAIL: user_query cell not found")

# Patch 6b: rewrite tara_pipeline.run() cell to use enriched_query
# Re-find after insertion (index shifted)
i_run, cell_run = find_cell("result = tara_pipeline.run")
if i_run is not None:
    NEW_RUN = '''\
# Build enriched query for the LLM  (embedding still uses plain user_query)
if ecu_entry:
    enriched_query = (
        f"{ecu_entry['name']}\\n\\n"
        f"AUTHORITATIVE ASSET LIST (from system dataecu specification) — "
        f"generate ONLY these assets, no others:\\n"
        f"{ecu_entry['hint']}\\n\\n"
        f"All threat analysis, damage scenarios, and edges must reference "
        f"ONLY the assets listed above. Do NOT add any other components."
    )
else:
    enriched_query = user_query

print(f"🎯 Generating TARA for  : {user_query}")
print(f"   Enriched prompt query: {enriched_query[:120]}...")
print(f"   Retriever top_k      : 20")
print(f"   Embedding model      : {EMBED_MODEL}")

result = tara_pipeline.run(
    {
        "text_embedder": {"text": user_query},        # plain query for retrieval
        "prompt_builder": {"question": enriched_query}  # enriched for LLM
    },
    include_outputs_from=["retriever"]
)

print("✅ Pipeline run complete.")
'''
    set_source(cell_run, NEW_RUN)
    print(f"PATCH 6b OK: rewrote tara_pipeline.run cell {i_run}")
else:
    print("PATCH 6b FAIL: tara_pipeline.run cell not found")

# ─────────────────────────────────────────────────────────────────────────────
# Save notebook
# ─────────────────────────────────────────────────────────────────────────────
with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"\n✅ Notebook saved: {NB_PATH}")
print(f"   Total cells: {len(nb['cells'])}")
