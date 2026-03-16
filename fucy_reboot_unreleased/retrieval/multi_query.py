# =============================================================================
# multi_query.py — Multi-query retrieval with result fusion
# =============================================================================

import os
from haystack import Document
from haystack_integrations.components.generators.google_ai import GoogleAIGeminiGenerator

import config


class MultiQueryRetriever:
    """
    Generates N alternative query phrasings via Gemini, runs retrieval
    for each, and de-duplicates/merges the results.

    Off by default (config.ENABLE_MULTI_QUERY) since it adds latency.
    """

    EXPAND_PROMPT = """Generate {n} different phrasings of this query for a cybersecurity TARA knowledge base.
Each phrasing should capture a different angle or level of specificity.
Return one phrasing per line, nothing else.

Original query: {query}

Phrasings:"""

    def __init__(self):
        os.environ["GOOGLE_API_KEY"] = config.GOOGLE_API_KEY
        self._generator = GoogleAIGeminiGenerator(
            model=config.GEMINI_MODEL,
            generation_kwargs={"temperature": 0.3},  # slightly creative
        )

    def generate_queries(self, query: str, n: int | None = None) -> list[str]:
        """Generate N alternative phrasings of the query."""
        if not config.ENABLE_MULTI_QUERY:
            return [query]

        n = n or config.MULTI_QUERY_COUNT
        try:
            prompt = self.EXPAND_PROMPT.format(query=query, n=n)
            result = self._generator.run(prompt=prompt)
            raw = result["replies"][0].strip()
            variants = [line.strip().lstrip("0123456789.-) ") for line in raw.split("\n") if line.strip()]
            # Always include the original
            all_queries = [query] + variants[:n]
            print(f"  [MultiQuery] Generated {len(all_queries)} query variants")
            return all_queries
        except Exception as e:
            print(f"  [MultiQuery] Fallback to single query: {e}")
            return [query]

    @staticmethod
    def deduplicate(doc_lists: list[list[Document]]) -> list[Document]:
        """Merge multiple document lists, removing duplicates by document ID."""
        seen_ids = set()
        merged = []
        for docs in doc_lists:
            for doc in docs:
                doc_id = doc.id
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    merged.append(doc)
        return merged
