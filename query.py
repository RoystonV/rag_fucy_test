# =============================================================================
# query.py — ask() function: run a natural language query through the pipeline
# =============================================================================

import json
import os
import re
from datetime import datetime
from pathlib import Path

from haystack import Pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_filename(query: str) -> str:
    """Turn a query string into a safe filename slug (max 40 chars)."""
    slug = re.sub(r"[^\w\s-]", "", query.lower()).strip()
    slug = re.sub(r"\s+", "_", slug)[:40]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"rag_{slug}_{timestamp}.json"


def save_json(data: dict, query: str, output_dir: str = "output") -> str:
    """
    Save *data* as a formatted JSON file inside *output_dir*.

    Returns the absolute path of the saved file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(query)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return os.path.abspath(filepath)


# ---------------------------------------------------------------------------
# Main query function
# ---------------------------------------------------------------------------

def ask(
    rag_pipeline: Pipeline,
    query: str,
    pretty: bool = True,
    save: bool = True,
    output_dir: str = "output",
) -> dict:
    """
    Run the RAG pipeline for a natural language query.

    Args:
        rag_pipeline: The assembled Haystack Pipeline.
        query:        Natural language question.
        pretty:       If True, pretty-print the full JSON response.
        save:         If True (default), save the JSON result to *output_dir*.
        output_dir:   Directory where JSON files are written (default: 'output').

    Returns:
        Parsed JSON dict (empty dict on parse failure).
    """
    result = rag_pipeline.run({
        "text_embedder":  {"text": query},
        "prompt_builder": {"question": query},
    })
    raw = result["llm"]["replies"][0]

    try:
        parsed = json.loads(raw)
        if pretty:
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        inner = parsed.get("result", {})
        print(f"\n[Intent] {inner.get('query_intent', 'n/a')}")
        for section in ["assets", "edges", "damage_scenarios", "damage_details"]:
            items = inner.get(section)
            if items is not None:
                print(f"  {section}: {len(items)} item(s)")

        # ---- auto-save JSON ----
        if save:
            path = save_json(parsed, query, output_dir=output_dir)
            print(f"\n  [Saved] {path}")

        return parsed
    except json.JSONDecodeError as e:
        print("[JSON parse error]", e)
        print(raw)
        return {}
