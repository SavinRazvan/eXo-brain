"""
File: constants.py
Path: tests/constants.py
Role: Shared test-only constants (JWT secrets, adapter distribution names).
Used By:
 - tests/conftest.py
 - tests/modules/tools/*
 - tests/modules/api/*
Depends On:
 - N/A
Notes:
 - HS256 secrets must be >= 32 bytes to avoid PyJWT InsecureKeyLengthWarning in pytest output.
"""

from __future__ import annotations

# ≥32 bytes — PyJWT / RFC 7518 recommendation for HS256 test tokens.
BYOC_WORKER_JWT_SECRET = "exo-byoc-test-worker-jwt-secret-value-ok"

ADAPTER_DISTRIBUTIONS: tuple[str, ...] = (
    "exo-brain-core-contracts",
    "exo-brain-adapter-sdk",
    "exo-adapter-echo",
    "exo-adapter-openai",
)

ADAPTER_IMPORT_MODULES: dict[str, str] = {
    "exo-brain-core-contracts": "exo_brain_core_contracts",
    "exo-brain-adapter-sdk": "exo_brain_adapter_sdk",
    "exo-adapter-echo": "exo_adapter_echo",
    "exo-adapter-openai": "exo_adapter_openai",
}
