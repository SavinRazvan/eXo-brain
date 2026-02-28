"""
File: provider.py
Path: src/secrets/provider.py
Role: Abstract secrets provider contract for runtime/config integrations.
Used By:
 - src/secrets/env_provider.py
 - src/config/provider_registry.py
Depends On:
 - abc
Notes:
 - Contract enables env/vault/kms implementations without changing callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretsProvider(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None:
        """Return secret value by key or None when unavailable."""

