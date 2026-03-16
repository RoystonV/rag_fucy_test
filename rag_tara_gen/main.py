# =============================================================================
# main.py — CLI entry point for TARA RAG Pipeline
# =============================================================================
# Usage:
#   python main.py --query "Battery Management System ECU"
#   python main.py --query "Infotainment Head Unit" --output my_report.json
#   python main.py --list-ecus
#   python main.py --query "Gateway ECU" --no-save
# =============================================================================

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from components import (
    resolve_ecu, list_ecus, build_enriched_query,
    parse_and_fix, print_summary,
    EMBED_MODEL, GEMINI_MODEL, RETRIEVER_TOP_K,
)
from ingest import load_all_documents
from pipeline import build_pipeline, run_query


def main():
    parser = argparse.ArgumentParser(
        description="TARA RAG Pipeline — ISO/SAE 21434 Threat Analysis & Risk Assessment Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --query "Battery Management System ECU"
  python main.py --query "Infotainment Head Unit" --output infotainment_tara.json
  python main.py --list-ecus
        """,
    )
    parser.add_argument("--query",  "-q", type=str, default=None,
                        help='Target ECU or system (e.g. "Battery Management System ECU")')
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output JSON filename (default: tara_output_<query>.json)")
    parser.add_argument("--no-save", action="store_true",
                        help="Print JSON to console only, do not save to file")
    parser.add_argument("--list-ecus", action="store_true",
                        help="List all ECU keys from dataecu.json and exit")
    args = parser.parse_args()

    # ── List ECUs and exit (no API key needed) ────────────────────────────────
    if args.list_ecus:
        list_ecus()
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    user_query = args.query.strip()

    print("\n" + "=" * 60)
    print("  TARA RAG Pipeline v2.0  |  ISO/SAE 21434")
    print("=" * 60)
    print(f"  Query : {user_query}")
    print("=" * 60 + "\n")

    # ── API key check ─────────────────────────────────────────────────────────
    if "GOOGLE_API_KEY" not in os.environ:
        print("❌ GOOGLE_API_KEY is not set.")
        print("   Windows : set GOOGLE_API_KEY=your-key-here")
        print("   Linux   : export GOOGLE_API_KEY=your-key-here")
        sys.exit(1)

    # ── Step 1: Resolve ECU ───────────────────────────────────────────────────
    print("[1/4] Resolving ECU from dataecu.json...")
    ecu_entry = resolve_ecu(user_query)
    if ecu_entry:
        print(f"  ✅ Matched : {ecu_entry['name']}")
        print(f"     Type   : {ecu_entry['type']}")
        print(f"     Hint   : {ecu_entry['hint'][:100]}...")
    else:
        print("  ⚠️  No dataecu.json match — using open-ended generation")

    enriched_query = build_enriched_query(user_query, ecu_entry)

    # ── Step 2: Ingest ────────────────────────────────────────────────────────
    print("\n[2/4] Ingesting datasets...")
    all_docs = load_all_documents()

    # ── Step 3: Embed & pipeline ──────────────────────────────────────────────
    print("\n[3/4] Embedding documents & building pipeline...")
    pipeline, _ = build_pipeline(all_docs)

    # ── Step 4: Generate ──────────────────────────────────────────────────────
    print("\n[4/4] Generating TARA report...")
    print(f"  Embedding model : {EMBED_MODEL}")
    print(f"  LLM model       : {GEMINI_MODEL}")
    print(f"  Retriever top_k : {RETRIEVER_TOP_K}")
    print(f"  Enriched query  : {enriched_query[:120]}...")

    raw_output = run_query(pipeline, user_query, enriched_query)

    # ── Post-process ──────────────────────────────────────────────────────────
    print("\nPost-processing...")
    tara_json = parse_and_fix(raw_output)

    if tara_json is None:
        print("❌ Failed to generate valid JSON. Raw output:")
        print(raw_output[:1000])
        sys.exit(1)

    print("✅ Valid JSON parsed.")
    print_summary(tara_json)

    # ── Print ─────────────────────────────────────────────────────────────────
    print("\n" + "-" * 60)
    print(json.dumps(tara_json, indent=2, ensure_ascii=False))
    print("-" * 60)

    # ── Save ──────────────────────────────────────────────────────────────────
    if not args.no_save:
        out_file = args.output or (
            "tara_output_" + re.sub(r"[^a-zA-Z0-9_-]", "_", user_query.strip()) + ".json"
        )
        out_path = Path(__file__).parent / out_file
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(tara_json, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Saved → {out_path}")


if __name__ == "__main__":
    main()
