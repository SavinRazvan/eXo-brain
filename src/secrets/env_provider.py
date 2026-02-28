"""
File: env_provider.py
Path: src/secrets/env_provider.py
Role: Environment-variable backed secrets provider.
Used By:
 - src/config/provider_registry.py
Depends On:
 - os
 - src/secrets/provider.py
Notes:
 - Baseline provider for local/dev profiles and CI.
"""

from __future__ import annotations

import os

from src.secrets.provider import SecretsProvider


class EnvSecretsProvider(SecretsProvider):
    def get(self, key: str) -> str | None:
        value = os.getenv(key)
        if value is None:
            return None
        value = value.strip()
        return value or None

