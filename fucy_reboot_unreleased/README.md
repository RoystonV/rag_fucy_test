# fucy_reboot_unreleased

---

> [!CAUTION]
> ## ⚠️ DO NOT RUN OR EXECUTE THIS CODE
>
> **This module is purely for internal testing and experimentation.**
> It is **NOT production-ready**, **NOT finalised**, and **must NOT be integrated** into any downstream systems or pipelines.
>
> **Developers attempting to integrate this module should stop here.** Wait for an official release.

---

> [!WARNING]
> ## ⚠️ OUTPUTS ARE NOT VERIFIED
>
> All generated outputs (JSON responses, TARA reports, retrieval results, evaluation metrics) produced by this pipeline **have not been reviewed or validated**. They may contain incorrect, incomplete, or hallucinated information. Do **not** use any outputs from this module for any official, production, or regulatory purpose until they have been formally audited.

---

## What This Is

`fucy_reboot_unreleased` is an **experimental prototype** of a Hybrid RAG + CAG (Cache-Augmented Generation) pipeline for automotive TARA (Threat Analysis and Risk Assessment) per ISO/SAE 21434.

It is being developed and tested internally before any production decision is made. The code is intentionally checked in here for review and tracking purposes only.

---

## Architecture (Prototype)

```
User Query
    │
    ▼
[QueryRewriter] → expands abbreviations, adds domain synonyms
    │
    ▼
[HybridRetriever] → BM25 keyword + dense vector search (RRF fusion)
    │
    ▼
[CrossEncoderReranker] → fine-grained (query, doc) pair scoring
    │
    ▼
[ContextAssembler] → relevance filter + MMR dedup + token budget
    │
    ▼
[FucyGenerator] → Gemini call (with optional CAG cache)
    │
    ▼
Validated JSON output
```

**CAG = Cache-Augmented Generation** — static domain data (`dataecu.json`, `annex.json`, ISO clauses) preloaded into Gemini's context cache for zero retrieval latency.

---

## Module Overview

| Module | File | Purpose |
|---|---|---|
| Config | `config.py` | All tunable hyperparameters |
| Ingestion | `ingestion/ingestor.py` | JSON, XML, CAPEC loaders |
| Ingestion | `ingestion/normalizer.py` | Text cleaning & unicode normalisation |
| Chunking | `chunking/chunker.py` | 3 strategies: sentence-window, fixed-overlap, structure-aware |
| Embeddings | `embeddings/embedder.py` | Batched embedding with disk cache |
| Indexing | `indexing/index_manager.py` | Persistent InMemoryDocumentStore |
| Retrieval | `retrieval/retriever.py` | Hybrid BM25 + vector with RRF |
| Retrieval | `retrieval/query_rewriter.py` | LLM query expansion |
| Retrieval | `retrieval/multi_query.py` | Multi-query variant retrieval |
| Re-ranking | `reranking/reranker.py` | Cross-encoder (ms-marco-MiniLM) |
| Context | `context/assembler.py` | MMR dedup, relevance filter, token budget |
| CAG | `cag/cache_builder.py` | Gemini context cache builder |
| CAG | `cag/cache_manager.py` | Cache lifecycle management |
| Generation | `generation/generator.py` | Gemini call + JSON validation + retry |
| Evaluation | `evaluation/evaluator.py` | Precision@k, MRR, coverage metrics |
| Pipeline | `pipeline.py` | Main orchestrator |
| Notebook | `fucy_reboot_pipeline.ipynb` | Step-by-step experimental notebook |

---

## Status

| Area | Status |
|---|---|
| Code | 🟡 Prototype / Under Development |
| Testing | 🔴 Not Tested |
| Output Validation | 🔴 Not Reviewed |
| Integration Readiness | 🔴 Not Ready |
| Production Approval | 🔴 Pending |

---

*Last updated: March 2026 — fucy_reboot internal prototype*
