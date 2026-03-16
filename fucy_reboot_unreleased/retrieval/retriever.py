# =============================================================================
# retriever.py — Hybrid search: BM25 + dense vector with RRF fusion
# =============================================================================

from haystack import Document
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.retrievers.in_memory import (
    InMemoryEmbeddingRetriever,
    InMemoryBM25Retriever,
)
from haystack.components.joiners import DocumentJoiner

import config


class HybridRetriever:
    """
    Fuses BM25 keyword search + dense vector search via Reciprocal Rank Fusion.

    Uses Haystack 2.x native components:
    - InMemoryBM25Retriever for sparse keyword matching
    - InMemoryEmbeddingRetriever for dense semantic matching
    - DocumentJoiner for reciprocal_rank_fusion
    """

    def __init__(
        self,
        document_store: InMemoryDocumentStore,
        model: str | None = None,
        top_k: int | None = None,
        bm25_weight: float | None = None,
        vector_weight: float | None = None,
    ):
        self.top_k = top_k or config.RETRIEVAL_TOP_K
        self.bm25_weight = bm25_weight or config.BM25_WEIGHT
        self.vector_weight = vector_weight or config.VECTOR_WEIGHT

        # Dense retriever
        self._text_embedder = SentenceTransformersTextEmbedder(
            model=model or config.EMBED_MODEL
        )
        self._text_embedder.warm_up()

        self._vector_retriever = InMemoryEmbeddingRetriever(
            document_store=document_store,
            top_k=self.top_k,
        )

        # Sparse BM25 retriever
        self._bm25_retriever = InMemoryBM25Retriever(
            document_store=document_store,
            top_k=self.top_k,
        )

        # Joiner for RRF fusion
        self._joiner = DocumentJoiner(
            join_mode="reciprocal_rank_fusion",
            top_k=self.top_k,
            weights=[self.vector_weight, self.bm25_weight],
        )

    def retrieve(self, query: str) -> list[Document]:
        """
        Run hybrid retrieval: embed query → vector search + BM25 → RRF fuse.
        Returns a single ranked list of documents.
        """
        # 1. Embed the query for dense retrieval
        embed_result = self._text_embedder.run(text=query)
        query_embedding = embed_result["embedding"]

        # 2. Dense retrieval
        vector_result = self._vector_retriever.run(query_embedding=query_embedding)
        vector_docs = vector_result["documents"]

        # 3. BM25 retrieval
        bm25_result = self._bm25_retriever.run(query=query)
        bm25_docs = bm25_result["documents"]

        # 4. Fuse via RRF
        joined = self._joiner.run(documents=[vector_docs, bm25_docs])
        fused_docs = joined["documents"]

        return fused_docs
