# =============================================================================
# ingest.py — Load JSON data, create Documents, embed & store
# =============================================================================

import json
from haystack import Document
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.components.embedders import SentenceTransformersDocumentEmbedder

import config


def _clean_node(node: dict) -> dict:
    """Strip interaction-state keys only; preserve style and all data fields."""
    return {k: v for k, v in node.items() if k not in config.NODE_STRIP}


def _clean_edge(edge: dict) -> dict:
    """Strip interaction-state keys only."""
    return {k: v for k, v in edge.items() if k not in config.EDGE_STRIP}


def build_document_store() -> InMemoryDocumentStore:
    """
    Load both JSON files, create one Document per node/edge/derivation/detail,
    embed all documents, write to an InMemoryDocumentStore, and return it.
    """
    doc_embedder = SentenceTransformersDocumentEmbedder(model=config.EMBED_MODEL)
    doc_embedder.warm_up()

    docs: list[Document] = []

    # -----------------------------------------------------------------------
    # DATASET 1 — item_defination.json
    # Each node → 1 Document  |  Each edge → 1 Document
    # -----------------------------------------------------------------------
    with open(config.ITEM_PATH, "r", encoding="utf-8") as f:
        item_data = json.load(f)

    model_name = item_data["Models"][0]["name"] if item_data.get("Models") else "unknown"
    model_id   = item_data["Models"][0]["_id"]  if item_data.get("Models") else None

    item_start = len(docs)
    for asset in item_data.get("Assets", []):
        asset_id = asset.get("_id")
        template = asset.get("template", {})

        for node in template.get("nodes", []):
            cn = _clean_node(node)
            docs.append(Document(
                content=json.dumps(cn, ensure_ascii=False),
                meta={
                    "source":     "item_definition",
                    "type":       "node",
                    "model_name": model_name,
                    "model_id":   model_id,
                    "asset_id":   asset_id,
                    "node_id":    node.get("id"),
                    "node_label": node.get("data", {}).get("label", ""),
                },
            ))

        for edge in template.get("edges", []):
            ce = _clean_edge(edge)
            docs.append(Document(
                content=json.dumps(ce, ensure_ascii=False),
                meta={
                    "source":      "item_definition",
                    "type":        "edge",
                    "model_id":    model_id,
                    "asset_id":    asset_id,
                    "edge_id":     edge.get("id"),
                    "source_node": edge.get("source"),
                    "target_node": edge.get("target"),
                },
            ))

    print(f"Item Definition  -> {len(docs) - item_start} docs (nodes + edges)")

    # -----------------------------------------------------------------------
    # DATASET 2 — Damage_scenarios.json
    # Each Derivation → 1 Document  |  Each Detail → 1 Document
    # -----------------------------------------------------------------------
    with open(config.DAMAGE_PATH, "r", encoding="utf-8") as f:
        damage_data = json.load(f)

    damage_start = len(docs)
    for ds in damage_data.get("Damage_scenarios", []):
        ds_type  = ds.get("type", "")
        ds_id    = ds.get("_id")
        ds_model = ds.get("model_id")

        for deriv in ds.get("Derivations", []):
            docs.append(Document(
                content=json.dumps(deriv, ensure_ascii=False),
                meta={
                    "source":    "damage_scenarios",
                    "type":      "derivation",
                    "ds_type":   ds_type,
                    "ds_id":     ds_id,
                    "model_id":  ds_model,
                    "ds_id_ref": deriv.get("id"),
                    "node_id":   deriv.get("nodeId"),
                },
            ))

        for detail in ds.get("Details", []) or []:
            docs.append(Document(
                content=json.dumps(detail, ensure_ascii=False),
                meta={
                    "source":   "damage_scenarios",
                    "type":     "detail",
                    "ds_type":  ds_type,
                    "ds_id":    ds_id,
                    "model_id": ds_model,
                    "node_id":  detail.get("nodeId"),
                    "name":     detail.get("Name") or detail.get("name"),
                },
            ))

    print(f"Damage Scenarios -> {len(docs) - damage_start} docs (derivations + details)")
    print(f"Total            -> {len(docs)} documents")

    # -----------------------------------------------------------------------
    # Embed all documents and write to store
    # -----------------------------------------------------------------------
    document_store = InMemoryDocumentStore()
    embedded_docs = doc_embedder.run(documents=docs)["documents"]
    document_store.write_documents(embedded_docs)
    print(f"All {len(embedded_docs)} documents embedded and stored.")

    return document_store
