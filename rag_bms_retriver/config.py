# =============================================================================
# config.py — Central configuration for BMS RAG pipeline
# =============================================================================

import os

# ---------------------------------------------------------------------------
# Google Gemini API key
# Set GOOGLE_API_KEY as an env variable, or replace the fallback string.
# ---------------------------------------------------------------------------
GOOGLE_API_KEY: str = os.environ.get("GOOGLE_API_KEY", "YOUR_KEY_HERE")

# ---------------------------------------------------------------------------
# Embedding model (sentence-transformers)
# ---------------------------------------------------------------------------
EMBED_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Gemini generation model
# ---------------------------------------------------------------------------
GEMINI_MODEL: str = "gemini-2.0-flash"
GENERATION_KWARGS: dict = {"temperature": 0.0}

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
TOP_K: int = 50  # broad queries pull sufficient context

# ---------------------------------------------------------------------------
# Data file paths (relative to project root)
# ---------------------------------------------------------------------------
ITEM_PATH: str = "item_defination.json"
DAMAGE_PATH: str = "Damage_scenarios.json"

# ---------------------------------------------------------------------------
# Fields to strip from nodes / edges (interaction-state booleans only)
# ---------------------------------------------------------------------------
NODE_STRIP: set = {"dragging", "resizing", "selected"}
EDGE_STRIP: set = {"selected"}
