# =============================================================================
# cache_manager.py — TTL management, refresh, and cache ID registry
# =============================================================================

import json
import os
import time
from pathlib import Path
from typing import Optional

import config
from cag.cache_builder import build_cache


class CacheManager:
    """
    Lifecycle management for Gemini context caches.

    - get_or_build() — returns valid cache_name, rebuilds if expired
    - refresh() — extends TTL on an existing cache
    - invalidate() — forces rebuild on next get_or_build()
    """

    def __init__(self, registry_path: str | None = None, datasets_dir: str | None = None):
        self.registry_path = Path(registry_path or config.CAG_CACHE_REGISTRY)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.datasets_dir = datasets_dir
        self._registry = self._load_registry()

    def _load_registry(self) -> dict:
        """Load cache registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_registry(self):
        """Save cache registry to disk."""
        with open(self.registry_path, "w") as f:
            json.dump(self._registry, f, indent=2)

    def get_or_build(self) -> Optional[str]:
        """
        Return a valid cache_name. Rebuilds if expired or missing.
        Returns None if CAG is disabled or build fails.
        """
        if not config.ENABLE_CAG:
            return None

        # Check if we have a valid cached entry
        cache_name = self._registry.get("cache_name")
        expires_at = self._registry.get("expires_at", 0)

        if cache_name and time.time() < expires_at:
            print(f"  [CacheManager] Using existing cache: {cache_name}")
            return cache_name

        # Build new cache
        print("  [CacheManager] Building new context cache...")
        cache_name = build_cache(self.datasets_dir)

        if cache_name:
            self._registry = {
                "cache_name": cache_name,
                "created_at": time.time(),
                "expires_at": time.time() + config.CAG_TTL_SECONDS,
                "ttl_seconds": config.CAG_TTL_SECONDS,
            }
            self._save_registry()

        return cache_name

    def refresh(self, cache_name: str | None = None) -> bool:
        """Extend TTL on an existing cache."""
        name = cache_name or self._registry.get("cache_name")
        if not name:
            return False

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=config.GOOGLE_API_KEY)
            client.caches.update(
                name=name,
                config=types.UpdateCachedContentConfig(
                    ttl=f"{config.CAG_TTL_SECONDS}s",
                ),
            )
            self._registry["expires_at"] = time.time() + config.CAG_TTL_SECONDS
            self._save_registry()
            print(f"  [CacheManager] Refreshed cache TTL: {name}")
            return True
        except Exception as e:
            print(f"  [CacheManager] Failed to refresh: {e}")
            return False

    def invalidate(self):
        """Force rebuild on next get_or_build()."""
        self._registry = {}
        self._save_registry()
        print("  [CacheManager] Cache invalidated — will rebuild on next query")

    @property
    def is_active(self) -> bool:
        """Check if we have a non-expired cache."""
        return bool(
            self._registry.get("cache_name")
            and time.time() < self._registry.get("expires_at", 0)
        )
