# =============================================================================
# query_rewriter.py — LLM-based query expansion & rewriting
# =============================================================================

import os
from haystack_integrations.components.generators.google_ai import GoogleAIGeminiGenerator

import config


class QueryRewriter:
    """
    Rewrites the user query into a more retrieval-friendly form using Gemini.
    Expands abbreviations, adds domain synonyms, removes ambiguity.
    """

    REWRITE_PROMPT = """You are a query rewriting assistant for a cybersecurity TARA (Threat Analysis and Risk Assessment) knowledge base about automotive ECUs.

Given a user query, rewrite it to be more specific and retrieval-friendly:
- Expand abbreviations (BMS → Battery Management System, CAN → Controller Area Network)
- Add relevant domain synonyms
- Make implicit concepts explicit
- Keep the rewrite concise (1-2 sentences max)

Return ONLY the rewritten query, nothing else.

User query: {query}

Rewritten query:"""

    def __init__(self):
        os.environ["GOOGLE_API_KEY"] = config.GOOGLE_API_KEY
        self._generator = GoogleAIGeminiGenerator(
            model=config.GEMINI_MODEL,
            generation_kwargs={"temperature": 0.0},
        )

    def rewrite(self, query: str) -> str:
        """
        Rewrite the query for better retrieval.
        Returns the rewritten query string.
        Falls back to original query on any error.
        """
        if not config.ENABLE_QUERY_REWRITING:
            return query

        try:
            prompt = self.REWRITE_PROMPT.format(query=query)
            result = self._generator.run(prompt=prompt)
            rewritten = result["replies"][0].strip()
            if rewritten:
                print(f"  [QueryRewriter] '{query}' → '{rewritten}'")
                return rewritten
        except Exception as e:
            print(f"  [QueryRewriter] Fallback to original query: {e}")

        return query
