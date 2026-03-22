# TARA RAG Pipeline — `rag_tara_gen`

Automated **Threat Analysis and Risk Assessment (TARA)** report generator for automotive ECUs, compliant with **ISO/SAE 21434 Clause 15**.

Built with [Haystack](https://haystack.deepset.ai/) + [Google Gemini](https://ai.google.dev/) and a semantic RAG pipeline over automotive threat databases.

---

## How It Works

```
user_query ("Battery Management System ECU")
        │
        ├─ resolve_ecu()  ──► dataecu.json
        │    Fuzzy-match query to one of 50 ECU entries.
        │    Returns authoritative asset list (hint field).
        │
        ├─ text_embedder  ──► BAAI/bge-small-en-v1.5
        │    Embeds plain query for semantic retrieval.
        │
        ├─ retriever (top_k=20)  ──► InMemoryDocumentStore
        │    Retrieves relevant chunks from:
        │      • MITRE ATT&CK (Mobile + ICS)
        │      • Automotive Threat Matrix (ATM)
        │      • CAPEC attack patterns
        │      • CWE weaknesses
        │      • ISO 21434 clauses (5, 6, 8, 9, 10, 11, 15)
        │      • Annex F (impact rating guidelines)
        │      • REPORTS_DB (reference TARA reports + hierarchy/edge summaries)
        │
        └─ Gemini LLM (gemini-2.5-flash-lite)
             Prompt = enriched query (hint as asset constraint)
                    + retrieved context (with architecture rules)
             Output = ISO 21434-compliant TARA JSON with hierarchy
```

---

## Module Structure

| File | Role |
|------|------|
| `main.py` | CLI entry point — runs the full pipeline |
| `config.py` | All paths, model names, and tunable constants |
| `components.py` | ECU resolution, UUID post-processing, Haystack builders |
| `ingest.py` | Loads and chunks all datasets into Haystack Documents |
| `prompt.py` | Jinja2 prompt template sent to the LLM |
| `pipeline.py` | Assembles and runs the Haystack RAG pipeline |
| `postprocess.py` | UUID stamping, crosslinking, JSON parsing helpers |
| `resolve_ecu.py` | Standalone ECU fuzzy matcher + `list_ecus()` utility |

---

## Setup & Usage

### 1. Install dependencies
```bash
pip install haystack-ai "sentence-transformers>=2.2.0" google-ai-haystack lxml
```

### 2. Set your Google API key
```powershell
# Windows PowerShell
$env:GOOGLE_API_KEY = "your-key-here"

# Linux / macOS
export GOOGLE_API_KEY="your-key-here"
```

### 3. Run from the terminal
```bash
cd rag_tara_gen

# Generate a TARA report
python main.py --query "Battery Management System ECU"

# Custom output filename
python main.py --query "Infotainment Head Unit" --output infotainment_tara.json

# Print JSON to console only (no file saved)
python main.py --query "ADAS ECU" --no-save

# List all 50 supported ECU keys
python main.py --list-ecus
```

Output is saved as `tara_output_<system_name>.json` in the `rag_tara_gen/` folder.

### Notebook (Google Colab)
Open `Tara_expo_v3_0.ipynb` in Colab, run cells top to bottom, and set your query in **Cell 13**.

---

## Output JSON Structure

The output uses a **hierarchical node architecture** with three node types:

```json
{
  "assets": {
    "_id": "<uuid>",
    "model_id": "<uuid>",
    "template": {
      "nodes": [
        {
          "id": "<uuid>",
          "type": "group",
          "parentId": null,
          "data": { "label": "Battery Management System", "nodeCount": 7 },
          "properties": ["Integrity", "Authenticity"],
          "zIndex": 0
        },
        {
          "id": "<uuid>",
          "type": "default",
          "parentId": "<group-uuid>",
          "isAsset": false,
          "data": {
            "label": "CellMonitoring",
            "description": "...",
            "style": { "backgroundColor": "#e6df19" }
          },
          "properties": ["Integrity", "Availability"]
        },
        {
          "id": "<uuid>",
          "type": "data",
          "parentId": "<group-uuid>",
          "isAsset": false,
          "data": { "label": "SoC", "style": { "backgroundColor": "#e3e896" } },
          "properties": ["Authenticity", "Integrity"]
        }
      ],
      "edges": [
        {
          "id": "<uuid>",
          "source": "<node-id>",
          "target": "<node-id>",
          "type": "step",
          "animated": true,
          "properties": ["Integrity"],
          "data": { "label": "SPI_CellMonitor" }
        }
      ]
    }
  },
  "damage_scenarios": {
    "_id": "<uuid>",
    "type": "damage",
    "Derivations": [
      {
        "id": "<uuid>",
        "nodeId": "<linked-node-uuid>",
        "name": "CAN Bus Spoofing",
        "asset": "CAN Transceiver",
        "loss": "Integrity",
        "damage_scene": "Unauthorized command injection"
      }
    ],
    "Details": [
      {
        "_id": "<uuid>",
        "Name": "CAN Bus Attack",
        "Description": "Attacker replays CAN frames...",
        "cyberLosses": [{ "id": "<uuid>", "name": "Integrity", "node": "CAN Transceiver", "nodeId": "<uuid>" }],
        "impacts": {
          "Safety Impact": "Major",
          "Financial Impact": "Moderate",
          "Operational Impact": "Major",
          "Privacy Impact": "Negligible"
        }
      }
    ]
  }
}
```

### Node Types

| Type | Purpose | Example |
|------|---------|---------|
| `group` | Invisible container for hierarchy | Battery Management System, MCU subgroup |
| `default` | Visible component node | CellMonitoring, Code Flash, CAN Transceiver |
| `data` | Small circular data item | SoC, SoH |

---

## Supported Systems (`dataecu.json`)

50 automotive ECU/system entries with curated asset hint lists:

| Key | System | Example Assets |
|-----|--------|---------------|
| `bms` | Battery Management System | CellMonitoring, IO and Analog, Code Flash, Keys, Certificates, Debug Port, CAN Transceiver, ICD Shunt CAN, SoC, SoH |
| `infotainment` | Infotainment Head Unit | Head unit OS, Bluetooth/Wi-Fi, USB, Navigation, PII |
| `gateway` | Gateway / Domain Controller | Routing tables, Firewall rules, OTA gateway |
| `adas` | ADAS ECU | Perception software, Neural networks, V2X, OTA |
| `tcu` | Telematics Control Unit | Modem, SIM/eSIM, Cloud APIs, OTA client |
| `bcm` | Body Control Module | Firmware, RKE logic, Immobilizer keys |
| `obd` | OBD-II Diagnostic Port | UDS services, Seed-Key, Tool authentication |
| `eps` | Electric Power Steering | MCU, CAN, Safety watchdog, Calibration |
| ... | *(43 more)* | |

---

## Datasets (`datasets/`)

| File / Folder | Source | Size |
|--------------|--------|------|
| `mobileattack.json` | MITRE ATT&CK Mobile | 4.4 MB |
| `icsattack.json` | MITRE ATT&CK ICS | 3.1 MB |
| `atm.json` | Automotive Threat Matrix | 289 KB |
| `capec.xml` | CAPEC v3 | 3.8 MB |
| `cwec.xml` | CWE v4 | 16 MB |
| `dataecu.json` | ECU asset definitions (50 systems) | 10 KB |
| `annex.json` | ISO 21434 Annex F impact tables | 5.5 KB |
| `clauses/` | ISO 21434 Clauses 5, 6, 8–11, 15 | 7 JSON files |
| `reports_db/` | Reference TARA reports (BMS, Infotainment) | ~1 MB |

---

## Key Design Decisions

- **`resolve_ecu()` — 6-pass fuzzy matching**: alias table → exact key → full name substring → acronym (suffix-stripped) → word overlap → partial key match. Constrains the LLM to a curated asset list, preventing hallucination.
- **Split query**: plain query used for embedding (accurate retrieval); enriched query (with asset list) sent to LLM (constrained generation).
- **Hierarchical architecture generation**: prompt template teaches the LLM three node types (`group`, `default`, `data`) with `parentId` hierarchy, so generated architectures match reference report structures.
- **Structural ingestion**: `ingest.py` generates per-report hierarchy summaries and edge summaries alongside per-node chunks, giving the retriever full architectural context.
- **Short edge labels**: prompt enforces protocol/interface names (SPI, CAN1, IO_PINS) instead of descriptive phrases.
- **Color-coded components**: prompt specifies distinct `backgroundColor` values per component role (monitoring=yellow, security=green, debug=red, etc.).
- **UUID post-processing**: `stamp_uuids()` + `crosslink_node_ids()` guarantee all IDs are valid `uuid4` and all `Derivations[].nodeId` / `cyberLosses[].nodeId` are correctly cross-referenced.
- **Section-level ISO 21434 chunking**: each clause section is a separate Document, enabling precise sub-clause retrieval instead of broad clause-level noise.

---

## Changelog

### v2.1 — Architecture Accuracy Improvements (2026-03-22)

- **`dataecu.json`**: Updated BMS hint with exact component names, hierarchy (MCU group container), node types, and 9 named edge connections from the reference `bms_1.json`.
- **`prompt.py`**: Rewrote prompt template with:
  - ARCHITECTURE RULES section (group/default/data node types, parentId hierarchy)
  - Three node examples in JSON schema (group, default, data) instead of one
  - Edge label guidance (short protocol names, not descriptive phrases)
  - Color coding instructions per component role
  - REPORTS_DB matching instruction (follow reference when target matches)
- **`ingest.py`**: Added hierarchy_summary and edge_summary chunk types per reference report for structural context retrieval.
- **Notebooks**: Both `Tara_expo_v2.0.ipynb` and `Tara_expo_v3_0.ipynb` updated with matching prompt template.
- **`prompt.py`**: Removed `[REFERENCE-PATTERN-ONLY]` Jinja conditional tag from prompt template.

