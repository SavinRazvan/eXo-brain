"""
File: prometheus_metrics.py
Path: src/api/routers/prometheus_metrics.py
Role: Optional Prometheus text metrics endpoint for scrapers.
Used By:
 - src/api/app.py
Depends On:
 - fastapi
 - src/observability/telemetry_export.py
Notes:
 - Gated by EXO_ENABLE_PROMETHEUS_METRICS; keep off by default for minimal attack surface.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from src.observability.telemetry_export import build_minimal_prometheus_text

router = APIRouter(tags=["system"])


@router.get("/metrics", summary="Prometheus text metrics (optional)")
async def prometheus_metrics() -> Response:
    return Response(content=build_minimal_prometheus_text(), media_type="text/plain; version=0.0.4")
