"""
patch_resolve_ecu_final.py  —  Add alias table for obd/tcu edge cases.

Instead of further complicating the fuzzy logic, add a small alias lookup
at the start of resolve_ecu so well-known query patterns always hit the right key.
"""
import json
from pathlib import Path

NB_PATH = Path(r"c:\Users\Roysten\Desktop\FUCYTECH 8th sem\rag_develop\rag_fucy_test\rag_tara_gen\Tara_expo_v2.0.ipynb")

with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

def set_source(cell, text):
    lines = text.splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1].rstrip("\n")
    cell["source"] = lines

NEW_RESOLVE = '''\
# ── Resolve the queried system against dataecu.json ──────────────────────────
# dataecu.json has 50 ECU/system entries, each with a curated `hint` field
# listing the EXACT expected assets for that system. We match user_query to
# the closest entry and inject its hint as an authoritative constraint into the
# LLM prompt -- so the LLM generates ONLY those assets and no others.
# ─────────────────────────────────────────────────────────────────────────────

# Generic automotive suffix words removed before acronym extraction
_SUFFIX_WORDS = {
    "ecu", "system", "module", "interface", "controller", "unit",
    "network", "port", "server", "bus", "head", "vehicle", "automotive"
}

# Well-known phrase -> dataecu.json key aliases  (handles ambiguous queries)
_ALIASES = {
    "obd": "obd",
    "obd-ii": "obd",
    "obd2":  "obd",
    "tcu":   "tcu",
    "telematics control": "tcu",
    "bcm":   "bcm",
    "ecm":   "ecm",
    "ivi":   "ivi",
    "eps":   "eps",
    "abs":   "abs",
    "bms":   "bms",
    "adas":  "adas",
}

def _acronym(text):
    """Generate acronym stripping generic automotive suffixes."""
    skip = {"the", "and", "for", "of", "a", "an", "or", "in", "on", "to", "/"}
    words = [w.strip("()/-").lower() for w in text.replace("/", " ").split()]
    sig_words  = [w for w in words if w and w not in skip]
    core_words = [w for w in sig_words if w not in _SUFFIX_WORDS]
    chosen = core_words if core_words else sig_words
    return "".join(w[0] for w in chosen if w)

def resolve_ecu(query, ecu_path=ECU_PATH):
    """
    Fuzzy-match query against dataecu.json keys and names.

    Matching order:
      0. Alias table (well-known abbreviations / phrases)
      1. Exact key or key as standalone word in query
      2. Full entry name is substring of query
      3. Acronym of query (suffix-stripped) matches or starts a key
      4. Significant name-word overlap (>= 2 shared core words)
      5. Any key word > 3 chars appears in query

    Returns matched entry dict {name, type, hint} or None.
    """
    with open(ecu_path, "r", encoding="utf-8") as f:
        ecu_db = json.load(f)

    q = query.lower().strip()

    # Pass 0: alias table
    for phrase, key in _ALIASES.items():
        if phrase in q and key in ecu_db:
            return ecu_db[key]

    # Pass 1: exact key or key as standalone word
    for key, entry in ecu_db.items():
        if key == q or f" {key} " in f" {q} ":
            return entry

    # Pass 2: full entry name substring match
    for key, entry in ecu_db.items():
        if entry["name"].lower() in q:
            return entry

    # Pass 3a: exact acronym match
    query_acronym = _acronym(q)
    for key, entry in ecu_db.items():
        if query_acronym and query_acronym == key:
            return entry

    # Pass 3b: acronym starts key (within 1 extra char)
    if len(query_acronym) >= 2:
        for key, entry in ecu_db.items():
            if key.startswith(query_acronym) and len(key) - len(query_acronym) <= 1:
                return entry

    # Pass 4: significant name-word overlap
    for key, entry in ecu_db.items():
        name_words = [w.strip("()/-").lower()
                      for w in entry["name"].replace("/", " ").split()]
        core_name  = [w for w in name_words
                      if len(w) > 2 and w not in _SUFFIX_WORDS]
        if sum(1 for w in core_name if w in q) >= 2:
            return entry

    # Pass 5: any key word > 3 chars in query
    for key, entry in ecu_db.items():
        key_words = key.replace("_", " ").split()
        if any(w in q for w in key_words if len(w) > 3):
            return entry

    return None


ecu_entry = resolve_ecu(user_query)
if ecu_entry:
    print(f"Matched ECU  : {ecu_entry[\'name\']}")
    print(f"Type         : {ecu_entry[\'type\']}")
    print(f"Asset hint   : {ecu_entry[\'hint\']}")
else:
    print("No dataecu.json match found -- will use open-ended generation.")
'''

found = False
for i, c in enumerate(cells):
    if "def resolve_ecu" in src(c):
        set_source(c, NEW_RESOLVE)
        print(f"Patched resolve_ecu cell at index {i}")
        found = True
        break

if not found:
    print("FAIL: resolve_ecu cell not found")

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print("Notebook saved.")
