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
    resolve_ecu, list_ecus, build_enriched_query, build_pinned_docs,
    EMBED_MODEL, GEMINI_MODEL, RETRIEVER_TOP_K,
)
from postprocess import parse_and_fix, print_summary
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
    print("  TARA RAG Pipeline v2.1  |  ISO/SAE 21434")
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

    # ── Step 2b: Strip unrelated ECU docs ─────────────────────────────────────
    # Remove every ECU doc that does NOT belong to the resolved ECU entry.
    # This prevents unrelated ECU component lists (ABS, ECM, Throttle, etc.)
    # from leaking into the prompt via pinned docs or the retriever.
    if ecu_entry:
        ecu_name_lc = ecu_entry.get("name", "").lower()
        before_count = sum(1 for d in all_docs if d.meta.get("source") == "ECU")
        all_docs = [
            d for d in all_docs
            if d.meta.get("source") != "ECU" or ecu_name_lc in d.content.lower()
        ]
        after_count = sum(1 for d in all_docs if d.meta.get("source") == "ECU")
        print(f"  🔍 ECU doc filter: kept {after_count}/{before_count} entries (matched ECU only)")

    # ── Step 2c: Build pinned context ─────────────────────────────────────────
    # Pinned docs = ECU entry + all REPORTS_DB chunks for the matched system.
    # These bypass the retriever and are always guaranteed in the prompt.
    pinned_docs, matched_model = build_pinned_docs(all_docs, ecu_entry)
    print(f"\n  📌 Pinned context docs : {len(pinned_docs)}")
    if matched_model:
        print(f"     REPORTS_DB model   : {matched_model} (full reference architecture pinned)")
    else:
        print("     REPORTS_DB model   : (none found — using dataecu hint + threat intelligence only)")
        # When there's no reference architecture, tighten the enriched query
        # to make very explicit that only the authoritative asset list may be used.
        if ecu_entry:
            enriched_query += (
                "\n\nIMPORTANT: No reference architecture exists in the database for this system. "
                "Generate ONLY the components listed in the AUTHORITATIVE ASSET LIST above. "
                "Do NOT add any extra components, sub-systems, or interfaces not mentioned there. "
                "For an unknown system with a partial asset list, prefer fewer, well-justified "
                "components over a long speculative list."
            )

    # ── Step 3: Embed & pipeline ──────────────────────────────────────────────
    print("\n[3/4] Embedding threat-framework docs & building pipeline...")
    print(f"  Embedding model : {EMBED_MODEL}")
    print(f"  LLM model       : {GEMINI_MODEL}")
    print(f"  Retriever top_k : {RETRIEVER_TOP_K}  (threat docs only)")
    text_embedder, retriever, prompt_builder, generator = build_pipeline(all_docs)

    # ── Step 4: Generate ──────────────────────────────────────────────────────
    print("\n[4/4] Generating TARA report...")
    print(f"  Enriched query  : {enriched_query[:120]}...")

    raw_output = run_query(
        text_embedder, retriever, prompt_builder, generator,
        user_query, enriched_query, pinned_docs,
    )

    # ── Post-process ──────────────────────────────────────────────────────────
    print("\nPost-processing...")
    tara_json = parse_and_fix(raw_output)

    if tara_json is None:
        print("❌ Failed to generate valid JSON. Raw output:")
        print(raw_output[:1000])
        sys.exit(1)

    print("✅ Valid JSON parsed.")
    print_summary(tara_json)

    # ── Optional: save prompt for debugging ───────────────────────────────────
    safe_name   = re.sub(r"[^a-zA-Z0-9_-]", "_", user_query.strip())
    prompts_dir = Path(__file__).parent / "outputs" / "prompts"
    tara_dir    = Path(__file__).parent / "outputs" / "tara"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    tara_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = prompts_dir / f"tara_prompt_{safe_name}.txt"
    try:
        # Reconstruct the prompt text for inspection
        from haystack.components.builders import PromptBuilder as _PB
        from prompt import TARA_PROMPT_TEMPLATE
        _pb = _PB(template=TARA_PROMPT_TEMPLATE, required_variables=["documents", "question"])
        from components import build_pinned_docs as _bpd
        # Re-assemble with same docs used (pinned_docs already computed above)
        embedding = text_embedder.run(text=user_query)["embedding"]
        retrieved = retriever.run(query_embedding=embedding)["documents"]
        all_ctx   = pinned_docs + retrieved
        _prompt   = _pb.run(documents=all_ctx, question=enriched_query)["prompt"]
        with open(prompt_path, "w", encoding="utf-8") as _f:
            _f.write(_prompt)
        print(f"  📄 Prompt saved → {prompt_path}")
    except Exception as _e:
        print(f"  ⚠️  Prompt save skipped: {_e}")

    # ── Print ─────────────────────────────────────────────────────────────────
    print("\n" + "-" * 60)
    print(json.dumps(tara_json, indent=2, ensure_ascii=False))
    print("-" * 60)

    # ── Save ──────────────────────────────────────────────────────────────────
    if not args.no_save:
        out_file = args.output or f"tara_output_{safe_name}.json"
        out_path = tara_dir / out_file
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(tara_json, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Saved → {out_path}")


if __name__ == "__main__":
    main()
