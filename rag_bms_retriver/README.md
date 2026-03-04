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
Gemini (gemini-2.5-flash-lite)
   │
   ▼
Structured JSON Response
   │
   ▼
Auto-saved to output/  (+ download button in notebook)
```

---

## Project Structure

```
rag_fucy_test/
├── config.py               # API key, model names, file paths
├── ingest.py               # Load JSON files → embed → store
├── pipeline.py             # Build Haystack RAG pipeline
├── query.py                # ask() — run a query, parse & save response
├── main.py                 # Entry point — interactive chatbot (CLI)
├── BMS_rag.ipynb           # Self-contained Jupyter notebook version
├── item_defination.json    # Asset/node/edge data
├── Damage_scenarios.json   # Damage scenario data
├── output/                 # Auto-created — exported JSON query results
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

## CLI Options (`main.py`)

| Flag | Default | Description |
|---|---|---|
| *(none)* | — | Saves JSON to `./output/` after every query |
| `--output-dir DIR` | `output` | Save JSON files to a custom folder |
| `--no-save` | — | Disable automatic JSON export |

```bash
# Save to a custom folder
python main.py --output-dir exports

# Disable saving
python main.py --no-save
```

---

## JSON Export

Every successful query **automatically exports** a formatted JSON file.

### CLI (`main.py` / `query.py`)
Files are saved to `output/` (or the folder set by `--output-dir`) with a timestamped, query-derived filename:
```
output/rag_give_me_all_damage_scenarios_20260227_104500.json
```
The full path is printed in the terminal after each query:
```
  [Saved] C:\...\rag_fucy_test\output\rag_give_me_all_damage_scenarios_20260227_104500.json
```

### Notebook (`BMS_rag.ipynb`)
A **clickable blue download button** appears in the cell output after every successful query. Clicking it triggers a direct browser download of the JSON result — no extra libraries required.

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
    "assets": [ "..." ],
    "edges": [ "..." ],
    "damage_scenarios": [ "..." ],
    "damage_details": [ "..." ]
  }
}
```

Sections are included only when relevant to the query.

---

## Requirements

| Package | Version |
|---------|---------|
| `haystack-ai` | latest |
| `sentence-transformers` | ≥ 2.2.0 |
| `google-ai-haystack` | latest |
