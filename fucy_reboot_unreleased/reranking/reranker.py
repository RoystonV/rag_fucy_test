# =============================================================================
# reranker.py — Cross-encoder re-ranking via Haystack
# =============================================================================

from haystack import Document
from haystack.components.rankers import TransformersSimilarityRanker

import config


class CrossEncoderReranker:
    """
    Second-stage re-ranker using a cross-encoder model to score
    (query, document) pairs for fine-grained relevance.

    Wraps Haystack's TransformersSimilarityRanker.
    """

    def __init__(
        self,
        model: str | None = None,
        top_n: int | None = None,
    ):
        self.model = model or config.RERANKER_MODEL
        self.top_n = top_n or config.RERANKER_TOP_N

        self._ranker = TransformersSimilarityRanker(
            model=self.model,
            top_k=self.top_n,
        )
        self._warmed = False

    def _warm_up(self):
        if not self._warmed:
            self._ranker.warm_up()
            self._warmed = True

    def rerank(self, query: str, documents: list[Document]) -> list[Document]:
        """
        Re-rank documents using the cross-encoder model.

        Args:
            query: The user query.
            documents: Candidate documents from the retriever.

        Returns:
            Top-N documents re-ranked by cross-encoder score.
        """
        if not documents:
            return []

        self._warm_up()

        try:
            result = self._ranker.run(query=query, documents=documents)
            reranked = result["documents"]
            print(f"  [Reranker] {len(documents)} -> {len(reranked)} (top-{self.top_n})")
            return reranked
        except Exception as e:
            print(f"  [Reranker] Error, falling back to unsorted: {e}")
            return documents[: self.top_n]
