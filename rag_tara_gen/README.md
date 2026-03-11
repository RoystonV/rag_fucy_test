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
        │      • REPORTS_DB (reference TARA reports)
        │
        └─ Gemini LLM
             Prompt = enriched query (hint as asset constraint)
                    + retrieved context (REPORTS_DB tagged as pattern-only)
             Output = ISO 21434-compliant TARA JSON
```

---

## Output JSON Structure

```json
{
  "assets": {
    "_id": "<uuid>",
    "model_id": "<uuid>",
    "template": {
      "nodes": [
        {
          "id": "<uuid>",
          "type": "default",
          "isAsset": true,
          "data": { "label": "Battery Management MCU", "description": "..." },
          "properties": ["Integrity", "Confidentiality", "Availability"],
          "position": { "x": 0, "y": 0 },
          "positionAbsolute": { "x": 0, "y": 0 }
        }
      ],
      "edges": [
        {
          "id": "<uuid>",
          "source": "<node-id>",
          "target": "<node-id>",
          "type": "step",
          "animated": true,
          "markerEnd": { "color": "#64B5F6", "type": "arrowclosed" },
          "properties": ["Integrity"]
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
        "asset": "CAN/vehicle network messages",
        "loss": "Integrity",
        "damage_scene": "Unauthorized command injection"
      }
    ],
    "Details": [
      {
        "_id": "<uuid>",
        "Name": "CAN Bus Attack",
        "Description": "Attacker replays CAN frames to inject malicious commands...",
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

---

## Supported Systems (`dataecu.json`)

50 automotive ECU/system entries with curated asset hint lists:

| Key | System | Example Assets |
|-----|--------|---------------|
| `bms` | Battery Management System | MCU, CAN messages, HSM, Firmware, Cell monitoring |
| `infotainment` | Infotainment Head Unit | Head unit OS, Bluetooth/Wi-Fi, USB, Navigation, PII |
| `gateway` | Gateway / Domain Controller | Routing tables, Firewall rules, OTA gateway |
| `adas` | ADAS ECU | Perception software, Neural networks, V2X, OTA |
| `tcu` | Telematics Control Unit | Modem, SIM/eSIM, Cloud APIs, OTA client |
| `bcm` | Body Control Module | Firmware, RKE logic, Immobilizer keys |
| `obd` | OBD-II Diagnostic Port | UDS services, Seed-Key, Tool authentication |
| `eps` | Electric Power Steering | MCU, CAN, Safety watchdog, Calibration |
| ... | *(43 more)* | |

---

## Setup (Google Colab)

### 1. Install dependencies (Cell 1)
```bash
pip install haystack-ai sentence-transformers google-ai-haystack lxml
```

### 2. Set API key
```python
import os
os.environ["GOOGLE_API_KEY"] = "your-key-here"
# or use Colab Secrets panel
```

### 3. Set your query (Cell 13)
```python
user_query = "Battery Management System ECU"
# Other examples:
#   "Infotainment Head Unit"
#   "Gateway / Domain Controller"
#   "ADAS ECU"
#   "Telematics Control Unit"
#   "OBD-II Diagnostic Port"
```

### 4. Run all cells top to bottom

Output is saved as `tara_output_<system_name>.json`.

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

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `patch_tara_all.py` | Apply all 6 patches to the notebook |
| `patch_resolve_ecu_final.py` | Re-patch the `resolve_ecu()` function only |
| `verify_queries.py` | Test `resolve_ecu()` matching against 12 queries |

---

## Key Design Decisions

- **`resolve_ecu()` uses 5-pass fuzzy matching** — exact key → full name → acronym (with suffix stripping) → word overlap → partial match — plus an alias table for known abbreviations (BMS, TCU, OBD, etc.)
- **REPORTS_DB chunks are tagged `[REFERENCE-PATTERN-ONLY]`** in the prompt so Gemini uses them for JSON structure only, never copying node names across systems
- **Embedding uses plain query; LLM receives enriched query** — so retrieval stays accurate while the generation is constrained to the dataecu.json asset list
- **UUID stamping post-processing** — all `id`/`_id`/`model_id` fields are guaranteed valid `uuid4` after generation; `Derivations[].nodeId` is crosslinked by asset label matching
