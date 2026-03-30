# =============================================================================
# pipeline.py — Haystack RAG pipeline assembly and run (two-phase context)
# =============================================================================
#
# CONTEXT STRATEGY:
#  - Pinned docs (ECU entry + matching REPORTS_DB chunks) are injected directly.
#  - The semantic retriever only operates on threat-framework docs
#    (MITRE, ATM, CAPEC, CWE, ISO 21434, Annex F) so all top_k slots are
#    used for threat intelligence, not wasted on unrelated ECU entries.
# =============================================================================

from collections import Counter

from haystack.components.builders import PromptBuilder
from haystack.components.embedders import SentenceTransformersTextEmbedder

from components import (
    build_threat_store, build_retriever, build_generator,
    EMBED_MODEL, RETRIEVER_TOP_K,
)
from prompt import TARA_PROMPT_TEMPLATE


def build_pipeline(all_docs: list):
    """
    Build the RAG pipeline using a threat-framework-only document store.
    ECU/REPORTS_DB docs are pinned separately (see build_pinned_docs in components.py).

    Returns:
        text_embedder  — SentenceTransformersTextEmbedder (warmed up)
        retriever      — InMemoryEmbeddingRetriever on threat-only store
        prompt_builder — PromptBuilder with TARA template
        generator      — GoogleAIGeminiGenerator
    """
    # Build threat-only store (MITRE, ATM, CAPEC, CWE, ISO 21434, Annex F)
    threat_store, text_embedder = build_threat_store(all_docs)
    print(f"✅ Embedders ready  [{EMBED_MODEL}]")

    retriever      = build_retriever(threat_store)
    generator      = build_generator()
    prompt_builder = PromptBuilder(
        template=TARA_PROMPT_TEMPLATE,
        required_variables=["documents", "question"],
    )

    print("✅ TARA RAG pipeline built (two-phase: pinned + threat retriever).")
    return text_embedder, retriever, prompt_builder, generator


def run_query(
    text_embedder: SentenceTransformersTextEmbedder,
    retriever,
    prompt_builder: PromptBuilder,
    generator,
    user_query: str,
    enriched_query: str,
    pinned_docs: list,
) -> str:
    """
    Run the two-phase TARA query:
      Phase 1 — pinned_docs are injected directly (ECU entry + REPORTS_DB reference)
      Phase 2 — semantic retrieval on threat-framework store (top_k slots = CWE/CAPEC/MITRE/ATM)
    The two sets are merged (pinned first) before the LLM prompt is built.

    Args:
        text_embedder:  Warmed-up SentenceTransformersTextEmbedder.
        retriever:      InMemoryEmbeddingRetriever on threat-only store.
        prompt_builder: PromptBuilder with TARA template.
        generator:      GoogleAIGeminiGenerator.
        user_query:     Plain query for embedding (accurate retrieval signal).
        enriched_query: Expanded query with asset list — used for the LLM prompt.
        pinned_docs:    Docs guaranteed to be in context (ECU + REPORTS_DB chunks).

    Returns:
        Raw LLM reply string.
    """
    # Phase 1 — embed the plain query
    embedding = text_embedder.run(text=user_query)["embedding"]

    # Phase 2 — retrieve threat-framework docs
    retrieved_docs = retriever.run(query_embedding=embedding)["documents"]

    # Merge: pinned first so they appear at the top of the context block
    all_context = pinned_docs + retrieved_docs

    print(f"\nPinned docs        : {len(pinned_docs)}")
    print(f"  Sources          : {Counter(d.meta.get('source') for d in pinned_docs)}")
    print(f"Retrieved docs     : {len(retrieved_docs)}")
    print(f"  Sources          : {Counter(d.meta.get('source') for d in retrieved_docs)}")
    print(f"Total context docs : {len(all_context)}\n")

    # Build prompt with merged context
    prompt_output = prompt_builder.run(documents=all_context, question=enriched_query)
    prompt_text   = prompt_output["prompt"]

    # Generate
    llm_output = generator.run(parts=prompt_text)
    return llm_output["replies"][0] if llm_output.get("replies") else ""
