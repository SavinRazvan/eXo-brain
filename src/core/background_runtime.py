"""
File: background_runtime.py
Path: src/core/background_runtime.py
Role: Background job submission and status tracking over task graph scheduler.
Used By:
 - src/integration/host_adapter.py
Depends On:
 - src/core/task_graph.py
 - src/core/scheduler.py
Notes:
 - Runtime keeps execution state separate from orchestration logic.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.scheduler import SchedulerResult, TaskScheduler
from src.core.task_graph import TaskGraph


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class BackgroundJob:
    job_id: str
    status: JobStatus = JobStatus.PENDING
    result: SchedulerResult | None = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BackgroundRuntime:
    def __init__(self, scheduler: TaskScheduler) -> None:
        self._scheduler = scheduler
        self._jobs: dict[str, BackgroundJob] = {}

    def submit(self, graph: TaskGraph, payload: dict[str, Any] | None = None, job_id: str | None = None) -> str:
        resolved_job_id = job_id or f"job_{uuid.uuid4().hex}"
        job = BackgroundJob(job_id=resolved_job_id, metadata={"payload": dict(payload or {})})
        self._jobs[resolved_job_id] = job
        asyncio.create_task(self._run_job(graph=graph, job=job))
        return resolved_job_id

    def get_job(self, job_id: str) -> BackgroundJob:
        if job_id not in self._jobs:
            raise KeyError(f"Job '{job_id}' was not found")
        return self._jobs[job_id]

    async def _run_job(self, graph: TaskGraph, job: BackgroundJob) -> None:
        try:
            job.status = JobStatus.RUNNING
            payload = dict(job.metadata.get("payload", {}))
            result = await self._scheduler.execute(job_id=job.job_id, graph=graph, initial_payload=payload)
            job.result = result
            job.status = JobStatus.FAILED if result.failed else JobStatus.COMPLETED
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            job.status = JobStatus.FAILED
            job.error = str(exc)
