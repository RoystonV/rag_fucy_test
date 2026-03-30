# =============================================================================
# postprocess.py — UUID stamping, crosslinking, layout, and JSON parsing
# =============================================================================

import json
import re
import uuid as _uuid


# ─────────────────────────────────────────────────────────────────────────────
# UUID stamping
# ─────────────────────────────────────────────────────────────────────────────

def stamp_uuids(obj: dict) -> dict:
    """
    Walk the JSON tree and replace any id/_id/model_id that is empty,
    None, or a placeholder string with a fresh uuid4.
    """
    ID_KEYS = {"id", "_id", "model_id"}

    def _bad(val) -> bool:
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


# ─────────────────────────────────────────────────────────────────────────────
# nodeId cross-linking
# ─────────────────────────────────────────────────────────────────────────────

def crosslink_node_ids(obj: dict) -> dict:
    """
    After node UUIDs are stamped, propagate real nodeId values into
    Derivations[].nodeId and Details[].cyberLosses[].nodeId by label-matching.
    """
    nodes = obj.get("assets", {}).get("template", {}).get("nodes", [])
    label_to_id = {
        n.get("data", {}).get("label", "").lower(): n.get("id")
        for n in nodes if n.get("id")
    }

    for d in obj.get("damage_scenarios", {}).get("Derivations", []):
        nid = d.get("nodeId", "")
        if not nid or str(nid).startswith("<") or "PLACEHOLDER" in str(nid):
            matched    = label_to_id.get(d.get("asset", "").lower())
            d["nodeId"] = matched if matched else str(_uuid.uuid4())

    for det in obj.get("damage_scenarios", {}).get("Details", []):
        for cl in det.get("cyberLosses", []):
            nid = cl.get("nodeId", "")
            if not nid or str(nid).startswith("<") or "PLACEHOLDER" in str(nid):
                matched       = label_to_id.get(cl.get("node", "").lower())
                cl["nodeId"]  = matched if matched else str(_uuid.uuid4())
            if not cl.get("id") or str(cl.get("id", "")).startswith("<"):
                cl["id"] = str(_uuid.uuid4())

    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic layout
# ─────────────────────────────────────────────────────────────────────────────

_PAD      = 24   # padding inside a group (px)
_COL_GAP  = 20   # horizontal gap between sibling nodes
_ROW_GAP  = 20   # vertical gap between rows of nodes
_HEADER   = 36   # top space reserved for a group's own label


