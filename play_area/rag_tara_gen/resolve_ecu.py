# =============================================================================
# resolve_ecu.py — Fuzzy ECU matcher against dataecu.json
# =============================================================================

import json
from pathlib import Path

import config


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SUFFIX_WORDS = {
    "ecu", "system", "module", "interface", "controller", "unit",
    "network", "port", "server", "bus", "head", "vehicle", "automotive"
}

_ALIASES = {
    "obd":              "obd",
    "obd-ii":           "obd",
    "obd2":             "obd",
    "tcu":              "tcu",
    "telematics control": "tcu",
    "bcm":              "bcm",
    "ecm":              "ecm",
    "ivi":              "ivi",
    "eps":              "eps",
    "abs":              "abs",
    "bms":              "bms",
    "adas":             "adas",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _acronym(text: str) -> str:
    """Generate acronym, stripping generic automotive suffix words."""
    skip      = {"the", "and", "for", "of", "a", "an", "or", "in", "on", "to", "/"}
    words     = [w.strip("()/-").lower() for w in text.replace("/", " ").split()]
    sig_words = [w for w in words if w and w not in skip]
    core      = [w for w in sig_words if w not in _SUFFIX_WORDS]
    chosen    = core if core else sig_words
    return "".join(w[0] for w in chosen if w)


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

def resolve_ecu(query: str, ecu_path=None) -> dict | None:
    """
    Fuzzy-match query against dataecu.json keys and names.

    Matching order:
      0. Alias table (well-known abbreviations / phrases)
      1. Exact key or key as standalone word in query
      2. Full entry name is substring of query
      3a. Exact acronym match
      3b. Acronym starts key (within 1 extra char)
      4. Significant name-word overlap (>= 2 shared core words)
      5. Any key word > 3 chars appears in query

    Returns matched entry dict {name, type, hint} or None.
    """
    ecu_path = ecu_path or config.ECU_PATH
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

    # Pass 2: full entry name substring
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
        core_name  = [w for w in name_words if len(w) > 2 and w not in _SUFFIX_WORDS]
        if sum(1 for w in core_name if w in q) >= 2:
            return entry

    # Pass 5: any key word > 3 chars in query
    for key, entry in ecu_db.items():
        key_words = key.replace("_", " ").split()
        if any(w in q for w in key_words if len(w) > 3):
            return entry

    return None


def list_ecus(ecu_path=None) -> None:
    """Print all ECU keys and names from dataecu.json."""
    ecu_path = ecu_path or config.ECU_PATH
    with open(ecu_path, "r", encoding="utf-8") as f:
        ecu_db = json.load(f)
    print(f"\n{'Key':<20} {'Name'}")
    print("-" * 60)
    for key, entry in ecu_db.items():
        print(f"  {key:<18} {entry.get('name', '')}")
    print(f"\nTotal: {len(ecu_db)} ECU entries")
