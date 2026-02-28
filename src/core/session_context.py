"""
File: session_context.py
Path: src/core/session_context.py
Role: Typed session and correlation context contracts for orchestration boundaries.
Used By:
 - src/core/orchestrator.py
 - src/core/event_router.py
 - src/integration/host_adapter.py
Depends On:
 - dataclasses
Notes:
 - Keep this contract provider-neutral and stable for replay/audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SessionContext:
    session_id: str
    run_id: str
    job_id: str
    task_id: str
    agent_id: str
    provider_id: str = "default"
    correlation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_runtime_context(cls, session_id: str, context: dict[str, Any]) -> "SessionContext":
        return cls(
            session_id=session_id,
            run_id=str(context.get("run_id", "run_unknown")),
            job_id=str(context.get("job_id", "job_unknown")),
            task_id=str(context.get("task_id", "task_unknown")),
            agent_id=str(context.get("agent_id", "agent_unknown")),
            provider_id=str(context.get("provider_id", "default")),
            correlation_id=str(context.get("correlation_id", context.get("run_id", "corr_unknown"))),
            metadata=dict(context.get("session_metadata", {})),
        )
