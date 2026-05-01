import hashlib
import json
import time
from copy import deepcopy
from typing import Any, Callable


class SimpleCache:
    """Small in-memory cache to avoid repeated search, scrape, summary, and answer calls."""

    def __init__(self, default_ttl_seconds: int = 3600):
        self.default_ttl_seconds = default_ttl_seconds
        self._store: dict[str, dict[str, Any]] = {}

    def make_key(self, namespace: str, payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{namespace}:{digest}"

    def get(self, namespace: str, payload: Any) -> Any | None:
        key = self.make_key(namespace, payload)
        entry = self._store.get(key)
        if not entry:
            return None

        if entry["expires_at"] and entry["expires_at"] < time.time():
            self._store.pop(key, None)
            return None

        return deepcopy(entry["value"])

    def set(
        self,
        namespace: str,
        payload: Any,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> Any:
        key = self.make_key(namespace, payload)
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        self._store[key] = {
            "value": deepcopy(value),
            "expires_at": time.time() + ttl if ttl > 0 else None,
        }
        return deepcopy(value)

    def get_or_set(
        self,
        namespace: str,
        payload: Any,
        factory: Callable[[], Any],
        ttl_seconds: int | None = None,
    ) -> Any:
        cached = self.get(namespace, payload)
        if cached is not None:
            return cached

        value = factory()
        return self.set(namespace, payload, value, ttl_seconds)

    def clear(self) -> None:
        self._store.clear()


cache = SimpleCache()
