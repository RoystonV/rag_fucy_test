# BMS RAG — Battery Management System TARA Knowledge Base

A **Retrieval-Augmented Generation (RAG)** chatbot that answers natural language queries about a BMS (Battery Management System) TARA (Threat Analysis and Risk Assessment) dataset.

Built with [Haystack](https://haystack.deepset.ai/) + [Google Gemini](https://ai.google.dev/) + [Sentence Transformers](https://www.sbert.net/).

---

## How It Works

```
Your Query
   │
   ▼
SentenceTransformers Embedder   ←── item_defination.json
   │                            ←── Damage_scenarios.json
   ▼
InMemory Retriever (top_k=50)
   │
   ▼
Prompt Builder (Jinja2 template)
   │
   ▼
Gemini 2.0 Flash
   │
   ▼
Structured JSON Response
```

---

## Project Structure

```
rag_fucy_test/
├── config.py               # API key, model names, file paths
├── ingest.py               # Load JSON files → embed → store
├── pipeline.py             # Build Haystack RAG pipeline
├── query.py                # ask() — run a query, parse response
├── main.py                 # Entry point — interactive chatbot
├── item_defination.json    # Asset/node/edge data
├── Damage_scenarios.json   # Damage scenario data
├── BMS_rag.ipynb           # Original notebook (reference)
└── requirements.txt        # Python dependencies
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your Google Gemini API key

**Option A** — Edit `config.py`:
```python
GOOGLE_API_KEY = "your-api-key-here"
```

**Option B** — Environment variable (recommended):
```powershell
# PowerShell
$env:GOOGLE_API_KEY = "your-api-key-here"

# CMD
set GOOGLE_API_KEY=your-api-key-here
```

### 3. Run
```bash
python main.py
```

---

## Example Queries

```
give me all damage scenarios assets and properties
what edges are connected to CellMonitoring
show all cyber loss properties for every node
list all derivations related to loss of integrity
full report on BatteryPack
everything
```

---

## Output Format

Every response is a structured JSON object:

```json
{
  "result": {
    "query_intent": "User wants all damage scenarios and asset properties",
    "assets": [ ... ],
    "edges": [ ... ],
    "damage_scenarios": [ ... ],
    "damage_details": [ ... ]
  }
}
```

---

## Requirements

| Package | Version |
|---------|---------|
| `haystack-ai` | latest |
| `sentence-transformers` | ≥ 2.2.0 |
| `google-ai-haystack` | latest |