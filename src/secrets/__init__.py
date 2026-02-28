"""
File: __init__.py
Path: src/secrets/__init__.py
Role: Public exports for secrets provider abstractions.
Used By:
 - src/config/provider_registry.py
 - tests/unit/test_secrets_provider.py
Depends On:
 - src/secrets/provider.py
 - src/secrets/env_provider.py
 - src/secrets/cache_and_rotation.py
Notes:
 - Default path should remain environment-backed unless configured otherwise.
"""

from src.secrets.cache_and_rotation import CachedSecretsProvider
from src.secrets.env_provider import EnvSecretsProvider
from src.secrets.provider import SecretsProvider

__all__ = ["SecretsProvider", "EnvSecretsProvider", "CachedSecretsProvider"]

