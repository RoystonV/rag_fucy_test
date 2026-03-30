# TARA RAG Visualizer — `rag_front_test`

Interactive web frontend for the **TARA RAG Pipeline**. Generates ISO/SAE 21434-compliant Threat Analysis & Risk Assessment (TARA) reports for automotive ECUs and visualizes them in a dark-mode dashboard with an interactive graph.

---

## Folder Structure

```
rag_front_test/
├── frontend/
│   ├── index.html        ← Single-page app (UI)
│   ├── style.css         ← Dark-mode stylesheet
│   ├── app.js            ← Report list, detail panels, stats
│   ├── graph.js          ← Interactive architecture graph renderer
│   ├── server.py         ← Flask API server (run this to start)
│   └── seed_mongo.py     ← One-time script: load existing TARA JSONs into MongoDB
│
└── rag_tara_gen/         ← Copy of the TARA RAG pipeline
    ├── main.py           ← CLI: generate new TARA reports
    ├── db.py             ← MongoDB save/load helpers
    ├── datasets/         ← All knowledge bases (CWE, CAPEC, MITRE, ISO 21434 …)
    └── outputs/tara/     ← Generated TARA JSON files
```

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | ≥ 3.10 | `python --version` |
| MongoDB | ≥ 6.0 | Must be running locally on port 27017 |
| Google API Key | — | For Gemini LLM (only needed to generate new reports) |

---

## Quick Start

### Step 1 — Install Python dependencies

```powershell
pip install flask flask-cors pymongo
```

For generating **new** TARA reports (optional), also install the pipeline dependencies:

```powershell
pip install haystack-ai "sentence-transformers>=2.2.0" google-ai-haystack lxml
```

---

### Step 2 — Start MongoDB

Make sure `mongod` is running. On Windows:

```powershell
# If installed as a service, it may already be running.
# Otherwise start manually:
mongod --dbpath "C:\data\db"
```

Verify with:
```powershell
mongosh --eval "db.adminCommand('ping')"
```

The app uses:
- **URI**: `mongodb://localhost:27017` (override with `MONGO_URI` env var)
- **Database**: `tara_db`
- **Collection**: `reports`

---

### Step 3 — Seed MongoDB with existing reports

Run this **once** from the `frontend/` directory to load the pre-generated TARA JSONs into MongoDB:

```powershell
cd rag_front_test\frontend
python seed_mongo.py
```

Expected output:
```
🌱 Seeding MongoDB with 5 reports...

  ✅ tara_output_ABS.json              → ABS
  ✅ tara_output_BMS.json              → BMS
  ✅ tara_output_Battery_Management_System_ECU.json → Battery Management System ECU
  ✅ tara_output_Infotainment_Head_Unit.json → Infotainment Head Unit
  ✅ tara_output_Infotainment_System_ECU.json → Infotainment System ECU

🍃 MongoDB now has 5 reports in tara_db.reports
```

---

### Step 4 — Start the Flask server

```powershell
cd rag_front_test\frontend
python server.py
```

Then open your browser at:

```
http://localhost:5000
```

---

## Generating New Reports

To generate a new TARA report and have it automatically saved to MongoDB:

```powershell
# Set your Google API key
$env:GOOGLE_API_KEY = "your-key-here"

# Run from the pipeline folder
cd rag_front_test\rag_tara_gen
python main.py --query "Gateway ECU"
```

The output JSON is saved to `rag_tara_gen/outputs/tara/`. Then re-run `seed_mongo.py` to load it into the visualizer, or the pipeline will upsert it into MongoDB automatically if `db.py` is configured.

List all 50 supported ECU systems:
```powershell
python main.py --list-ecus
```

---

## API Endpoints

The Flask server exposes these REST endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the frontend (index.html) |
| `GET` | `/api/status` | MongoDB connection status |
| `GET` | `/api/reports` | List all saved TARA reports (summary) |
| `GET` | `/api/report/<id>` | Full TARA report JSON by MongoDB ID |
| `DELETE` | `/api/report/<id>` | Delete a report by MongoDB ID |
| `GET` | `/api/ecus` | List all ECU entries from `dataecu.json` |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `PORT` | `5000` | Flask server port |
| `GOOGLE_API_KEY` | *(required for generation)* | Gemini API key |

Set in PowerShell:
```powershell
$env:MONGO_URI = "mongodb://localhost:27017"
$env:PORT = "5000"
$env:GOOGLE_API_KEY = "your-key-here"
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `❌ Flask not installed` | `pip install flask flask-cors pymongo` |
| `⚠️ MongoDB not reachable` | Start `mongod` and check it's on port 27017 |
| `❌ No tara_output_*.json files found` | Run the pipeline first: `python main.py --query "..."` |
| `GOOGLE_API_KEY not set` | `$env:GOOGLE_API_KEY = "your-key"` (only needed for generation) |
| Browser shows empty report list | Run `seed_mongo.py` to populate the database |
| Port 5000 already in use | `$env:PORT = "8080"` then `python server.py` |

---

## Related

- [`rag_tara_gen/README.md`](rag_tara_gen/README.md) — Full documentation for the pipeline (datasets, architecture, CLI options, output JSON schema)
- ISO/SAE 21434 — Automotive cybersecurity standard this pipeline implements
