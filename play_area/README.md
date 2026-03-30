# play_area — Sandbox for TARA Pipeline Experiments

> ⚠️ **This folder is a SANDBOX COPY of `rag_tara_gen`.**
> All experiments, changes, and tests should be done here.
> The original `rag_tara_gen/` files are **not affected**.

---

## What is this?

`play_area/` is an isolated copy of the full TARA RAG pipeline created for safe experimentation — testing prompt changes, ingest tweaks, new ECU entries, dataset modifications, or pipeline behaviour — without risking the production pipeline in `rag_tara_gen/`.

```
play_area/
└── rag_tara_gen/     ← full copy of the production pipeline
    ├── main.py
    ├── components.py
    ├── ingest.py
    ├── prompt.py
    ├── pipeline.py
    ├── postprocess.py
    ├── datasets/
    │   ├── dataecu.json
    │   ├── reports_db/   ← bms_1.json, infotainment_2.json, abs_1.json
    │   └── ...
    └── outputs/          ← experiment outputs land here
```

---

## Current Experiment: BMS Full Reference Architecture

**Goal:** Test what the LLM prompt looks like when the full `bms_1.json` reference
architecture is pinned into context, and how closely the generated output follows it.

### Run

```powershell
$env:GOOGLE_API_KEY = "your-key-here"
cd play_area\rag_tara_gen
python main.py --query "Battery Management System ECU"
```

Outputs:
- `outputs/tara/tara_output_Battery_Management_System_ECU.json` — generated TARA
- `outputs/prompts/tara_prompt_Battery_Management_System_ECU.txt` — full prompt sent to LLM

---

## Rules

- ✅ Make changes freely here
- ✅ Run queries and inspect outputs
- ❌ Do NOT copy changes back to `rag_tara_gen/` unless tested and confirmed
- ❌ Do NOT commit `play_area/outputs/` (generated files)