def apply_layout(obj: dict) -> dict:
    """
    Compute position and positionAbsolute for every node dynamically.

    Strategy
    ────────
    1.  Top-level system GROUP  → placed at canvas origin (0, 0).
    2.  External nodes          → parentId is null and type != "group";
                                  stacked to the right of the system group.
    3.  Children of any group   → arranged left-to-right in rows inside their
                                  parent, respecting each node's own width/height.
    4.  positionAbsolute        → computed recursively (parent abs + rel pos).
    """
    nodes = obj.get("assets", {}).get("template", {}).get("nodes", [])
    if not nodes:
        return obj

    # ── Build lookup structures ──────────────────────────────────────────────
    id_to_node   = {n["id"]: n for n in nodes}
    children_map = {}   # parentId (or None) -> [node, ...]
    for n in nodes:
        pid = n.get("parentId")
        children_map.setdefault(pid, []).append(n)

    # ── Helper: lay out a list of nodes inside a parent area ────────────────
    def _layout_children(parent_id: str | None,
                         area_w: float,
                         offset_x: float = _PAD,
                         offset_y: float = _PAD + _HEADER) -> None:
        kids = children_map.get(parent_id, [])
        if not kids:
            return

        # Split by type so groups go after regular nodes
        regular = [k for k in kids if k.get("type") != "group"]
        subgrps = [k for k in kids if k.get("type") == "group"]

        usable_w = area_w - _PAD * 2
        x, y     = offset_x, offset_y
        row_h    = 0

        for node in regular:
            nw = node.get("width")  or node.get("data", {}).get("style", {}).get("width",  150)
            nh = node.get("height") or node.get("data", {}).get("style", {}).get("height",  50)
            nw, nh = float(nw), float(nh)

            # Wrap to next row if it would overflow
            if x + nw > offset_x + usable_w and x > offset_x:
                x  = offset_x
                y += row_h + _ROW_GAP
                row_h = 0

            node["position"] = {"x": round(x, 2), "y": round(y, 2)}
            x    += nw + _COL_GAP
            row_h = max(row_h, nh)

        if regular:
            y += row_h + _ROW_GAP

        # Sub-groups placed below regular nodes, side by side
        sg_x = offset_x
        for sg in subgrps:
            sgw = sg.get("width")  or sg.get("data", {}).get("style", {}).get("width",  300)
            sgh = sg.get("height") or sg.get("data", {}).get("style", {}).get("height", 200)
            sgw, sgh = float(sgw), float(sgh)
            sg["position"] = {"x": round(sg_x, 2), "y": round(y, 2)}
            _layout_children(sg["id"], sgw,
                             offset_x=_PAD,
                             offset_y=_PAD + _HEADER)
            sg_x += sgw + _COL_GAP

    # ── Step 1: lay out the top-level system group(s) ───────────────────────
    top_groups   = [n for n in nodes
                    if n.get("parentId") is None and n.get("type") == "group"]
    ext_nodes    = [n for n in nodes
                    if n.get("parentId") is None and n.get("type") != "group"]

    sys_right = 0.0   # rightmost edge of all system groups (for external nodes)
    sys_y     = 0.0

    for grp in top_groups:
        grp_w = grp.get("width")  or grp.get("data", {}).get("style", {}).get("width",  1041)
        grp_h = grp.get("height") or grp.get("data", {}).get("style", {}).get("height",  510)
        grp_w, grp_h = float(grp_w), float(grp_h)

        grp["position"]         = {"x": 0.0, "y": sys_y}
        grp["positionAbsolute"] = {"x": 0.0, "y": sys_y}

        _layout_children(grp["id"], grp_w, offset_x=_PAD, offset_y=_PAD + _HEADER)

        sys_right = max(sys_right, grp_w)
        sys_y    += grp_h + 60

    # ── Step 2: external nodes stacked to the right ──────────────────────────
    ext_x = sys_right + 60.0
    ext_y = 40.0
    for node in ext_nodes:
        nh = node.get("height") or node.get("data", {}).get("style", {}).get("height", 50)
        node["position"]         = {"x": round(ext_x, 2), "y": round(ext_y, 2)}
        node["positionAbsolute"] = {"x": round(ext_x, 2), "y": round(ext_y, 2)}
        ext_y += float(nh) + 30

    # ── Step 3: compute positionAbsolute recursively ─────────────────────────
    def _abs(node_id: str, parent_abs_x: float, parent_abs_y: float) -> None:
        node = id_to_node.get(node_id)
        if not node:
            return
        rel = node.get("position", {"x": 0.0, "y": 0.0})
        ax  = parent_abs_x + rel["x"]
        ay  = parent_abs_y + rel["y"]
        node["positionAbsolute"] = {"x": round(ax, 2), "y": round(ay, 2)}
        for child in children_map.get(node_id, []):
            _abs(child["id"], ax, ay)

    for grp in top_groups:
        abs_pos = grp["positionAbsolute"]
        for child in children_map.get(grp["id"], []):
            _abs(child["id"], abs_pos["x"], abs_pos["y"])

    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Master entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_and_fix(raw_text: str) -> dict | None:
    """
    Strip markdown fences, parse JSON, apply UUID stamping, crosslink nodeIds,
    then compute dynamic positions for all nodes.
    Returns fixed dict or None on parse failure.
    """
    cleaned = re.sub(r"^```[a-z]*\n?", "", raw_text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip())

    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON parse error: {e}")
        print(f"Raw output (first 500 chars):\n{cleaned[:500]}")
        return None

    obj = stamp_uuids(obj)
    obj = crosslink_node_ids(obj)
    obj = apply_layout(obj)          # ← dynamic positions
    return obj


def print_summary(tara_json: dict) -> None:
    """Print a short summary of the generated TARA JSON."""
    node_count  = len(tara_json.get("assets", {}).get("template", {}).get("nodes", []))
    edge_count  = len(tara_json.get("assets", {}).get("template", {}).get("edges", []))
    deriv_count = len(tara_json.get("damage_scenarios", {}).get("Derivations", []))
    ds_count    = len(tara_json.get("damage_scenarios", {}).get("Details", []))
    print(f"   Nodes          : {node_count}")
    print(f"   Edges          : {edge_count}")
    print(f"   Derivations    : {deriv_count}")
    print(f"   Damage details : {ds_count}")
    print("   IDs            : all stamped as uuid4")
    print("   Positions      : dynamically computed")

