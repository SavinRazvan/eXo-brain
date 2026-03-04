"""
File: test_ui_static.py
Path: tests/modules/api/test_ui_static.py
Role: Verifies Slice 3 static dashboard files are served under /ui.
Used By:
 - pytest
Depends On:
 - src/api/bootstrap.py
Notes:
 - Uses build_test_app() to validate mount wiring independently from SQLite persistence.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app


def test_ui_index_is_served() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "eXo-brain Dashboard" in resp.text
    assert "Import + Upload + Activate" in resp.text
    assert "tool-version" in resp.text
    assert "tool-package-ref" in resp.text


def test_ui_js_bundle_is_served() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/ui/app.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers.get("content-type", "")
    assert "Dashboard entry point" in resp.text

    tools_js = client.get("/ui/screens/tools.js")
    assert tools_js.status_code == 200
    assert "javascript" in tools_js.headers.get("content-type", "")
    assert "importToolSchema" in tools_js.text
    assert "uploadToolVersion" in tools_js.text
    assert "validateToolVersion" in tools_js.text
    assert "listToolVersions" in tools_js.text


def test_ui_css_is_served() -> None:
    app = build_test_app()
    client = TestClient(app)
    resp = client.get("/ui/styles.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers.get("content-type", "")
