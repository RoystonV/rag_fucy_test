# =============================================================================
# query.py — ask() function: run a natural language query through the pipeline
# =============================================================================

import json
from haystack import Pipeline


def ask(rag_pipeline: Pipeline, query: str, pretty: bool = True) -> dict:
    """
    Run the RAG pipeline for a natural language query.

    Args:
        rag_pipeline: The assembled Haystack Pipeline.
        query:        Natural language question.
        pretty:       If True, pretty-print the full JSON response.

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
        return parsed
    except json.JSONDecodeError as e:
        print("[JSON parse error]", e)
        print(raw)
        return {}
