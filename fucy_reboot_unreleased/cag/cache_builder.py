# =============================================================================
# cache_builder.py — Build & upload context cache to Gemini API
# =============================================================================

import json
import os
from pathlib import Path
from typing import Any

import config


def prepare_cag_content(datasets_dir: str | None = None) -> str:
    """
    Concatenate all CAG-designated datasets into a single formatted
    text block suitable for Gemini context caching.

    Reads files specified in config.CAG_DATASETS.
    """
    base = Path(datasets_dir) if datasets_dir else Path("datasets")
    parts: list[str] = []

    for dataset_path in config.CAG_DATASETS:
        full_path = base.parent / dataset_path if not Path(dataset_path).is_absolute() else Path(dataset_path)

        if full_path.is_dir():
            # Load all .json files from directory
            for json_file in sorted(full_path.glob("*.json")):
                content = _load_and_format(json_file)
                if content:
                    parts.append(f"=== {json_file.name} ===\n{content}")
        elif full_path.exists():
            content = _load_and_format(full_path)
            if content:
                parts.append(f"=== {full_path.name} ===\n{content}")
        else:
            print(f"  [CAG] Warning: dataset not found: {full_path}")

    combined = "\n\n" + "\n\n".join(parts)
    print(f"  [CAG] Prepared {len(parts)} dataset blocks ({len(combined)} chars)")
    return combined


def _load_and_format(path: Path) -> str:
    """Load a JSON file and format it as readable text."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  [CAG] Error loading {path}: {e}")
        return ""


def build_cache(datasets_dir: str | None = None) -> str | None:
    """
    Build and upload the CAG context cache to Gemini.

    Returns the cache_name string (e.g. 'cachedContents/abc123') or None on failure.
    Requires the google-genai SDK.
    """
    if not config.ENABLE_CAG:
        print("  [CAG] Disabled via config.ENABLE_CAG")
        return None

    content_text = prepare_cag_content(datasets_dir)
    if not content_text.strip():
        print("  [CAG] No content to cache")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GOOGLE_API_KEY)

        # Create cached content
        cache = client.caches.create(
            model=config.GEMINI_MODEL,
            config=types.CreateCachedContentConfig(
                display_name="fucy_reboot_domain_knowledge",
                contents=[content_text],
                ttl=f"{config.CAG_TTL_SECONDS}s",
            ),
        )

        cache_name = cache.name
        print(f"  [CAG] Cache created: {cache_name} (TTL={config.CAG_TTL_SECONDS}s)")
        return cache_name

    except ImportError:
        print("  [CAG] google-genai SDK not installed. Install with: pip install google-genai")
        return None
    except Exception as e:
        print(f"  [CAG] Failed to create cache: {e}")
        return None
