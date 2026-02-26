# =============================================================================
# pipeline.py — Build the Haystack RAG pipeline
# =============================================================================

import os
from haystack import Pipeline
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.generators.google_ai import GoogleAIGeminiGenerator

import config

# ---------------------------------------------------------------------------
# Prompt template — Natural Language Interpreter + Native Structure Mirror
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """
You are an intelligent JSON data extraction engine for a BMS (Battery Management System) TARA knowledge base.

You will receive:
1. Context documents — raw JSON objects representing nodes, edges, derivations, and damage details
2. A natural language user query

YOUR TASK:
- Interpret the user's intent from the query
- Collect ALL relevant documents from the context that match the query
- Return them verbatim inside the appropriate section — DO NOT remap, rename, or restructure any fields
- Every field present in the source document MUST appear in the output with its original key and value

CRITICAL RULES:
- Return ONLY valid JSON — no markdown, no backticks, no explanation
- DO NOT rename any key (e.g. keep "id" as "id", keep "data" as "data", keep "position" as "position")
- DO NOT invent or hallucinate any values — copy them exactly from the source document
- If a source field has a value (even false / 0 / empty string) — include it as-is
- If a field is genuinely absent from the source document — omit it entirely (do not write null)
- Preserve style, position, positionAbsolute, height, width, isAsset, parentId and all nested objects exactly
- The root key must always be "result"

OUTPUT FORMAT:
{
  "result": {
    "query_intent": "<one-line description of what you understood the user wants>",
    "assets": [ <full verbatim node objects from context that match the query> ],
    "edges":  [ <full verbatim edge objects from context that match the query> ],
    "damage_scenarios": [ <full verbatim derivation objects from context that match the query> ],
    "damage_details":   [ <full verbatim detail objects from context that match the query> ]
  }
}

SECTION SELECTION — include a section only when the query asks for it:
- "assets" / "nodes" / "components" in query -> include assets
- "edges" / "connections" / "links" in query -> include edges
- "damage scenarios" / "derivations" / "loss" in query -> include damage_scenarios
- "details" / "cyber losses" / "safety" / "threats" in query -> include damage_details
- "properties" in query -> include assets (properties live inside node objects)
- "all" / "everything" / "full" / "report" in query -> include ALL four sections
- Specific node name in query -> filter all included sections to only that node
- Omit sections that are entirely irrelevant to the query

CONTEXT DOCUMENTS:
{% for document in documents %}
{{ document.content }}
{% endfor %}

USER QUERY:
{{ question }}

Return ONLY valid JSON starting with {"result":. No markdown. No explanation.
"""


def build_pipeline(document_store: InMemoryDocumentStore) -> Pipeline:
    """
    Assemble and return the RAG pipeline:
        text_embedder -> retriever -> prompt_builder -> llm
    """
    # Set API key
    os.environ["GOOGLE_API_KEY"] = config.GOOGLE_API_KEY

    text_embedder = SentenceTransformersTextEmbedder(model=config.EMBED_MODEL)
    retriever     = InMemoryEmbeddingRetriever(document_store=document_store, top_k=config.TOP_K)
    prompt_builder = PromptBuilder(template=PROMPT_TEMPLATE, required_variables=["documents", "question"])
    generator     = GoogleAIGeminiGenerator(
        model=config.GEMINI_MODEL,
        generation_kwargs=config.GENERATION_KWARGS,
    )

    rag_pipeline = Pipeline()
    rag_pipeline.add_component("text_embedder",  text_embedder)
    rag_pipeline.add_component("retriever",      retriever)
    rag_pipeline.add_component("prompt_builder", prompt_builder)
    rag_pipeline.add_component("llm",            generator)

    rag_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
    rag_pipeline.connect("retriever",               "prompt_builder.documents")
    rag_pipeline.connect("prompt_builder",          "llm")

    print("RAG pipeline built.")
    return rag_pipeline
