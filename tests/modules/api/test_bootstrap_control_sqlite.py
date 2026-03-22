"""
File: test_bootstrap_control_sqlite.py
Path: tests/modules/api/test_bootstrap_control_sqlite.py
Role: Covers bootstrap wiring when control-plane state uses SQLite backends.
Used By:
 - pytest
Depends On:
 - src/api/bootstrap.py
 - src/api/app.py
Notes:
 - Exercises SQLite run-control registry + tenant rate limiters (bootstrap sqlite branch).
"""

from __future__ import annotations

from dataclasses import replace

from fastapi import FastAPI

from src.api.app import _default_provider_registry, _default_settings
from src.api.bootstrap import bootstrap
from src.config.settings import RuntimeSettings
from src.core.run_control_registry import SQLiteRunControlRegistry
from src.tenancy.rate_limiter import SQLiteTenantRateLimiter


def test_bootstrap_uses_sqlite_when_control_state_backend_is_sqlite(tmp_path) -> None:
    base = _default_settings()
    settings = replace(
        base,
        runtime=replace(
            base.runtime,
            control_state_backend="sqlite",
            control_state_sqlite_db_path=str(tmp_path / "control_state.db"),
        ),
    )
    app = FastAPI()
    registry = _default_provider_registry(settings)
    bootstrap(app, registry, settings, persistence_backend="memory")

    assert isinstance(app.state.run_control_registry, SQLiteRunControlRegistry)
    assert isinstance(app.state.turn_rate_limiter, SQLiteTenantRateLimiter)
    assert isinstance(app.state.tool_upload_rate_limiter, SQLiteTenantRateLimiter)
