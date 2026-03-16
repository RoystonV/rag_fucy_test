# =============================================================================
# pipeline.py — Main RAG + CAG orchestrator
# =============================================================================

import sys
import os
from pathlib import Path
from typing import Any, Optional

# Ensure fucy_reboot is on the path
sys.path.insert(0, str(Path(__file__).parent))

from haystack import Document

import config
from ingestion.ingestor import load_all_datasets
from chunking.chunker import SemanticChunker
from embeddings.embedder import BatchedEmbedder
from indexing.index_manager import IndexManager
from retrieval.retriever import HybridRetriever
from retrieval.query_rewriter import QueryRewriter
from retrieval.multi_query import MultiQueryRetriever
from reranking.reranker import CrossEncoderReranker
from context.assembler import ContextAssembler
from cag.cache_manager import CacheManager
from generation.generator import FucyGenerator


class FucyPipeline:
    """
    Main orchestrator. Pipeline flow:

      query → [QueryRewriter] → [HybridRetriever (BM25 + Vector RRF)]
            → [CrossEncoderReranker] → [ContextAssembler]
            → [FucyGenerator (with optional CAG cache)] → JSON result

    CAG is an additive layer: if enabled, static domain knowledge gets
    preloaded into Gemini's context cache and attached to every LLM call.
    """

    def __init__(self, datasets_dir: str = "datasets"):
        self.datasets_dir = datasets_dir

        # Core components (initialized lazily during build_index)
        self._index_manager = IndexManager()
        self._embedder = BatchedEmbedder()
        self._retriever: Optional[HybridRetriever] = None
        self._rewriter = QueryRewriter()
        self._multi_query = MultiQueryRetriever()
        self._reranker = CrossEncoderReranker()
        self._assembler = ContextAssembler()
        self._generator = FucyGenerator()

        # CAG layer
        self._cache_manager = CacheManager(datasets_dir=datasets_dir)
        self._cache_name: Optional[str] = None

    def build_index(self, force_rebuild: bool = False) -> int:
        """
        Ingest → chunk → embed → index. Uses cache when available.
        Returns the number of indexed documents.
        """
        # Try loading cached index
        if not force_rebuild:
            store = self._index_manager.load()
            if store is not None:
                self._retriever = HybridRetriever(document_store=store)
                return store.count_documents()

        print("\n[Pipeline] Building index from scratch...")

        # 1. Ingest
        print("\n1. Ingesting datasets...")
        records = load_all_datasets(self.datasets_dir)

        # 2. Chunk
        print("\n2. Chunking...")
        chunker = SemanticChunker(
            strategy=config.CHUNK_STRATEGY,
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            sentences_per_chunk=config.SENTENCES_PER_CHUNK,
        )
        chunks = chunker.chunk(records)
        print(f"  {len(records)} records → {len(chunks)} chunks")

        # 3. Embed
        print("\n3. Embedding...")
        embedded_docs = self._embedder.embed_from_records(chunks)

        # 4. Index
        print("\n4. Indexing...")
        store = self._index_manager.build(embedded_docs)
        self._index_manager.save()

        # 5. Build retriever
        self._retriever = HybridRetriever(document_store=store)

        print(f"\n[Pipeline] Index ready: {store.count_documents()} documents\n")
        return store.count_documents()

    def build_cag_cache(self) -> Optional[str]:
        """Build or retrieve the CAG context cache."""
        if not config.ENABLE_CAG:
            return None

        print("\n[Pipeline] Setting up CAG cache...")
        self._cache_name = self._cache_manager.get_or_build()
        return self._cache_name

    def retrieve(self, query: str) -> list[Document]:
        """Run the full retrieval pipeline (without generation)."""
        if self._retriever is None:
            raise RuntimeError("Index not built. Call build_index() first.")

        # Query rewriting
        rewritten = self._rewriter.rewrite(query)

        # Multi-query (if enabled)
        if config.ENABLE_MULTI_QUERY:
            queries = self._multi_query.generate_queries(rewritten)
            all_docs = []
            for q in queries:
                docs = self._retriever.retrieve(q)
                all_docs.append(docs)
            fused = MultiQueryRetriever.deduplicate(all_docs)
        else:
            fused = self._retriever.retrieve(rewritten)

        # Re-rank
        reranked = self._reranker.rerank(query, fused)

        # Assemble context
        assembled = self._assembler.assemble(reranked, query)

        return assembled

    def run(self, query: str, **overrides) -> dict[str, Any]:
        """
        Full pipeline: query → retrieve → generate → JSON.

        Overrides can temporarily change config values for this run:
            pipeline.run("query", RETRIEVAL_TOP_K=50, ENABLE_CAG=False)
        """
        # Apply any temporary overrides
        original_values = {}
        for key, value in overrides.items():
            if hasattr(config, key):
                original_values[key] = getattr(config, key)
                setattr(config, key, value)

        try:
            print(f"\n{'='*60}")
            print(f"  Query: {query}")
            print(f"{'='*60}")

            # Retrieve
            context_docs = self.retrieve(query)
            context_text = self._assembler.format_context(context_docs)

            # Check CAG
            cache = self._cache_name if config.ENABLE_CAG else None

            # Generate
            print("\n5. Generating response...")
            result = self._generator.generate(
                query=query,
                context_docs=context_docs,
                context_text=context_text,
                cache_name=cache,
            )

            print(f"\n{'='*60}")
            print(f"  Done. Retrieved {len(context_docs)} chunks.")
            if cache:
                print(f"  CAG cache: {cache}")
            print(f"{'='*60}\n")

            return result

        finally:
            # Restore original config values
            for key, value in original_values.items():
                setattr(config, key, value)
