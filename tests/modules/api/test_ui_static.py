"""
File: test_ui_static.py
Path: tests/modules/api/test_ui_static.py
Role: Verifies UI/static dashboard endpoints are not mounted in API-first mode.
Used By:
 - pytest
Depends On:
 - src/api/bootstrap.py
Notes:
 - Option C API-first baseline intentionally defers dashboard serving from backend runtime.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app


def test_ui_index_is_not_mounted() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/ui/")
    assert resp.status_code == 404


def test_ui_static_assets_are_not_mounted() -> None:
    app = build_test_app()
    client = TestClient(app)
    assert client.get("/ui/app.js").status_code == 404
    assert client.get("/ui/screens/tools.js").status_code == 404
    assert client.get("/ui/screens/playground.js").status_code == 404
    assert client.get("/ui/styles.css").status_code == 404
