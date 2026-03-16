# =============================================================================
# index_manager.py — Document store management with persistence
# =============================================================================

import os
import pickle
from pathlib import Path
from typing import Optional

from haystack import Document
from haystack.document_stores.in_memory import InMemoryDocumentStore

import config


class IndexManager:
    """
    Manages the InMemoryDocumentStore lifecycle:
    - build() — create fresh index from embedded documents
    - save() / load() — persist to / restore from disk (pickle)
    - add() — incremental document addition
    """

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = Path(cache_dir or config.INDEX_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.store: Optional[InMemoryDocumentStore] = None

    def build(self, documents: list[Document]) -> InMemoryDocumentStore:
        """Create a fresh store and write all documents into it."""
        self.store = InMemoryDocumentStore()
        self.store.write_documents(documents)
        print(f"  [Index] Built fresh index with {self.store.count_documents()} documents")
        return self.store

    def add(self, documents: list[Document]):
        """Incrementally add documents to an existing store."""
        if self.store is None:
            raise RuntimeError("No index loaded. Call build() or load() first.")
        self.store.write_documents(documents)
        print(f"  [Index] Added {len(documents)} documents (total: {self.store.count_documents()})")

    def save(self, name: str = "default"):
        """Persist the document store to disk."""
        if self.store is None:
            raise RuntimeError("No index to save. Call build() first.")
        path = self.cache_dir / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump(self.store, f)
        print(f"  [Index] Saved index to {path}")

    def load(self, name: str = "default") -> Optional[InMemoryDocumentStore]:
        """Load a persisted document store from disk."""
        path = self.cache_dir / f"{name}.pkl"
        if not path.exists():
            print(f"  [Index] No cached index found at {path}")
            return None

        with open(path, "rb") as f:
            self.store = pickle.load(f)
        print(f"  [Index] Loaded cached index ({self.store.count_documents()} documents)")
        return self.store

    def get_store(self) -> InMemoryDocumentStore:
        """Return the current store, raising if none exists."""
        if self.store is None:
            raise RuntimeError("No index loaded. Call build() or load() first.")
        return self.store

    def clear(self):
        """Clear the in-memory store."""
        if self.store:
            self.store = InMemoryDocumentStore()
            print("  [Index] Cleared in-memory index")
