"""
File: app.py
Path: src/api/app.py
Role: FastAPI application factory — creates and configures the eXo-brain API.
Used By:
 - src/api/bootstrap.py
 - tests/modules/api/
Depends On:
 - fastapi
 - src/api/bootstrap.py
Notes:
 - create_app() is the single entry-point. Never instantiate FastAPI directly outside this file.
 - Routers are registered here as they are built in Slices 2–4.
 - app.state holds: tenant_factory, provider_registry, policy_overlay_store (set by bootstrap).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app(title: str = "eXo-brain API", version: str = "0.1.0") -> FastAPI:
    """Create and return a configured FastAPI application instance."""
    app = FastAPI(
        title=title,
        version=version,
        description=(
            "Provider-neutral AI orchestration platform. "
            "Deterministic tool execution, multi-tenant runtime isolation, "
            "SSE and WebSocket streaming."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"], summary="Platform health check")
    async def health() -> dict:
        return {"status": "ok", "platform": "eXo-brain"}

    # Slice 2 — Tool & Agent Management
    from src.api.routers.tools import router as tools_router
    from src.api.routers.agents import router as agents_router

    app.include_router(tools_router, prefix="/tenants")
    app.include_router(agents_router, prefix="/tenants")

    # Slice 3 — Adapter Playground (sessions, turns, providers)
    from src.api.routers.sessions import router as sessions_router
    from src.api.routers.turns import router as turns_router
    from src.api.routers.providers import router as providers_router

    app.include_router(sessions_router, prefix="/tenants")
    app.include_router(turns_router, prefix="/tenants")
    app.include_router(providers_router)

    # Slice 4 — Tenant Policy & Quota Management
    from src.api.routers.tenants import router as tenants_router

    app.include_router(tenants_router, prefix="/tenants")

    # Slice 1 — Auth Hardening (API key management)
    from src.api.routers.admin_keys import router as admin_keys_router

    app.include_router(admin_keys_router)

    return app
