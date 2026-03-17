# =============================================================================
# config.py — Central configuration for TARA RAG pipeline
# =============================================================================

from pathlib import Path

# ---------------------------------------------------------------------------
# Base dataset directory (relative to this file's location)
# ---------------------------------------------------------------------------
BASE_PATH    = Path(__file__).parent / "datasets"

MITRE_MOBILE = BASE_PATH / "mobileattack.json"
MITRE_ICS    = BASE_PATH / "icsattack.json"
ATM_PATH     = BASE_PATH / "atm.json"
CAPEC_PATH   = BASE_PATH / "capec.xml"
CWE_PATH     = BASE_PATH / "cwec.xml"
ECU_PATH     = BASE_PATH / "dataecu.json"
ANNEX_PATH   = BASE_PATH / "annex.json"
CLAUSE_PATH  = BASE_PATH / "clauses"
REPORTS_PATH = BASE_PATH / "reports_db"

# ---------------------------------------------------------------------------
# Embedding model
# BGE-small beats MiniLM on BEIR benchmarks at same size
# ---------------------------------------------------------------------------
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
# Fallback: "sentence-transformers/all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
MAX_CHARS = 1500   # max chars per chunk for threat-framework entries

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
GEMINI_MODEL = "gemini-2.5-flash-lite"

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
RETRIEVER_TOP_K = 20
