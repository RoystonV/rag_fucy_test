# =============================================================================
# ingestor.py — Multi-format document ingestion
# =============================================================================

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def load_json_file(path: str) -> dict | list:
    """Load a JSON file and return parsed content."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_json_flat(path: str, source_tag: str = "") -> list[dict[str, Any]]:
    """
    Load a flat or nested JSON file and return a list of
    {content: str, meta: dict} records — one per top-level entry.
    """
    data = load_json_file(path)
    source = source_tag or Path(path).stem
    records: list[dict[str, Any]] = []

    if isinstance(data, dict):
        for key, value in data.items():
            records.append({
                "content": json.dumps(value, ensure_ascii=False),
                "meta": {"source": source, "key": key, "file": Path(path).name},
            })
    elif isinstance(data, list):
        for i, item in enumerate(data):
            records.append({
                "content": json.dumps(item, ensure_ascii=False),
                "meta": {"source": source, "index": i, "file": Path(path).name},
            })
    return records


def load_dataecu(path: str) -> list[dict[str, Any]]:
    """Load dataecu.json — one record per ECU entry with structured content."""
    data = load_json_file(path)
    records = []
    for ecu_key, ecu_info in data.items():
        content = (
            f"ECU: {ecu_info.get('name', ecu_key)}\n"
            f"Type: {ecu_info.get('type', 'unknown')}\n"
            f"Assets: {ecu_info.get('hint', '')}"
        )
        records.append({
            "content": content,
            "meta": {
                "source": "dataecu",
                "ecu_key": ecu_key,
                "ecu_name": ecu_info.get("name", ecu_key),
                "ecu_type": ecu_info.get("type", ""),
                "file": Path(path).name,
            },
        })
    return records


def load_clauses(folder: str) -> list[dict[str, Any]]:
    """Load all clause JSON files from a folder."""
    records = []
    folder_path = Path(folder)
    for json_file in sorted(folder_path.glob("*.json")):
        data = load_json_file(str(json_file))
        clause_name = json_file.stem  # e.g. "clause-10"

        if isinstance(data, dict):
            for section_key, section_val in data.items():
                content = json.dumps(section_val, ensure_ascii=False)
                records.append({
                    "content": f"[{clause_name}] {section_key}: {content}",
                    "meta": {
                        "source": "iso_clause",
                        "clause": clause_name,
                        "section": section_key,
                        "file": json_file.name,
                    },
                })
        elif isinstance(data, list):
            for i, item in enumerate(data):
                records.append({
                    "content": f"[{clause_name}] {json.dumps(item, ensure_ascii=False)}",
                    "meta": {
                        "source": "iso_clause",
                        "clause": clause_name,
                        "index": i,
                        "file": json_file.name,
                    },
                })
    return records


def load_reports_db(folder: str) -> list[dict[str, Any]]:
    """Load all TARA report JSON files from reports_db folder."""
    records = []
    folder_path = Path(folder)
    for json_file in sorted(folder_path.glob("*.json")):
        data = load_json_file(str(json_file))
        report_name = json_file.stem

        # Reports are typically large nested structures — flatten into sections
        if isinstance(data, dict):
            for section_key, section_val in data.items():
                if isinstance(section_val, list):
                    for i, item in enumerate(section_val):
                        records.append({
                            "content": json.dumps(item, ensure_ascii=False),
                            "meta": {
                                "source": "tara_report",
                                "report": report_name,
                                "section": section_key,
                                "index": i,
                                "file": json_file.name,
                            },
                        })
                else:
                    records.append({
                        "content": json.dumps(section_val, ensure_ascii=False),
                        "meta": {
                            "source": "tara_report",
                            "report": report_name,
                            "section": section_key,
                            "file": json_file.name,
                        },
                    })
    return records


def load_xml_attack_patterns(path: str, max_entries: int = 0) -> list[dict[str, Any]]:
    """
    Stream-load CAPEC / CWE / ICS-ATT&CK XML files efficiently.
    Returns one record per attack pattern / weakness entry.
    Set max_entries=0 for no limit.
    """
    records = []
    source = Path(path).stem
    count = 0

    for event, elem in ET.iterparse(path, events=("end",)):
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag in ("Attack_Pattern", "Weakness"):
            # Extract key attributes
            entry_id = elem.get("ID", "")
            name = elem.get("Name", "")

            # Collect all text content from child elements
            text_parts = [f"ID: {entry_id}", f"Name: {name}"]
            desc_elem = elem.find(".//{*}Description")
            if desc_elem is not None and desc_elem.text:
                text_parts.append(f"Description: {desc_elem.text.strip()}")

            records.append({
                "content": "\n".join(text_parts),
                "meta": {
                    "source": source,
                    "entry_id": entry_id,
                    "name": name,
                    "type": tag.lower(),
                    "file": Path(path).name,
                },
            })
            elem.clear()  # free memory
            count += 1
            if max_entries and count >= max_entries:
                break

    return records


def load_all_datasets(datasets_dir: str) -> list[dict[str, Any]]:
    """
    Master loader — ingests all available datasets from the datasets/ folder.
    Returns a flat list of {content, meta} records ready for chunking.
    """
    base = Path(datasets_dir)
    all_records: list[dict[str, Any]] = []

    # ECU registry
    dataecu = base / "dataecu.json"
    if dataecu.exists():
        recs = load_dataecu(str(dataecu))
        print(f"  dataecu.json        -> {len(recs)} records")
        all_records.extend(recs)

    # Annex
    annex = base / "annex.json"
    if annex.exists():
        recs = load_json_flat(str(annex), source_tag="annex")
        print(f"  annex.json          -> {len(recs)} records")
        all_records.extend(recs)

    # ISO clauses
    clauses_dir = base / "clauses"
    if clauses_dir.exists():
        recs = load_clauses(str(clauses_dir))
        print(f"  clauses/            -> {len(recs)} records")
        all_records.extend(recs)

    # ATM attack patterns
    atm = base / "atm.json"
    if atm.exists():
        recs = load_json_flat(str(atm), source_tag="atm")
        print(f"  atm.json            -> {len(recs)} records")
        all_records.extend(recs)

    # TARA reports
    reports = base / "reports_db"
    if reports.exists():
        recs = load_reports_db(str(reports))
        print(f"  reports_db/         -> {len(recs)} records")
        all_records.extend(recs)

    # CAPEC XML
    capec = base / "capec.xml"
    if capec.exists():
        recs = load_xml_attack_patterns(str(capec))
        print(f"  capec.xml           -> {len(recs)} records")
        all_records.extend(recs)

    # CWE XML
    cwec = base / "cwec.xml"
    if cwec.exists():
        recs = load_xml_attack_patterns(str(cwec))
        print(f"  cwec.xml            -> {len(recs)} records")
        all_records.extend(recs)

    # ICS ATT&CK JSON
    ics = base / "icsattack.json"
    if ics.exists():
        recs = load_json_flat(str(ics), source_tag="icsattack")
        print(f"  icsattack.json      -> {len(recs)} records")
        all_records.extend(recs)

    # Mobile ATT&CK JSON
    mobile = base / "mobileattack.json"
    if mobile.exists():
        recs = load_json_flat(str(mobile), source_tag="mobileattack")
        print(f"  mobileattack.json   -> {len(recs)} records")
        all_records.extend(recs)

    print(f"\n  TOTAL INGESTED      -> {len(all_records)} records")
    return all_records
