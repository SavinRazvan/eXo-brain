"""
File: ui.py
Path: src/api/routers/ui.py
Role: Mount static dashboard assets under /ui.
Used By:
 - src/api/app.py
Depends On:
 - fastapi
 - fastapi.staticfiles
Notes:
 - Uses check_dir=False so API boot does not fail when UI assets are not built yet.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def mount_ui(app: FastAPI) -> None:
    """Mount the dashboard static files under /ui."""
    repo_root = Path(__file__).resolve().parents[3]
    dist_dir = repo_root / "ui" / "dist"
    app.mount(
        "/ui",
        StaticFiles(directory=str(dist_dir), html=True, check_dir=False),
        name="ui",
    )
