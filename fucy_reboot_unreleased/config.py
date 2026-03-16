# =============================================================================
# config.py — Central configuration for fucy_reboot RAG + CAG pipeline
# =============================================================================

import os

# ---------------------------------------------------------------------------
# Google Gemini API
# ---------------------------------------------------------------------------
GOOGLE_API_KEY: str = os.environ.get("GOOGLE_API_KEY", "YOUR_KEY_HERE")
GEMINI_MODEL: str = "gemini-2.0-flash"
GENERATION_KWARGS: dict = {"temperature": 0.0}

# ---------------------------------------------------------------------------
# Embedding model (sentence-transformers)
# Swap this to try different embedding models without touching any other code
# ---------------------------------------------------------------------------
EMBED_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_BATCH_SIZE: int = 64

# ---------------------------------------------------------------------------
# Chunking strategy
# ---------------------------------------------------------------------------
CHUNK_STRATEGY: str = "sentence_window"   # "sentence_window" | "fixed_overlap" | "structure_aware"
CHUNK_SIZE: int = 300                      # tokens / chars per chunk
CHUNK_OVERLAP: int = 50                    # overlap between consecutive chunks
SENTENCES_PER_CHUNK: int = 5              # used by sentence_window strategy

# ---------------------------------------------------------------------------
# Indexing & persistence
# ---------------------------------------------------------------------------
INDEX_CACHE_DIR: str = "cache/index"       # directory to save/load index pickles
EMBED_CACHE_DIR: str = "cache/embeddings"  # directory to cache embedding vectors

# ---------------------------------------------------------------------------
# Retrieval — Hybrid (BM25 + dense vector)
# ---------------------------------------------------------------------------
RETRIEVAL_TOP_K: int = 30          # initial candidates from each retriever
BM25_WEIGHT: float = 0.3           # weight for BM25 in RRF fusion
VECTOR_WEIGHT: float = 0.7         # weight for dense vector in RRF fusion
ENABLE_QUERY_REWRITING: bool = True
ENABLE_MULTI_QUERY: bool = False   # generates N query variants (adds latency)
MULTI_QUERY_COUNT: int = 3

# ---------------------------------------------------------------------------
# Re-ranking
# ---------------------------------------------------------------------------
RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_TOP_N: int = 10           # how many chunks pass to context assembler

# ---------------------------------------------------------------------------
# Context assembly (hallucination reduction)
# ---------------------------------------------------------------------------
MIN_RELEVANCE_SCORE: float = 0.0   # drop chunks below this re-ranker score
MAX_CONTEXT_CHARS: int = 80_000    # hard token budget (chars ≈ tokens * 4)
ENABLE_MMR_DEDUP: bool = True      # remove near-duplicate chunks (MMR)
MMR_LAMBDA: float = 0.7            # 1.0 = pure relevance, 0.0 = pure diversity

# ---------------------------------------------------------------------------
# CAG — Cache-Augmented Generation (Gemini explicit context caching)
# These are the small, static reference datasets preloaded into the LLM cache
# ---------------------------------------------------------------------------
ENABLE_CAG: bool = True
CAG_TTL_SECONDS: int = 3600        # how long to keep the Gemini cache alive (1 hr)
CAG_CACHE_REGISTRY: str = "cache/cag_registry.json"  # stores active cache_name + expiry

# Files to include in the CAG context cache (paths relative to fucy_reboot/)
CAG_DATASETS: list = [
    "datasets/dataecu.json",
    "datasets/annex.json",
    "datasets/clauses",            # folder — all .json files inside are included
]

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
EVAL_PRECISION_K: int = 5          # k for precision@k metric
