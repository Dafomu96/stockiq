"""
Cache layer for StockIQ.

Design decision (ADR-002): JSON file cache for the MVP.
The abstract interface (CacheBackend) means switching to Redis
in Phase 3 requires changing one line in the factory, not the callers.

All cache operations are typed and log on miss/hit for observability.
"""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from config.exceptions import CacheError
from config.settings import settings

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract cache interface.

    Concrete implementations: JsonFileCache (MVP), RedisCache (Phase 3).
    Callers depend on this interface, never on the implementation.
    """

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Return cached value or None if missing / expired."""

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int) -> None:
        """Store value with a TTL in seconds."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove a single key."""

    @abstractmethod
    def clear(self) -> None:
        """Flush the entire cache — useful in tests."""


class JsonFileCache(CacheBackend):
    """File-based JSON cache.

    Each key is stored as a separate JSON file:
        .cache/<key>.json  →  {"expires_at": <unix_ts>, "data": <value>}

    Pros: zero dependencies, human-readable, debuggable.
    Cons: not suitable for concurrent writes or large volumes.
    Replace with RedisCache for production (ADR-002).

    Args:
        cache_dir: Directory where cache files are written.
                   Defaults to settings.cache_dir (".cache").
    """

    def __init__(self, cache_dir: str | None = None) -> None:
        self._dir = Path(cache_dir or settings.cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(":", "_")
        return self._dir / f"{safe_key}.json"

    def get(self, key: str) -> Any | None:
        """Return value if cached and not expired, else None."""
        path = self._path(key)
        if not path.exists():
            logger.debug("cache_miss key=%s", key)
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("cache_read_error key=%s error=%s", key, exc)
            return None

        if time.time() > payload["expires_at"]:
            logger.debug("cache_expired key=%s", key)
            path.unlink(missing_ok=True)
            return None

        logger.debug("cache_hit key=%s", key)
        return payload["data"]

    def set(self, key: str, value: Any, ttl: int) -> None:
        """Write value to cache with expiry = now + ttl seconds."""
        payload = {"expires_at": time.time() + ttl, "data": value}
        try:
            self._path(key).write_text(
                json.dumps(payload, default=str), encoding="utf-8"
            )
        except OSError as exc:
            raise CacheError(f"Cannot write cache key '{key}': {exc}") from exc

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def clear(self) -> None:
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)


def get_cache() -> CacheBackend:
    """Factory function — returns the configured cache backend.

    To switch to Redis: change this function only.
    All callers remain unchanged.
    """
    return JsonFileCache()
