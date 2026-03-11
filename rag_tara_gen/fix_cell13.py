"""
fix_cell13.py  —  Fix the ordering/duplication issues in Cell 13 and 13b:

Issues found:
  1. Cell 13 (user_query cell) has its own print("Generating TARA...") block  
     that fires BEFORE resolve_ecu runs, and is then duplicated in the run cell.
  2. ecu_entry could be undefined if Cell 13 is re-run without Cell 13b.

Fixes:
  A. Remove the stale print block from Cell 13 (just set user_query cleanly).
  B. Add `ecu_entry = None` guard default at the top of the enriched_query/run cell
     so it never crashes on NameError.
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

# ── Fix A: Clean up Cell 13 (user_query cell) ────────────────────────────────
# Remove the stale print block — just keep user_query assignment + comments
i_query, cell_query = None, None
for i, c in enumerate(cells):
    if 'user_query = "Battery Management System ECU"' in src(c) and "resolve_ecu" not in src(c):
        i_query, cell_query = i, c
        break

if cell_query:
    NEW_QUERY_CELL = '''\
# ── Set your query here ──────────────────────────────────────────────────────
user_query = "Battery Management System ECU"   # Change as needed
# Examples:
#   "Infotainment Head Unit"
#   "Gateway / Domain Controller"
#   "ADAS ECU"
#   "Telematics Control Unit"
#   "OBD-II Diagnostic Port"
#   "BCM (Body Control Module)"
#   "ABS (Anti-lock Braking System)"
# ─────────────────────────────────────────────────────────────────────────────
print(f"Query set: {user_query}")
print("Run the next cell (13b) to resolve ECU and generate the TARA report.")
'''
    set_source(cell_query, NEW_QUERY_CELL)
    print(f"Fix A OK: cleaned Cell 13 (user_query) at index {i_query}")
else:
    print("Fix A FAIL: user_query cell not found")

# ── Fix B: Add `ecu_entry = None` guard to the enriched_query/run cell ───────
i_run, cell_run = None, None
for i, c in enumerate(cells):
    if "enriched_query" in src(c) and "tara_pipeline.run" in src(c):
        i_run, cell_run = i, c
        break

if cell_run:
    NEW_RUN_CELL = '''\
# Guard: ensure ecu_entry is defined even if Cell 13b was skipped
if "ecu_entry" not in dir():
    ecu_entry = None

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

print(f"Generating TARA for  : {user_query}")
print(f"ECU match            : {ecu_entry['name'] if ecu_entry else 'None (open-ended)'}")
print(f"Enriched query (120c): {enriched_query[:120]}...")
print(f"Retriever top_k      : 20")
print(f"Embedding model      : {EMBED_MODEL}")

result = tara_pipeline.run(
    {
        "text_embedder": {"text": user_query},          # plain query for retrieval
        "prompt_builder": {"question": enriched_query}  # enriched for LLM
    },
    include_outputs_from=["retriever"]
)

print("Pipeline run complete.")
'''
    set_source(cell_run, NEW_RUN_CELL)
    print(f"Fix B OK: patched run cell at index {i_run}")
else:
    print("Fix B FAIL: run cell not found")

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print("Notebook saved.")
