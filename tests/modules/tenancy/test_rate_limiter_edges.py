"""
File: test_rate_limiter_edges.py
Path: tests/modules/tenancy/test_rate_limiter_edges.py
Role: Edge-path tests for in-process and SQLite tenant rate limiters.
Used By:
 - pytest
Depends On:
 - src/tenancy/rate_limiter.py
Notes:
 - Covers disabled limiters and window rollover without waiting real clock time.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.tenancy.rate_limiter import SQLiteTenantRateLimiter, TenantRateLimiter


def test_tenant_rate_limiter_allows_all_when_max_requests_zero() -> None:
    limiter = TenantRateLimiter(max_requests=0, window_seconds=60)
    allowed, _remaining = limiter.allow("any")
    assert allowed is True


def test_tenant_rate_limiter_resets_window_when_epoch_advances(monkeypatch: pytest.MonkeyPatch) -> None:
    now = {"v": 1_000_000}

    monkeypatch.setattr("src.tenancy.rate_limiter.time.time", lambda: float(now["v"]))

    limiter = TenantRateLimiter(max_requests=1, window_seconds=10)
    assert limiter.allow("t1")[0] is True
    assert limiter.allow("t1")[0] is False
    now["v"] += 11
    assert limiter.allow("t1")[0] is True


def test_sqlite_rate_limiter_allows_all_when_max_requests_zero(tmp_path: Path) -> None:
    db = tmp_path / "rl.db"
    limiter = SQLiteTenantRateLimiter(db_path=str(db), max_requests=0, limiter_id="x")
    assert limiter.allow("t1")[0] is True


def test_sqlite_rate_limiter_inserts_first_row_when_missing(tmp_path: Path) -> None:
    db = tmp_path / "rl2.db"
    limiter = SQLiteTenantRateLimiter(db_path=str(db), max_requests=2, window_seconds=max(60, int(time.time() % 3600) or 60))
    assert limiter.allow("tenant_a", limiter_id="custom")[0] is True
