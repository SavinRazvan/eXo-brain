"""
File: test_worker_auth.py
Path: tests/modules/tools/test_worker_auth.py
Role: Unit tests for BYOC worker JWT mint and verification edge paths.
Used By:
 - pytest
Depends On:
 - src/tools/byoc/worker_auth.py
Notes:
 - Uses short-lived tokens and invalid payloads for deterministic failures.
"""

from __future__ import annotations

import time

import jwt
import pytest

from src.tools.byoc.worker_auth import mint_worker_token, verify_worker_token


def test_verify_worker_token_rejects_expired_token() -> None:
    secret = "worker-auth-test-secret-key-32b!!"
    payload = {
        "sub": "byoc-worker:x",
        "tenant_id": "t1",
        "worker_id": "w1",
        "jti": "jti_1",
        "iat": int(time.time()) - 120,
        "exp": int(time.time()) - 60,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(ValueError, match="WORKER_TOKEN_EXPIRED"):
        verify_worker_token(token=token, secret=secret, expected_tenant_id="t1")


def test_verify_worker_token_rejects_tenant_mismatch() -> None:
    secret = "worker-auth-test-secret-key-32b!!"
    token = mint_worker_token(tenant_id="t_a", worker_id="w1", secret=secret)
    with pytest.raises(ValueError, match="TENANT_MISMATCH"):
        verify_worker_token(token=token, secret=secret, expected_tenant_id="t_b")


def test_verify_worker_token_rejects_blank_worker_id() -> None:
    secret = "worker-auth-test-secret-key-32b!!"
    payload = {
        "sub": "byoc-worker:x",
        "tenant_id": "t1",
        "worker_id": "   ",
        "jti": "jti_1",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(ValueError, match="WORKER_TOKEN_INVALID"):
        verify_worker_token(token=token, secret=secret, expected_tenant_id="t1")


def test_verify_worker_token_rejects_blank_jti() -> None:
    secret = "worker-auth-test-secret-key-32b!!"
    payload = {
        "sub": "byoc-worker:x",
        "tenant_id": "t1",
        "worker_id": "w1",
        "jti": "  ",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(ValueError, match="WORKER_TOKEN_INVALID"):
        verify_worker_token(token=token, secret=secret, expected_tenant_id="t1")
