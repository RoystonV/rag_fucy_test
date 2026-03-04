# =============================================================================
# main.py — Entry point for the BMS RAG chatbot
#
# Usage:
#   python main.py
#   python main.py --no-save              # disable auto JSON export
#   python main.py --output-dir exports   # custom output folder (default: output)
#
# Set your Gemini API key in config.py or as an environment variable:
#   $env:GOOGLE_API_KEY = "your-key-here"   (PowerShell)
#   set GOOGLE_API_KEY=your-key-here        (CMD)
# =============================================================================

import argparse
import os

from ingest import build_document_store
from pipeline import build_pipeline
from query import ask


def main():
    parser = argparse.ArgumentParser(description="BMS RAG Chatbot")
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Disable automatic JSON export after each query.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        metavar="DIR",
        help="Directory for exported JSON files (default: output).",
    )
    args = parser.parse_args()

    save = not args.no_save
    output_dir = args.output_dir

    print("=" * 60)
    print("  BMS RAG Chatbot — powered by Haystack + Gemini")
    print("=" * 60)
    if save:
        print(f"  JSON export: ON  ->  {os.path.abspath(output_dir)}/")
    else:
        print("  JSON export: OFF (use --output-dir DIR to enable)")

    # Step 1: Load data, embed, and store
    print("\n[1/2] Ingesting and embedding documents...")
    document_store = build_document_store()

    # Step 2: Build the RAG pipeline
    print("\n[2/2] Building RAG pipeline...")
    rag_pipeline = build_pipeline(document_store)

    # Step 3: Interactive chatbot loop
    history = []
    print("\nReady! Ask anything in natural language.")
    print("Commands: 'exit' to quit | 'history' to list past queries")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nQuery: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        if user_input.lower() == "history":
            if not history:
                print("No history yet.")
            else:
                for i, h in enumerate(history, 1):
                    print(f"  [{i}] {h['query']}")
            continue

        print()
        parsed = ask(rag_pipeline, user_input, save=save, output_dir=output_dir)
        if parsed:
            history.append({"query": user_input, "result": parsed})
        print("-" * 60)


if __name__ == "__main__":
    main()

