# =============================================================================
# assembler.py — Context assembly with dedup, MMR, and token budget
# =============================================================================

import numpy as np
from haystack import Document

import config


class ContextAssembler:
    """
    Builds the final context window for the LLM by:
    1. Filtering by minimum relevance score
    2. MMR deduplication for diversity
    3. Token budget management
    4. Source attribution tagging
    """

    def __init__(
        self,
        min_score: float | None = None,
        max_chars: int | None = None,
        enable_mmr: bool | None = None,
        mmr_lambda: float | None = None,
    ):
        self.min_score = min_score if min_score is not None else config.MIN_RELEVANCE_SCORE
        self.max_chars = max_chars or config.MAX_CONTEXT_CHARS
        self.enable_mmr = enable_mmr if enable_mmr is not None else config.ENABLE_MMR_DEDUP
        self.mmr_lambda = mmr_lambda or config.MMR_LAMBDA

    def assemble(self, documents: list[Document], query: str = "") -> list[Document]:
        """
        Process documents into a clean context window.

        Returns filtered, deduplicated documents within token budget.
        """
        if not documents:
            return []

        # 1. Relevance threshold filtering
        filtered = self._filter_by_score(documents)

        # 2. MMR deduplication
        if self.enable_mmr and len(filtered) > 1:
            filtered = self._mmr_deduplicate(filtered)

        # 3. Token budget
        budgeted = self._apply_token_budget(filtered)

        print(f"  [Context] {len(documents)} → {len(budgeted)} chunks (budget: {self.max_chars} chars)")
        return budgeted

    def format_context(self, documents: list[Document]) -> str:
        """Format assembled documents into a single context string with source tags."""
        parts = []
        for i, doc in enumerate(documents):
            source = doc.meta.get("source", "unknown")
            file_name = doc.meta.get("file", "")
            tag = f"[source: {source}"
            if file_name:
                tag += f" | {file_name}"
            tag += f" | chunk {i + 1}]"

            parts.append(f"{tag}\n{doc.content}")

        return "\n\n---\n\n".join(parts)

    def _filter_by_score(self, documents: list[Document]) -> list[Document]:
        """Drop documents below minimum relevance score."""
        if self.min_score <= 0.0:
            return documents

        filtered = [d for d in documents if (d.score or 0.0) >= self.min_score]
        if len(filtered) < len(documents):
            print(f"  [Context] Score filter: {len(documents)} → {len(filtered)} (min={self.min_score})")
        return filtered

    def _mmr_deduplicate(self, documents: list[Document]) -> list[Document]:
        """
        Maximal Marginal Relevance: balance relevance with diversity.
        Removes near-duplicate chunks that add little new information.
        """
        # If docs don't have embeddings, skip MMR
        if not all(d.embedding for d in documents):
            return documents

        selected: list[Document] = [documents[0]]
        remaining = list(documents[1:])

        while remaining:
            best_score = -float("inf")
            best_idx = 0

            sel_embeddings = np.array([d.embedding for d in selected])

            for i, candidate in enumerate(remaining):
                cand_emb = np.array(candidate.embedding)

                # Relevance to query (use document score as proxy)
                relevance = candidate.score or 0.0

                # Max similarity to already-selected docs
                similarities = np.dot(sel_embeddings, cand_emb) / (
                    np.linalg.norm(sel_embeddings, axis=1) * np.linalg.norm(cand_emb) + 1e-8
                )
                max_sim = float(np.max(similarities))

                # MMR score
                mmr = self.mmr_lambda * relevance - (1 - self.mmr_lambda) * max_sim

                if mmr > best_score:
                    best_score = mmr
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected

    def _apply_token_budget(self, documents: list[Document]) -> list[Document]:
        """Keep adding documents until we exceed the character budget."""
        budgeted = []
        total_chars = 0

        for doc in documents:
            doc_len = len(doc.content or "")
            if total_chars + doc_len > self.max_chars:
                break
            budgeted.append(doc)
            total_chars += doc_len

        return budgeted
