"""
File: test_readiness_api.py
Path: tests/modules/api/test_readiness_api.py
Role: Smoke tests for /health and /ready system probes.
Used By:
 - pytest
Depends On:
 - src/api/app.py
Notes:
 - Uses the default sqlite-backed bootstrap from create_app().
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.fixture()
def _isolated_exo_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_DB_PATH", str(tmp_path / "exo.db"))


def test_health_is_liveness_ok(_isolated_exo_db: None) -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "ok"
    assert body.get("probe") == "liveness"


def test_ready_reports_sqlite_ok(_isolated_exo_db: None) -> None:
    client = TestClient(create_app())
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body.get("ready") is True
    checks = body.get("checks")
    assert isinstance(checks, dict)
    assert checks.get("primary_sqlite") == "ok"
