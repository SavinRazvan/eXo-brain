"""
File: test_secrets_provider.py
Path: tests/unit/test_secrets_provider.py
Role: Unit tests for environment and cached secrets provider behavior.
Used By:
 - pytest
Depends On:
 - src/secrets/env_provider.py
 - src/secrets/cache_and_rotation.py
Notes:
 - Verifies cache invalidation supports rotation-friendly retrieval.
"""

import os

from src.secrets.cache_and_rotation import CachedSecretsProvider
from src.secrets.env_provider import EnvSecretsProvider


def test_env_and_cached_secrets_provider_support_rotation_invalidation() -> None:
    os.environ["TEST_SECRET_KEY"] = "value_1"
    env_provider = EnvSecretsProvider()
    cached = CachedSecretsProvider(env_provider)
    assert cached.get("TEST_SECRET_KEY") == "value_1"

    os.environ["TEST_SECRET_KEY"] = "value_2"
    assert cached.get("TEST_SECRET_KEY") == "value_1"
    cached.invalidate("TEST_SECRET_KEY")
    assert cached.get("TEST_SECRET_KEY") == "value_2"

