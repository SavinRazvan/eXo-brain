"""
File: test_secrets_provider.py
Path: tests/modules/secrets/test_secrets_provider.py
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
from src.secrets.provider import SecretsProvider


def test_env_and_cached_secrets_provider_support_rotation_invalidation() -> None:
    os.environ["TEST_SECRET_KEY"] = "value_1"
    env_provider = EnvSecretsProvider()
    cached = CachedSecretsProvider(env_provider)
    assert cached.get("TEST_SECRET_KEY") == "value_1"

    os.environ["TEST_SECRET_KEY"] = "value_2"
    assert cached.get("TEST_SECRET_KEY") == "value_1"
    cached.invalidate("TEST_SECRET_KEY")
    assert cached.get("TEST_SECRET_KEY") == "value_2"


def test_env_secrets_provider_returns_none_for_missing_or_blank_values() -> None:
    provider = EnvSecretsProvider()
    os.environ.pop("MISSING_SECRET_KEY", None)
    assert provider.get("MISSING_SECRET_KEY") is None

    os.environ["BLANK_SECRET_KEY"] = "   "
    assert provider.get("BLANK_SECRET_KEY") is None


def test_cached_provider_retries_after_missing_value_invalidation() -> None:
    os.environ.pop("ROTATING_SECRET_KEY", None)
    env_provider = EnvSecretsProvider()
    cached = CachedSecretsProvider(env_provider)

    assert cached.get("ROTATING_SECRET_KEY") is None
    os.environ["ROTATING_SECRET_KEY"] = "rotated-value"
    assert cached.get("ROTATING_SECRET_KEY") is None

    cached.invalidate("ROTATING_SECRET_KEY")
    assert cached.get("ROTATING_SECRET_KEY") == "rotated-value"


class _RaisingSecretsProvider(SecretsProvider):
    def get(self, key: str) -> str | None:  # pragma: no cover - simple test helper
        raise RuntimeError(f"backend unavailable for {key}")


def test_cached_provider_surfaces_delegate_failures_deterministically() -> None:
    cached = CachedSecretsProvider(_RaisingSecretsProvider())
    try:
        cached.get("SECRET_KEY")
    except RuntimeError as exc:
        assert "backend unavailable" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected RuntimeError from delegate secrets provider")

