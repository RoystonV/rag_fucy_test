# =============================================================================
# chunker.py — Semantic chunking with multiple strategies
# =============================================================================

import json
import re
from typing import Any

from ingestion.normalizer import normalize_text


# ---------------------------------------------------------------------------
# Sentence splitter helper
# ---------------------------------------------------------------------------

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex heuristic."""
    parts = _SENTENCE_RE.split(text)
    return [s.strip() for s in parts if s.strip()]


# ---------------------------------------------------------------------------
# Chunking strategies
# ---------------------------------------------------------------------------

class SemanticChunker:
    """
    Chunks text using one of three strategies:

    1. sentence_window — groups N sentences per chunk with overlap
    2. fixed_overlap   — fixed character-count windows with stride
    3. structure_aware  — preserves JSON key groupings together

    Each chunk carries full provenance metadata from its parent record.
    """

    def __init__(
        self,
        strategy: str = "sentence_window",
        chunk_size: int = 300,
        chunk_overlap: int = 50,
        sentences_per_chunk: int = 5,
    ):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.sentences_per_chunk = sentences_per_chunk

    def chunk(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Chunk a list of {content, meta} records into smaller pieces.
        Returns a new list of {content, meta} with added chunk metadata.
        """
        all_chunks: list[dict[str, Any]] = []

        for record in records:
            content = normalize_text(record["content"], aggressive=True)
            meta = record.get("meta", {})

            if self.strategy == "sentence_window":
                chunks = self._sentence_window(content)
            elif self.strategy == "fixed_overlap":
                chunks = self._fixed_overlap(content)
            elif self.strategy == "structure_aware":
                chunks = self._structure_aware(content)
            else:
                chunks = self._sentence_window(content)

            for i, chunk_text in enumerate(chunks):
                chunk_meta = {**meta, "chunk_index": i, "chunk_strategy": self.strategy}
                all_chunks.append({"content": chunk_text, "meta": chunk_meta})

        return all_chunks

    def _sentence_window(self, text: str) -> list[str]:
        """Group N sentences with overlap."""
        sentences = _split_sentences(text)
        if not sentences:
            return [text] if text.strip() else []

        n = self.sentences_per_chunk
        overlap = max(1, n // 3)  # overlap ~1/3 of window
        chunks = []

        i = 0
        while i < len(sentences):
            window = sentences[i : i + n]
            chunks.append(" ".join(window))
            i += n - overlap

        return chunks

    def _fixed_overlap(self, text: str) -> list[str]:
        """Fixed character-count sliding window."""
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # Try to break at a word boundary
            if end < len(text):
                last_space = chunk.rfind(" ")
                if last_space > self.chunk_size // 2:
                    chunk = chunk[:last_space]
                    end = start + last_space

            chunks.append(chunk.strip())
            start = end - self.chunk_overlap

        return [c for c in chunks if c]

    def _structure_aware(self, text: str) -> list[str]:
        """
        For JSON content: keep top-level key groups together as chunks.
        Falls back to sentence_window for non-JSON.
        """
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return self._sentence_window(text)

        chunks = []
        if isinstance(data, dict):
            for key, value in data.items():
                entry = json.dumps({key: value}, ensure_ascii=False)
                if len(entry) > self.chunk_size:
                    # Sub-chunk large values
                    sub_chunks = self._fixed_overlap(entry)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(entry)
        elif isinstance(data, list):
            for item in data:
                entry = json.dumps(item, ensure_ascii=False)
                if len(entry) > self.chunk_size:
                    sub_chunks = self._fixed_overlap(entry)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(entry)
        else:
            chunks.append(text)

        return [c for c in chunks if c.strip()]
