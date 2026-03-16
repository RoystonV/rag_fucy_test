# =============================================================================
# embedder.py — Batched embedding with disk caching
# =============================================================================

import hashlib
import json
import os
import pickle
from pathlib import Path
from typing import Any

from haystack import Document
from haystack.components.embedders import SentenceTransformersDocumentEmbedder

import config


class BatchedEmbedder:
    """
    Wraps SentenceTransformersDocumentEmbedder with:
    - Configurable batch sizes
    - Disk caching to avoid re-embedding unchanged content
    - Easy model swapping via config.EMBED_MODEL
    """

    def __init__(
        self,
        model: str | None = None,
        batch_size: int | None = None,
        cache_dir: str | None = None,
    ):
        self.model = model or config.EMBED_MODEL
        self.batch_size = batch_size or config.EMBED_BATCH_SIZE
        self.cache_dir = Path(cache_dir or config.EMBED_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._embedder = SentenceTransformersDocumentEmbedder(
            model=self.model,
            batch_size=self.batch_size,
        )
        self._warmed = False

    def _warm_up(self):
        if not self._warmed:
            self._embedder.warm_up()
            self._warmed = True

    def _cache_key(self, contents: list[str]) -> str:
        """Generate a deterministic cache key from content + model name."""
        hasher = hashlib.md5()
        hasher.update(self.model.encode())
        for c in contents:
            hasher.update(c.encode())
        return hasher.hexdigest()

    def _load_cache(self, key: str) -> list[Document] | None:
        """Try to load cached embeddings."""
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
            except Exception:
                return None
        return None

    def _save_cache(self, key: str, docs: list[Document]):
        """Save embeddings to disk cache."""
        cache_file = self.cache_dir / f"{key}.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(docs, f)
        except Exception as e:
            print(f"[EmbedCache] Warning: failed to save cache: {e}")

    def embed_documents(self, documents: list[Document], use_cache: bool = True) -> list[Document]:
        """
        Embed a list of Haystack Documents.

        If use_cache is True and a matching cache exists, returns cached result.
        Otherwise embeds and caches.
        """
        self._warm_up()

        if use_cache:
            contents = [d.content or "" for d in documents]
            key = self._cache_key(contents)
            cached = self._load_cache(key)
            if cached is not None:
                print(f"  [EmbedCache] HIT — loaded {len(cached)} cached embeddings")
                return cached

        # Embed in batches
        result = self._embedder.run(documents=documents)
        embedded_docs = result["documents"]

        if use_cache:
            self._save_cache(key, embedded_docs)
            print(f"  [EmbedCache] MISS — embedded & cached {len(embedded_docs)} documents")

        return embedded_docs

    def embed_from_records(self, records: list[dict[str, Any]], use_cache: bool = True) -> list[Document]:
        """
        Convenience: convert {content, meta} dicts to Haystack Documents,
        embed them, and return.
        """
        documents = [
            Document(content=r["content"], meta=r.get("meta", {}))
            for r in records
        ]
        return self.embed_documents(documents, use_cache=use_cache)
