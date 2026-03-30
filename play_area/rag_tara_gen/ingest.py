# =============================================================================
# ingest.py — All dataset ingestion functions
# =============================================================================

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from haystack import Document
from lxml import etree

from components import (
    MITRE_MOBILE, MITRE_ICS, ATM_PATH, CAPEC_PATH, CWE_PATH,
    ECU_PATH, ANNEX_PATH, CLAUSE_PATH, REPORTS_PATH, MAX_CHARS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _truncate(text: str, max_chars: int = MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_period = cut.rfind(". ")
    return cut[:last_period + 1] if last_period > 0 else cut + "..."


def _flatten_list(lst) -> list:
    result = []
    for item in lst:
        if isinstance(item, list):
            result.extend(_flatten_list(item))
        elif isinstance(item, str):
            result.append(item)
    return result


def _section_to_text(section: dict, clause_id: str = "") -> str:
    parts = []
    sid   = section.get("section_id", "")
    title = section.get("section_title", "")
    parts.append(f"ISO 21434 Clause {clause_id} — Section {sid}: {title}")
    for item in _flatten_list(section.get("content", [])):
        parts.append(f"  - {item}")
    for req in section.get("requirements", []):
        rid   = req.get("id", "")
        rdesc = " ".join(_flatten_list(req.get("description", [])))
        parts.append(f"  [{rid}] {rdesc}")
    for rec in section.get("recommendations", []):
        rid   = rec.get("id", "")
        rdesc = " ".join(_flatten_list(rec.get("description", [])))
        parts.append(f"  [{rid}] (Recommendation) {rdesc}")
    for sub in section.get("subsections", []):
        parts.append(_section_to_text(sub, clause_id))
    return "\n".join(parts)


def _clean_node_for_text(node: dict):
    data  = node.get("data", {})
    label = data.get("label", node.get("id", ""))
    desc  = data.get("description", "")
    props = node.get("properties") or []
    ntype = node.get("type", "component")
    return label, desc, props, ntype


# ─────────────────────────────────────────────────────────────────────────────
# Threat frameworks
# ─────────────────────────────────────────────────────────────────────────────

def ingest_mitre(path, source: str) -> list[Document]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    docs = []
    for obj in data.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        name = obj.get("name", "")
        desc = _truncate(obj.get("description", ""))
        if not desc:
            continue
        docs.append(Document(
            content=f"MITRE Technique: {name}\nDescription: {desc}",
            meta={"source": source, "stix_id": obj.get("id")}
        ))
    return docs


def ingest_atm(path) -> list[Document]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    docs = []
    for obj in data.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        name = obj.get("name", "")
        desc = _truncate(re.sub(r"<[^>]+>", " ", obj.get("description", "")).strip())
        if not desc:
            continue
        docs.append(Document(
            content=f"ATM Technique: {name}\nDescription: {desc}",
            meta={"source": "ATM", "stix_id": obj.get("id")}
        ))
    return docs


def ingest_capec(xml_path) -> list[Document]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns   = {"capec": "http://capec.mitre.org/capec-3"}
    docs = []
    for ap in root.findall(".//capec:Attack_Pattern", ns):
        cid  = ap.get("ID")
        name = ap.get("Name", "")          # Name is an XML attribute, not a child element
        desc_el = ap.find("capec:Description", ns)
        if desc_el is not None:
            desc = _truncate(" ".join(desc_el.itertext()).strip())
        else:
            desc = ""
        if not desc:
            continue
        docs.append(Document(
            content=f"CAPEC-{cid}: {name}\nDescription: {desc}",
            meta={"source": "CAPEC", "capec_id": cid}
        ))
    return docs


def ingest_cwe(xml_path) -> list[Document]:
    parser = etree.XMLParser(recover=True, huge_tree=True)
    tree   = etree.parse(xml_path, parser)
    root   = tree.getroot()
    ns     = {"cwe": "http://cwe.mitre.org/cwe-7"}
    docs   = []
    for w in root.findall(".//cwe:Weakness", namespaces=ns):
        cwe_id  = w.get("ID")
        name    = w.get("Name", "")
        desc_el = w.find("cwe:Description", namespaces=ns)
        desc    = _truncate((desc_el.text or "").strip()) if desc_el is not None else ""
        if not desc:
            continue
        docs.append(Document(
            content=f"CWE-{cwe_id}: {name}\nDescription: {desc}",
            meta={"source": "CWE", "cwe_id": f"CWE-{cwe_id}"}
        ))
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# ISO 21434 & Annex F
# ─────────────────────────────────────────────────────────────────────────────

def ingest_iso_clauses(clause_dir) -> list[Document]:
    docs  = []
    for file in sorted(Path(clause_dir).glob("clause-*.json")):
        with open(file, "r", encoding="utf-8") as f:
            clause = json.load(f)
        clause_id    = clause.get("clause_id", file.stem.split("-")[1])
        clause_title = clause.get("clause_title", f"Clause {clause_id}")
        for section in clause.get("sections", []):
            text = _section_to_text(section, clause_id)
            if len(text.strip()) < 20:
                continue
            docs.append(Document(
                content=text,
                meta={
                    "source":       "ISO_21434",
                    "clause":       clause_id,
                    "clause_title": clause_title,
                    "section_id":   section.get("section_id", ""),
                    "title":        section.get("section_title", ""),
                }
            ))
    return docs


def ingest_annex(annex_path) -> list[Document]:
    if not Path(annex_path).exists():
        print("⚠️  Annex file not found — skipping.")
        return []
    with open(annex_path, "r", encoding="utf-8") as f:
        annex = json.load(f)
    annex_id    = annex.get("annex_id", "F")
    annex_title = annex.get("annex_title", "Guidelines for Impact Rating")
    docs = []
    for section in annex.get("sections", []):
        parts  = []
        sid    = section.get("section_id", "")
        stitle = section.get("section_title", "")
        parts.append(f"Annex {annex_id}: {annex_title} — Section {sid}: {stitle}")
        for c in section.get("content", []):
            parts.append(f"  - {c}")
        for t in section.get("tables", []):
            cols = t.get("columns", [])
            rows = t.get("rows", [])
            parts.append(f"\nTable {t.get('table_id')}: {t.get('table_title')}")
            if cols and rows:
                parts.append(" | ".join(cols))
                parts.append("-" * 40)
                for r in rows:
                    parts.append(" | ".join(str(r.get(col, "")) for col in cols))
        for note in section.get("notes", []):
            parts.append(f"Note: {note}")
        text = "\n".join(parts)
        if len(text.strip()) < 20:
            continue
        docs.append(Document(
            content=text,
            meta={"source": "ANNEX_F", "annex": annex_id, "section_id": sid, "title": stitle}
        ))
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# ECU data & Reports DB
# ─────────────────────────────────────────────────────────────────────────────

def _truncate_short(text, max_len: int = 800) -> str:
    """Simple truncation with str() coercion, used for reports-DB descriptions."""
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_len else text[:max_len] + "..."


# Visual-only fields that carry zero semantic value for the LLM
_VISUAL_FIELDS = {
    "position", "positionAbsolute", "dragging", "selected",
    "resizing", "isCopied", "zIndex", "width", "height",
}


def _strip_node(node: dict) -> dict:
    """Keep only semantically meaningful fields from a node object."""
    data = node.get("data", {})
    clean = {
        "id":       node.get("id", ""),
        "type":     node.get("type", "default"),
        "parentId": node.get("parentId"),
        "isAsset":  node.get("isAsset", False),
        "label":    data.get("label", "") or f"(group:{node.get('id','')[:8]})",
        "properties": node.get("properties", []),
    }
    if data.get("description"):
        clean["description"] = data["description"]
    # Keep color so LLM reproduces the same scheme
    bg = data.get("style", {}).get("backgroundColor")
    if bg:
        clean["backgroundColor"] = bg
    sz_h = data.get("style", {}).get("height") or node.get("height")
    sz_w = data.get("style", {}).get("width")  or node.get("width")
    if sz_h:
        clean["height"] = sz_h
    if sz_w:
        clean["width"]  = sz_w
    return clean


def _strip_edge(edge: dict) -> dict:
    """Keep only semantically meaningful fields from an edge object."""
    return {
        "id":           edge.get("id", ""),
        "source":       edge.get("source", ""),
        "target":       edge.get("target", ""),
        "sourceHandle": edge.get("sourceHandle", ""),
        "targetHandle": edge.get("targetHandle", ""),
        "protocol":     edge.get("data", {}).get("label", ""),
        "properties":   edge.get("properties", []),
    }


def _strip_derivation(d: dict) -> dict:
    return {
        "name":         d.get("name", ""),
        "asset":        d.get("asset", ""),
        "loss":         d.get("loss", ""),
        "damage_scene": d.get("damage_scene", ""),
    }


def _strip_detail(det: dict) -> dict:
    return {
        "Name":        det.get("Name", ""),
        "Description": det.get("Description", ""),
        "cyberLosses": [
            {"name": cl.get("name", ""), "node": cl.get("node", "")}
            for cl in det.get("cyberLosses", [])
        ],
        "impacts": det.get("impacts", {}),
    }


def _strip_attack_path(ap: dict) -> dict:
    """Extract the semantically useful fields from an AttackPaths entry."""
    return {
        "name":              ap.get("Name", ap.get("name", "")),
        "feasibility":       ap.get("Attack Feasibilities Rating",
                                   ap.get("Attack Feasibility Rating", "")),
        "elapsed_time":      ap.get("Elapsed Time", ""),
        "expertise":         ap.get("Expertise", ""),
        "equipment":         ap.get("Equipment", ""),
        "knowledge":         ap.get("Knowledge of the Item", ""),
        "window":            ap.get("Window of Opportunity", ""),
    }


def _strip_cybersec_req(scene: dict) -> dict:
    """Extract the semantically useful fields from a Cybersecurity scene entry."""
    return {
        "name":             scene.get("Name", scene.get("name", "")),
        "attack_scene":     scene.get("attack_scene_name", ""),
        "description":      _truncate_short(scene.get("Description") or "", 400),
    }


def _serialize_report_for_llm(
    model_name: str,
    nodes_list: list,
    edges_list: list,
    derivation_list: list,
    details_list: list,
    attack_paths: list | None = None,
    cybersec_reqs: list | None = None,
) -> str:
    """
    Produce a compact, semantically complete text representation of an entire
    reports_db entry — stripping all visual/layout-only fields so the LLM
    gets the full architecture without token-wasting coordinates and style noise.

    NEW: also serialises AttackPaths (feasibility ratings) and Cybersecurity
    requirements (threat→attack-scene mapping) when present.
    The base64 `image` field is NEVER included.
    """
    payload = {
        "model": model_name,
        "nodes": [_strip_node(n) for n in nodes_list],
        "edges": [_strip_edge(e) for e in edges_list],
        "damage_derivations": [
            _strip_derivation(d) for d in derivation_list if d.get("name")
        ],
        "damage_details": [
            _strip_detail(det) for det in details_list if det.get("Name")
        ],
    }

    # ── Attack paths (feasibility analysis) ──────────────────────────────────
    if attack_paths:
        stripped_paths = [
            _strip_attack_path(ap)
            for ap in attack_paths
            if ap.get("Name") or ap.get("name")
        ]
        if stripped_paths:
            payload["attack_paths"] = stripped_paths

    # ── Cybersecurity requirements (threat → attack scene mapping) ────────────
    if cybersec_reqs:
        stripped_reqs = [
            _strip_cybersec_req(s)
            for s in cybersec_reqs
            if s.get("Name") or s.get("name")
        ]
        if stripped_reqs:
            payload["cybersecurity_requirements"] = stripped_reqs

    return (
        f"=== FULL REFERENCE ARCHITECTURE: {model_name} ===\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
        + f"\n=== END REFERENCE ARCHITECTURE: {model_name} ==="
    )

def ingest_ecu(ecu_path) -> list[Document]:
    if not Path(ecu_path).exists():
        print(f"  ECU file not found: {ecu_path} — skipping.")
        return []
    with open(ecu_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    docs  = []
    items = data.items() if isinstance(data, dict) else enumerate(data)
    for key, val in items:
        docs.append(Document(
            content=json.dumps(val, indent=2),
            meta={"source": "ECU", "title": str(key)}
        ))
    return docs


def ingest_reports_db(reports_path) -> list[Document]:
    docs = []
    path = Path(reports_path)
    if not path.exists():
        print(f"  Reports DB folder not found: {reports_path}")
        return docs

    for json_file in sorted(path.glob("*.json")):
        fname = json_file.name
        with open(json_file, "r", encoding="utf-8") as f:
            report = json.load(f)

        if "assets" in report and "damage_scenarios" in report:
            assets_block    = report["assets"]
            damage_block    = report["damage_scenarios"]
            model_name      = assets_block.get("model_id", fname.replace(".json", ""))
            nodes_list      = assets_block.get("template", {}).get("nodes", [])
            derivation_list = damage_block.get("Derivations") or damage_block.get("derivation") or []
            details_list    = damage_block.get("Details")      or damage_block.get("details")     or []
            # Compact format has no AttackPaths / Cybersecurity sections
            attack_paths_raw  = []
            cybersec_raw      = []
        elif "Assets" in report:
            a_block         = report["Assets"][0] if report.get("Assets") else {}
            model_name      = report["Models"][0]["name"] if report.get("Models") else fname
            nodes_list      = a_block.get("template", {}).get("nodes", [])
            ds_list         = report.get("Damage_scenarios") or report.get("DamageScenarios") or []
            d_block         = ds_list[0] if ds_list else {}
            derivation_list = d_block.get("Derivations") or d_block.get("derivation") or []
            details_list    = d_block.get("Details")      or d_block.get("details")     or []
            # ── NEW: extract AttackPaths entries ─────────────────────────────
            ap_list = report.get("AttackPaths") or report.get("Attack_paths") or []
            # Each AttackPaths entry holds a list of individual attack paths
            attack_paths_raw = []
            for ap_block in ap_list:
                inner = ap_block.get("attack_paths") or ap_block.get("AttackPaths") or []
                attack_paths_raw.extend(inner)
            # ── NEW: extract Cybersecurity requirement scenes ─────────────────
            cs_list = report.get("Cybersecurity") or []
            cybersec_raw = []
            for cs_block in cs_list:
                scenes = cs_block.get("scenes") or []
                cybersec_raw.extend(scenes)
        else:
            print(f"  Unrecognised format in {fname} — skipping.")
            continue

        # ── Extract edges (needed for full_file chunk and edge summary) ─────
        if "assets" in report and "damage_scenarios" in report:
            edges_list = report["assets"].get("template", {}).get("edges", [])
        elif "Assets" in report:
            edges_list = (report["Assets"][0] if report.get("Assets") else {}).get("template", {}).get("edges", [])
        else:
            edges_list = []

        # ── FULL-FILE chunk (ALWAYS FIRST) ────────────────────────────────
        # Serialises the entire report semantically — this is the primary
        # context the LLM uses; individual chunks below are supplementary.
        # NOTE: the base64 `image` field is NEVER included.
        full_text = _serialize_report_for_llm(
            model_name, nodes_list, edges_list, derivation_list, details_list,
            attack_paths=attack_paths_raw,
            cybersec_reqs=cybersec_raw,
        )
        docs.append(Document(
            content=full_text,
            meta={"source": "REPORTS_DB", "file": fname,
                  "model": model_name, "type": "full_file"}
        ))

        node_count = 0
        for node in nodes_list:
            label, desc, props, ntype = _clean_node_for_text(node)
            # Fall back to id prefix for unlabelled group nodes
            if not label or label.strip() == "":
                label = f"(group:{node.get('id','')[:8]})"
            is_asset = node.get("isAsset", False)
            docs.append(Document(
                content=(
                    f"Reference Component [{model_name}]: {label}\n"
                    f"Type: {ntype}  IsAsset: {is_asset}\n"
                    f"Description: {desc}\n"
                    f"Security Properties: {', '.join(props) if props else 'N/A'}"
                ),
                meta={"source": "REPORTS_DB", "file": fname, "model": model_name,
                      "type": "asset", "is_asset": is_asset, "node_id": node.get("id", "")}
            ))
            node_count += 1

        deriv_count = 0
        for d in derivation_list:
            name = d.get("name", "")
            if not name:
                continue
            docs.append(Document(
                content=(
                    f"Reference Damage Derivation [{model_name}]:\n"
                    f"Threat/Weakness: {name}\n"
                    f"Affected Asset: {d.get('asset', '')}\n"
                    f"Cyber Loss: {d.get('loss', '')}\n"
                    f"Damage Scene: {d.get('damage_scene', '')}"
                ),
                meta={"source": "REPORTS_DB", "file": fname,
                      "model": model_name, "type": "damage_derivation"}
            ))
            deriv_count += 1

        detail_count = 0
        for det in details_list:
            dname = det.get("Name", "")
            if not dname:
                continue
            impacts    = det.get("impacts", {})
            losses     = [(cl.get("name", ""), cl.get("node", "")) for cl in det.get("cyberLosses", [])]
            impact_str = "  ".join(f"{k}: {v}" for k, v in impacts.items() if v)
            loss_str   = ", ".join(f"{n} ({nd})" for n, nd in losses if n)
            docs.append(Document(
                content=(
                    f"Reference Damage Scenario [{model_name}]: {dname}\n"
                    f"Description: {_truncate_short(det.get('Description', ''), 800)}\n"
                    f"Cyber Losses: {loss_str}\n"
                    f"Impact Ratings: {impact_str}"
                ),
                meta={"source": "REPORTS_DB", "file": fname,
                      "model": model_name, "type": "damage_detail"}
            ))
            detail_count += 1

        # ── NEW: AttackPaths chunks ──────────────────────────────────────
        ap_count = 0
        for ap in attack_paths_raw:
            aname = ap.get("Name") or ap.get("name", "")
            if not aname:
                continue
            docs.append(Document(
                content=(
                    f"Reference Attack Path [{model_name}]: {aname}\n"
                    f"Feasibility Rating : {ap.get('Attack Feasibilities Rating', ap.get('Attack Feasibility Rating', 'N/A'))}\n"
                    f"Elapsed Time       : {ap.get('Elapsed Time', 'N/A')}\n"
                    f"Expertise Required : {ap.get('Expertise', 'N/A')}\n"
                    f"Equipment          : {ap.get('Equipment', 'N/A')}\n"
                    f"Knowledge Required : {ap.get('Knowledge of the Item', 'N/A')}\n"
                    f"Window of Opportunity: {ap.get('Window of Opportunity', 'N/A')}"
                ),
                meta={"source": "REPORTS_DB", "file": fname,
                      "model": model_name, "type": "attack_path"}
            ))
            ap_count += 1

        # ── NEW: Cybersecurity requirement chunks ────────────────────────
        cs_count = 0
        for scene in cybersec_raw:
            sname = scene.get("Name") or scene.get("name", "")
            if not sname:
                continue
            docs.append(Document(
                content=(
                    f"Reference Cybersecurity Requirement [{model_name}]: {sname}\n"
                    f"Linked Attack Scene: {scene.get('attack_scene_name', 'N/A')}\n"
                    f"Description: {_truncate_short(scene.get('Description') or '', 400)}"
                ),
                meta={"source": "REPORTS_DB", "file": fname,
                      "model": model_name, "type": "cybersec_requirement"}
            ))
            cs_count += 1

        # ── NEW: Hierarchy summary chunk ─────────────────────────────────
        # Build a parent-child tree description so the retriever can surface
        # the full structural layout in one chunk.
        id_to_label = {}
        children_map = {}   # parentId -> [child labels]
        for node in nodes_list:
            label = node.get("data", {}).get("label", "") or node.get("id", "")
            nid   = node.get("id", "")
            ntype = node.get("type", "default")
            pid   = node.get("parentId")
            id_to_label[nid] = label or f"(unnamed {ntype})"
            children_map.setdefault(pid, []).append(
                f"{label} (type:{ntype})" if label else f"(unnamed {ntype})"
            )

        hierarchy_lines = [f"Architecture Hierarchy for [{model_name}]:"]
        # Top-level nodes (parentId is None or null)
        for pid_key in [None, "null", ""]:
            for child in children_map.get(pid_key, []):
                hierarchy_lines.append(f"  TOP: {child}")
        # Nested children
        for pid, kids in children_map.items():
            if pid in [None, "null", ""]:
                continue
            parent_label = id_to_label.get(pid, pid)
            hierarchy_lines.append(f"  {parent_label} contains: {', '.join(kids)}")

        if len(hierarchy_lines) > 1:
            docs.append(Document(
                content="\n".join(hierarchy_lines),
                meta={"source": "REPORTS_DB", "file": fname,
                      "model": model_name, "type": "hierarchy_summary"}
            ))

        # ── Edge summary chunk ───────────────────────────────────────────
        if edges_list:
            edge_lines = [f"Edge connections for [{model_name}]:"]
            for edge in edges_list:
                elabel = edge.get("data", {}).get("label", "")
                src_id = edge.get("source", "")
                tgt_id = edge.get("target", "")
                src_label = id_to_label.get(src_id, src_id)
                tgt_label = id_to_label.get(tgt_id, tgt_id)
                eprops = edge.get("properties", [])
                edge_lines.append(
                    f"  {elabel}: {src_label} ↔ {tgt_label} "
                    f"(properties: {', '.join(eprops) if eprops else 'none'})"
                )
            docs.append(Document(
                content="\n".join(edge_lines),
                meta={"source": "REPORTS_DB", "file": fname,
                      "model": model_name, "type": "edge_summary"}
            ))

        print(
            f"  {fname}: {node_count} components | {deriv_count} derivations | "
            f"{detail_count} details | {ap_count} attack paths | {cs_count} cybersec reqs"
        )

    print(f"\nREPORTS_DB total chunks: {len(docs)}")
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Master loader
# ─────────────────────────────────────────────────────────────────────────────

def load_all_documents() -> list[Document]:
    """Load and merge all dataset sources."""
    print("Loading threat frameworks...")
    mitre_docs  = ingest_mitre(MITRE_MOBILE, "MITRE_MOBILE")
    mitre_docs += ingest_mitre(MITRE_ICS,    "MITRE_ICS")
    atm_docs    = ingest_atm(ATM_PATH)
    capec_docs  = ingest_capec(CAPEC_PATH)
    cwe_docs    = ingest_cwe(CWE_PATH)
    print(Counter(d.meta["source"] for d in mitre_docs + atm_docs + capec_docs + cwe_docs))

    print("\nLoading ISO 21434 clauses...")
    iso_docs   = ingest_iso_clauses(CLAUSE_PATH)
    annex_docs = ingest_annex(ANNEX_PATH)
    print(f"  ISO 21434: {len(iso_docs)} sections  |  Annex F: {len(annex_docs)} sections")

    print("\nLoading ECU data...")
    ecu_docs = ingest_ecu(ECU_PATH)
    print(f"  ECU entries: {len(ecu_docs)}")

    print("\nLoading REPORTS DB...")
    reports_docs = ingest_reports_db(REPORTS_PATH)

    all_docs  = ecu_docs + iso_docs + annex_docs
    all_docs += mitre_docs + atm_docs + capec_docs + cwe_docs + reports_docs

    print(f"\n{'='*50}")
    print(f"Total documents: {len(all_docs)}")
    dist = Counter(d.meta.get("source", "?") for d in all_docs)
    for src, cnt in sorted(dist.items()):
        print(f"  {src:<20}: {cnt}")
    return all_docs
