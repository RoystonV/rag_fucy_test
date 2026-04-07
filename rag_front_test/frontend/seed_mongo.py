# =============================================================================
# seed_mongo.py  -  Load existing TARA JSON outputs into MongoDB
# =============================================================================
# Run this once (from rag_front_test/frontend/) to populate the DB with
# the pre-generated reports that already exist in outputs/tara/
# =============================================================================

import sys
import os
import json
from pathlib import Path

# Force UTF-8 output to avoid Windows cp1252 emoji errors
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent / "rag_tara_gen"
sys.path.insert(0, str(ROOT))

try:
    import db as mongo_db
except ImportError as e:
    print(f"[ERROR] Could not import db.py: {e}")
    sys.exit(1)

TARA_DIR = ROOT / "outputs" / "tara"

def infer_ecu_name(filename: str) -> str:
    """Turn tara_output_Battery_Management_System_ECU.json -> Battery Management System ECU"""
    name = filename.replace("tara_output_", "").replace(".json", "")
    return name.replace("_", " ")

def main():
    files = list(TARA_DIR.glob("tara_output_*.json"))
    if not files:
        print(f"[ERROR] No tara_output_*.json files found in {TARA_DIR}")
        sys.exit(1)

    print(f"\n[SEED] Seeding MongoDB with {len(files)} reports...\n")

    if not mongo_db.is_connected():
        print("[ERROR] Cannot connect to MongoDB. Is mongod running?")
        print(f"   URI: {mongo_db.MONGO_URI}")
        sys.exit(1)

    ok_count = 0
    for fpath in files:
        try:
            with open(fpath, encoding="utf-8") as f:
                tara_json = json.load(f)

            ecu_name = infer_ecu_name(fpath.name)
            query    = ecu_name

            mongo_id = mongo_db.save_report(tara_json, query_name=query, ecu_name=ecu_name)
            status   = "[OK]" if mongo_id else "[WARN]"
            print(f"  {status} {fpath.name}  ->  {ecu_name}")
            if mongo_id:
                ok_count += 1

        except Exception as e:
            print(f"  [FAIL] {fpath.name}: {e}")

    reports = mongo_db.list_reports()
    print(f"\n[DONE] MongoDB now has {len(reports)} reports in tara_db.reports")
    print(f"       {ok_count}/{len(files)} files seeded successfully")
    print("\nStart the frontend:\n  python server.py\n")

if __name__ == "__main__":
    main()
