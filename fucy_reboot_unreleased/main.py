# =============================================================================
# main.py — Interactive CLI entry point
# =============================================================================

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent))

import config
from pipeline import FucyPipeline


def main():
    parser = argparse.ArgumentParser(
        description="fucy_reboot — Hybrid RAG + CAG Pipeline for TARA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--datasets", default="datasets",
        help="Path to datasets directory (default: datasets/)",
    )
    parser.add_argument(
        "--rebuild", action="store_true",
        help="Force rebuild of the document index (ignore cache)",
    )
    parser.add_argument(
        "--no-cag", action="store_true",
        help="Disable CAG (context cache) even if enabled in config",
    )
    parser.add_argument(
        "--save-dir", default="outputs",
        help="Directory to save query results (default: outputs/)",
    )
    parser.add_argument(
        "--query", type=str, default=None,
        help="Run a single query and exit (non-interactive mode)",
    )
    args = parser.parse_args()

    # Override CAG if requested
    if args.no_cag:
        config.ENABLE_CAG = False

    # Build pipeline
    print("\n" + "=" * 60)
    print("  fucy_reboot — Hybrid RAG + CAG Pipeline")
    print("=" * 60)

    pipeline = FucyPipeline(datasets_dir=args.datasets)

    # Build index
    print("\n[1/2] Building document index...")
    doc_count = pipeline.build_index(force_rebuild=args.rebuild)
    print(f"  Index ready: {doc_count} documents")

    # Build CAG cache
    if config.ENABLE_CAG:
        print("\n[2/2] Setting up CAG cache...")
        cache = pipeline.build_cag_cache()
        if cache:
            print(f"  CAG active: {cache}")
        else:
            print("  CAG: skipped (build failed or disabled)")
    else:
        print("\n[2/2] CAG disabled")

    print("\n" + "=" * 60)
    print("  Ready! Type your query or 'quit' to exit.")
    print("  Type 'save' after a query to save the last result.")
    print("=" * 60 + "\n")

    # Single query mode
    if args.query:
        result = pipeline.run(args.query)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Interactive loop
    last_result = None
    last_query = None
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            user_input = input("\n🔍 Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if user_input.lower() == "save" and last_result is not None:
            # Save last result
            safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in last_query[:50])
            out_path = save_dir / f"{safe_name}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(last_result, f, indent=2, ensure_ascii=False)
            print(f"  Saved to {out_path}")
            continue

        # Run query
        result = pipeline.run(user_input)
        last_result = result
        last_query = user_input

        # Pretty print
        print("\n" + "-" * 40)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 40)


if __name__ == "__main__":
    main()
