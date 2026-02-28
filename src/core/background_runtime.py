"""
File: background_runtime.py
Path: src/core/background_runtime.py
Role: Background job submission and status tracking over task graph scheduler.
Used By:
 - src/integration/host_adapter.py
Depends On:
 - src/core/task_graph.py
 - src/core/scheduler.py
 - src/observability/tracing.py
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
from src.observability.logging import LogLevel, StructuredLogger
from src.observability.metrics import RuntimeMetrics
from src.observability.tracing import RuntimeTracer
from src.observability.timeline import RuntimeTimeline
from src.tenancy.quotas import TenantQuotaManager


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class BackgroundJob:
    job_id: str
    status: JobStatus = JobStatus.PENDING
    result: SchedulerResult | None = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BackgroundRuntime:
    def __init__(
        self,
        scheduler: TaskScheduler,
        logger: StructuredLogger | None = None,
        metrics: RuntimeMetrics | None = None,
        timeline: RuntimeTimeline | None = None,
        tracer: RuntimeTracer | None = None,
        tenant_quota_manager: TenantQuotaManager | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._jobs: dict[str, BackgroundJob] = {}
        self._job_tasks: dict[str, asyncio.Task[None]] = {}
        self._logger = logger
        self._metrics = metrics
        self._timeline = timeline
        self._tracer = tracer
        self._tenant_quota_manager = tenant_quota_manager or TenantQuotaManager()

    def submit(self, graph: TaskGraph, payload: dict[str, Any] | None = None, job_id: str | None = None) -> str:
        resolved_job_id = job_id or f"job_{uuid.uuid4().hex}"
        resolved_payload = dict(payload or {})
        tenant_id = str(resolved_payload.get("tenant_id", "default"))
        active_jobs = self._count_active_jobs(tenant_id)
        quota_decision = self._tenant_quota_manager.check_submission(tenant_id=tenant_id, active_jobs=active_jobs)
        if not quota_decision.allowed:
            raise ValueError(f"{quota_decision.reason_code}: {quota_decision.message}")
        job = BackgroundJob(
            job_id=resolved_job_id,
            metadata={"payload": resolved_payload, "graph": graph, "tenant_id": tenant_id},
        )
        self._jobs[resolved_job_id] = job
        self._emit(
            correlation_id=resolved_job_id,
            tenant_id=tenant_id,
            event="background.job_submitted",
            message="Background job submitted",
            context={"node_count": len(graph.node_ids()), "quota_reason": quota_decision.reason_code},
            level=LogLevel.INFO,
        )
        if self._metrics is not None:
            self._metrics.inc("background.job.submitted")
        self._job_tasks[resolved_job_id] = asyncio.create_task(self._run_job(graph=graph, job=job, resume=False))
        return resolved_job_id

    def get_job(self, job_id: str) -> BackgroundJob:
        if job_id not in self._jobs:
            raise KeyError(f"Job '{job_id}' was not found")
        return self._jobs[job_id]

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job '{job_id}' was not found")
        if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return False

        task = self._job_tasks.get(job_id)
        if task is None or task.done():
            return False

        self._emit(
            correlation_id=job_id,
            tenant_id=str(job.metadata.get("tenant_id", "default")),
            event="background.job_cancel_requested",
            message="Background job cancel requested",
            level=LogLevel.WARNING,
        )
        if self._metrics is not None:
            self._metrics.inc("background.job.cancel.requested")

        task.cancel()
        return True

    def resume_job(self, job_id: str) -> str:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job '{job_id}' was not found")
        if job.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
            raise RuntimeError(
                f"Job '{job_id}' is in status '{job.status.value}' and cannot be resumed"
            )

        graph = job.metadata.get("graph")
        if not isinstance(graph, TaskGraph):
            raise RuntimeError(f"Job '{job_id}' cannot be resumed because graph metadata is missing")

        job.status = JobStatus.PENDING
        job.error = ""
        job.result = None

        self._emit(
            correlation_id=job_id,
            tenant_id=str(job.metadata.get("tenant_id", "default")),
            event="background.job_resume_requested",
            message="Background job resume requested",
            level=LogLevel.INFO,
        )
        if self._metrics is not None:
            self._metrics.inc("background.job.resume.requested")

        self._job_tasks[job_id] = asyncio.create_task(self._run_job(graph=graph, job=job, resume=True))
        return job_id

    async def _run_job(self, graph: TaskGraph, job: BackgroundJob, resume: bool) -> None:
        job_span_id = self._start_span(
            correlation_id=job.job_id,
            name="background.run_job",
            attributes={"resume": resume},
        )
        try:
            job.status = JobStatus.RUNNING
            tenant_id = str(job.metadata.get("tenant_id", "default"))
            self._emit(
                correlation_id=job.job_id,
                tenant_id=tenant_id,
                event="background.job_started",
                message="Background job execution started",
                context={"resume": resume},
                level=LogLevel.INFO,
            )
            payload = dict(job.metadata.get("payload", {}))
            result = await self._scheduler.execute(
                job_id=job.job_id,
                graph=graph,
                initial_payload=payload,
                resume=resume,
                parent_span_id=job_span_id or None,
            )
            job.result = result
            job.status = JobStatus.FAILED if result.failed else JobStatus.COMPLETED
            self._emit(
                correlation_id=job.job_id,
                tenant_id=tenant_id,
                event="background.job_finished",
                message="Background job execution completed",
                context={"failed": result.failed, "outcomes": len(result.outcomes)},
                level=LogLevel.ERROR if result.failed else LogLevel.INFO,
            )
            if self._metrics is not None:
                if result.failed:
                    self._metrics.inc("background.job.failed")
                else:
                    self._metrics.inc("background.job.completed")
            self._finish_span(
                span_id=job_span_id,
                status="error" if result.failed else "ok",
                attributes={"failed": result.failed, "outcomes": len(result.outcomes)},
            )
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            self._emit(
                correlation_id=job.job_id,
                tenant_id=str(job.metadata.get("tenant_id", "default")),
                event="background.job_cancelled",
                message="Background job execution cancelled",
                level=LogLevel.WARNING,
            )
            if self._metrics is not None:
                self._metrics.inc("background.job.cancelled")
            self._finish_span(span_id=job_span_id, status="cancelled")
        except Exception as exc:  # pragma: no cover - defensive runtime boundary
            job.status = JobStatus.FAILED
            job.error = str(exc)
            self._emit(
                correlation_id=job.job_id,
                tenant_id=str(job.metadata.get("tenant_id", "default")),
                event="background.job_error",
                message="Background job execution error",
                context={"error": str(exc)},
                level=LogLevel.ERROR,
            )
            if self._metrics is not None:
                self._metrics.inc("background.job.error")
            self._finish_span(span_id=job_span_id, status="error", error=str(exc))
        finally:
            task = self._job_tasks.get(job.job_id)
            if task is asyncio.current_task():
                self._job_tasks.pop(job.job_id, None)

    def _emit(
        self,
        correlation_id: str,
        tenant_id: str,
        event: str,
        message: str,
        context: dict[str, Any] | None = None,
        level: LogLevel = LogLevel.INFO,
    ) -> None:
        if self._logger is not None:
            self._logger.log(
                level=level,
                event=event,
                message=message,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                context=context,
            )
        if self._timeline is not None:
            self._timeline.append(correlation_id=correlation_id, event=event, payload=context)

    def _count_active_jobs(self, tenant_id: str) -> int:
        active_statuses = {JobStatus.PENDING, JobStatus.RUNNING}
        return sum(
            1
            for job in self._jobs.values()
            if str(job.metadata.get("tenant_id", "default")) == tenant_id and job.status in active_statuses
        )

    def _start_span(
        self,
        correlation_id: str,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        if self._tracer is None:
            return ""
        return self._tracer.start_span(
            correlation_id=correlation_id,
            name=name,
            attributes=attributes,
        )

    def _finish_span(
        self,
        span_id: str,
        status: str,
        attributes: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        if self._tracer is None or not span_id:
            return
        self._tracer.finish_span(
            span_id=span_id,
            status=status,
            attributes=attributes,
            error=error,
        )
