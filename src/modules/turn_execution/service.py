"""
File: service.py
Path: src/modules/turn_execution/service.py
Role: Public turn-execution helper surface for adapter-driven progress behavior.
Used By:
 - src/core/orchestrator.py
Depends On:
 - src.tools.execution_adapter.py
Notes:
 - Keeps backend-specific progress handling out of core orchestration conditionals.
"""

from __future__ import annotations

from src.tools.execution_adapter import ToolExecutionAdapter


def adapter_manages_progress_events(adapter: ToolExecutionAdapter | None) -> bool:
    if adapter is None:
        return False
    manages_progress = getattr(adapter, "manages_progress_events", None)
    if not callable(manages_progress):
        return False
    return bool(manages_progress())
