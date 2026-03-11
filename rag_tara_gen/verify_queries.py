import json, importlib.util
from pathlib import Path

BASE     = Path(r"c:\Users\Roysten\Desktop\FUCYTECH 8th sem\rag_develop\rag_fucy_test\rag_tara_gen")
ECU_PATH = BASE / "datasets" / "dataecu.json"
NB_PATH  = BASE / "Tara_expo_v2.0.ipynb"

nb    = json.load(open(NB_PATH, encoding="utf-8"))
cells = nb["cells"]
src   = lambda c: "".join(c.get("source", []))

# Extract resolve_ecu source from notebook
resolve_src = next((src(c) for c in cells if "def resolve_ecu" in src(c)), "")
# Write to temp module (stop before the ecu_entry call)
body = resolve_src.split("ecu_entry = resolve_ecu")[0]
tmp = Path(r"C:\Users\Roysten\AppData\Local\Temp\_rtest.py")
tmp.write_text(
    f'import json\nfrom pathlib import Path\nECU_PATH = Path(r"{ECU_PATH}")\n' + body,
    encoding="utf-8"
)
spec = importlib.util.spec_from_file_location("_rtest", tmp)
mod  = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fn   = mod.resolve_ecu

ecu_db = json.load(open(ECU_PATH, encoding="utf-8"))

tests = [
    ("Battery Management System ECU",   "bms"),
    ("Infotainment Head Unit",           "infotainment"),
    ("Gateway / Domain Controller",      "gateway"),
    ("ADAS ECU",                         "adas"),
    ("bms system",                       "bms"),
    ("OBD-II Diagnostic Port",           "obd"),
    ("V2X Communication Module",         "v2x"),
    ("Telematics Control Unit",          "tcu"),
    ("EPS Electric Power Steering",      "eps"),
    ("CAN Bus Network",                  "can_bus"),
    ("ABS Anti-lock Braking System",     "abs"),
    ("Unknown XYZ",                       None),
]

all_ok = True
for q, exp in tests:
    entry = fn(q)
    if entry:
        # Match by name (not identity) since fn reopens the json internally
        key = next((k for k, v in ecu_db.items() if v["name"] == entry["name"]), "?")
        ok  = (exp is None) or (key == exp)
        if not ok: all_ok = False
        print(f'[{"OK  " if ok else "WRONG"}] {q!r}  =>  {key!r}: {entry["name"]}')
    else:
        ok = exp is None
        if not ok: all_ok = False
        print(f'[{"OK  " if ok else "WARN"}] {q!r} => No match (expected={exp!r})')

print()
print("ALL QUERIES MATCHED CORRECTLY" if all_ok else "SOME WRONG - see above")
tmp.unlink()
