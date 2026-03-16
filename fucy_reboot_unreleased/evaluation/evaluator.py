# =============================================================================
# evaluator.py — Retrieval quality metrics
# =============================================================================

from typing import Any

from haystack import Document


class RetrievalEvaluator:
    """
    Offline evaluation utilities:
    - precision_at_k
    - mean_reciprocal_rank
    - context_coverage (simple overlap check)
    """

    @staticmethod
    def precision_at_k(
        retrieved_ids: list[str],
        relevant_ids: set[str],
        k: int = 5,
    ) -> float:
        """
        Precision@k: fraction of top-k retrieved docs that are relevant.
        """
        top_k = retrieved_ids[:k]
        if not top_k:
            return 0.0
        hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
        return hits / len(top_k)

    @staticmethod
    def mean_reciprocal_rank(
        retrieved_ids: list[str],
        relevant_ids: set[str],
    ) -> float:
        """
        Mean Reciprocal Rank: 1/rank of the first relevant document.
        """
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_ids:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def context_coverage(
        retrieved_docs: list[Document],
        expected_keywords: list[str],
    ) -> float:
        """
        Simple keyword coverage: what fraction of expected keywords
        appear in the retrieved context?
        """
        if not expected_keywords:
            return 1.0

        combined = " ".join(d.content or "" for d in retrieved_docs).lower()
        hits = sum(1 for kw in expected_keywords if kw.lower() in combined)
        return hits / len(expected_keywords)

    @staticmethod
    def run_eval_batch(
        pipeline,
        test_cases: list[dict[str, Any]],
        k: int = 5,
    ) -> dict[str, float]:
        """
        Run batch evaluation on a set of test cases.

        Each test case: {"query": str, "relevant_ids": set[str]}
        Returns: {"avg_precision@k": float, "avg_mrr": float}
        """
        total_p = 0.0
        total_mrr = 0.0

        for case in test_cases:
            query = case["query"]
            relevant = set(case.get("relevant_ids", []))

            # Retrieve using the pipeline's retrieval step
            docs = pipeline.retrieve(query)
            doc_ids = [d.id for d in docs]

            total_p += RetrievalEvaluator.precision_at_k(doc_ids, relevant, k)
            total_mrr += RetrievalEvaluator.mean_reciprocal_rank(doc_ids, relevant)

        n = max(len(test_cases), 1)
        return {
            f"avg_precision@{k}": total_p / n,
            "avg_mrr": total_mrr / n,
        }
