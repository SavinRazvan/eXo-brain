"""
File: cache_and_rotation.py
Path: src/secrets/cache_and_rotation.py
Role: Lightweight cached secret access with explicit invalidation hooks.
Used By:
 - future secrets backends and runtime bootstrap paths
Depends On:
 - src/secrets/provider.py
Notes:
 - Keeps rotation behavior explicit by allowing cache eviction per key.
"""

from __future__ import annotations

from src.secrets.provider import SecretsProvider


class CachedSecretsProvider(SecretsProvider):
    def __init__(self, delegate: SecretsProvider) -> None:
        self._delegate = delegate
        self._cache: dict[str, str | None] = {}

    def get(self, key: str) -> str | None:
        if key not in self._cache:
            self._cache[key] = self._delegate.get(key)
        return self._cache[key]

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

