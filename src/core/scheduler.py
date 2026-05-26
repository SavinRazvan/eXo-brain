"""
File: scheduler.py
Path: src/core/scheduler.py
Role: Executes task graphs with retries, checkpointing, and resume support.
Used By:
 - src/core/background_runtime.py
Depends On:
 - src/core/task_graph.py
 - src/core/worker_pool.py
 - src/observability/tracing.py
 - src/persistence/contracts.py
Notes:
 - Scheduler stops dependents when an upstream node fails.
 - Defensive `AssertionError` after `_run_node` retry loop satisfies static exhaustiveness (unreachable).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from src.core.task_graph import TaskGraph, TaskNode, TaskOutcome, TaskStatus
from src.core.worker_pool import WorkerPool
from src.observability.logging import LogLevel, StructuredLogger
from src.observability.metrics import RuntimeMetrics
from src.observability.tracing import RuntimeTracer
from src.observability.timeline import RuntimeTimeline
from src.persistence.contracts import CheckpointRecord, CheckpointStatus, CheckpointStoreContract
from src.resilience.retry_policy import RetryPolicy


@dataclass(slots=True)
class SchedulerResult:
    job_id: str
    outcomes: dict[str, TaskOutcome] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return any(outcome.status == TaskStatus.FAILED for outcome in self.outcomes.values())


class TaskScheduler:
    def __init__(
        self,
        worker_pool: WorkerPool,
        checkpoint_store: CheckpointStoreContract,
        logger: StructuredLogger | None = None,
        metrics: RuntimeMetrics | None = None,
        timeline: RuntimeTimeline | None = None,
        tracer: RuntimeTracer | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._worker_pool = worker_pool
        self._checkpoints = checkpoint_store
        self._logger = logger
        self._metrics = metrics
        self._timeline = timeline
        self._tracer = tracer
        self._retry_policy = retry_policy or RetryPolicy()

    @property
    def worker_pool_concurrency(self) -> int:
        return self._worker_pool.max_concurrency

    def scale_worker_pool_up_to(self, target_concurrency: int) -> bool:
        return self._worker_pool.scale_up_to(target_concurrency)

    async def execute(
        self,
        job_id: str,
        graph: TaskGraph,
        initial_payload: dict[str, Any] | None = None,
        resume: bool = False,
        parent_span_id: str | None = None,
    ) -> SchedulerResult:
        started_at = perf_counter()
        execute_span_id = self._start_span(
            correlation_id=job_id,
            name="scheduler.execute",
            parent_span_id=parent_span_id,
            attributes={"resume": resume, "node_count": len(graph.node_ids())},
        )
        result = SchedulerResult(job_id=job_id)
        completed: set[str] = set()
        running: set[str] = set()
        failed: set[str] = set()
        cancelled: set[str] = set()
        self._emit(
            job_id=job_id,
            event="scheduler.job_started",
            message="Scheduler execution started",
            context={"resume": resume, "node_count": len(graph.node_ids())},
        )
        self._set_queue_depth(job_id, len(graph.node_ids()))

        try:
            if resume:
                checkpoints = await self._checkpoints.list_checkpoints(job_id)
                for checkpoint in checkpoints:
                    outcome = TaskOutcome(
                        node_id=checkpoint.node_id,
                        status=_task_status_from_checkpoint(checkpoint.status),
                        output=dict(checkpoint.payload),
                        reason_code=checkpoint.reason_code,
                        attempts=checkpoint.attempt,
                    )
                    result.outcomes[checkpoint.node_id] = outcome
                    if checkpoint.status == CheckpointStatus.COMPLETED:
                        completed.add(checkpoint.node_id)
                    elif checkpoint.status == CheckpointStatus.FAILED:
                        failed.add(checkpoint.node_id)

            base_payload = dict(initial_payload or {})
            while True:
                ready = [
                    node
                    for node in graph.ready_nodes(completed=completed, running=running, failed=failed)
                    if node.node_id not in cancelled
                ]
                if not ready:
                    break

                tasks = []
                for node in ready:
                    running.add(node.node_id)
                    tasks.append(
                        asyncio.create_task(
                            self._worker_pool.run(lambda node=node: self._run_node(job_id, node, result, base_payload))
                        )
                    )
                wave_outcomes = await asyncio.gather(*tasks)

                for outcome in wave_outcomes:
                    running.discard(outcome.node_id)
                    result.outcomes[outcome.node_id] = outcome
                    if outcome.status == TaskStatus.COMPLETED:
                        completed.add(outcome.node_id)
                    elif outcome.status == TaskStatus.FAILED:
                        failed.add(outcome.node_id)
                        self._mark_downstream_cancelled(graph, outcome.node_id, cancelled, result)
                self._set_queue_depth(job_id, len(graph.node_ids()) - len(result.outcomes))

            self._emit(
                job_id=job_id,
                event="scheduler.job_completed",
                message="Scheduler execution finished",
                context={"failed": result.failed, "outcomes": len(result.outcomes)},
                level=LogLevel.ERROR if result.failed else LogLevel.INFO,
            )
            if self._metrics is not None:
                self._metrics.observe_latency((perf_counter() - started_at) * 1000)
            self._finish_span(
                span_id=execute_span_id,
                status="error" if result.failed else "ok",
                attributes={"outcomes": len(result.outcomes), "failed": result.failed},
            )
            return result
        except Exception as exc:
            self._finish_span(
                span_id=execute_span_id,
                status="error",
                error=str(exc),
            )
            raise

    async def _run_node(
        self,
        job_id: str,
        node: TaskNode,
        result: SchedulerResult,
        base_payload: dict[str, Any],
    ) -> TaskOutcome:
        started_at = perf_counter()
        node_span_id = self._start_span(
            correlation_id=job_id,
            name="scheduler.run_node",
            attributes={"node_id": node.node_id},
        )
        attempts = 0
        max_attempts = max(1, node.retry_limit + 1)
        input_payload = self._build_input_payload(node, result, base_payload)
        self._emit(
            job_id=job_id,
            event="scheduler.node_started",
            message=f"Node '{node.node_id}' started",
            context={"node_id": node.node_id, "retry_limit": node.retry_limit},
        )
        await self._checkpoints.save_checkpoint(
            CheckpointRecord(
                job_id=job_id,
                node_id=node.node_id,
                status=CheckpointStatus.RUNNING,
                attempt=1,
            )
        )

        while attempts < max_attempts:
            attempts += 1
            try:
                timeout_s = node.timeout_ms / 1000
                output = await asyncio.wait_for(node.handler(dict(input_payload)), timeout=timeout_s)
                await self._checkpoints.save_checkpoint(
                    CheckpointRecord(
                        job_id=job_id,
                        node_id=node.node_id,
                        status=CheckpointStatus.COMPLETED,
                        attempt=attempts,
                        payload=output,
                    )
                )
                self._emit(
                    job_id=job_id,
                    event="scheduler.node_completed",
                    message=f"Node '{node.node_id}' completed",
                    context={"node_id": node.node_id, "attempts": attempts},
                )
                if self._metrics is not None:
                    self._metrics.inc("scheduler.node.success")
                    self._metrics.observe_latency((perf_counter() - started_at) * 1000)
                self._finish_span(
                    span_id=node_span_id,
                    status="ok",
                    attributes={"node_id": node.node_id, "attempts": attempts},
                )
                return TaskOutcome(
                    node_id=node.node_id,
                    status=TaskStatus.COMPLETED,
                    output=output,
                    attempts=attempts,
                )
            except TimeoutError:
                reason = "TASK_TIMEOUT"
                message = f"Task '{node.node_id}' timed out"
            except Exception as exc:  # pragma: no cover - defensive path
                reason = "TASK_EXECUTION_ERROR"
                message = str(exc)

            if attempts >= max_attempts:
                await self._checkpoints.save_checkpoint(
                    CheckpointRecord(
                        job_id=job_id,
                        node_id=node.node_id,
                        status=CheckpointStatus.FAILED,
                        attempt=attempts,
                        reason_code=reason,
                    )
                )
                self._emit(
                    job_id=job_id,
                    event="scheduler.node_failed",
                    message=f"Node '{node.node_id}' failed",
                    context={"node_id": node.node_id, "reason_code": reason, "attempts": attempts},
                    level=LogLevel.ERROR,
                )
                if self._metrics is not None:
                    self._metrics.inc("scheduler.node.failure")
                    self._metrics.observe_latency((perf_counter() - started_at) * 1000)
                self._finish_span(
                    span_id=node_span_id,
                    status="error",
                    attributes={"node_id": node.node_id, "attempts": attempts, "reason_code": reason},
                    error=message,
                )
                return TaskOutcome(
                    node_id=node.node_id,
                    status=TaskStatus.FAILED,
                    reason_code=reason,
                    error_message=message,
                    attempts=attempts,
                )
            if self._metrics is not None:
                self._metrics.inc("scheduler.node.retries")
            self._emit(
                job_id=job_id,
                event="scheduler.node_retry",
                message=f"Retrying node '{node.node_id}'",
                context={"node_id": node.node_id, "attempt": attempts + 1, "max_attempts": max_attempts},
                level=LogLevel.WARNING,
            )
            await asyncio.sleep(self._retry_policy.delay_seconds(attempts))

        raise AssertionError("unreachable: _run_node exited retry loop without return")  # pragma: no cover

    def _build_input_payload(
        self,
        node: TaskNode,
        result: SchedulerResult,
        base_payload: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(base_payload)
        dependencies: dict[str, Any] = {}
        for dep in node.depends_on:
            dep_outcome = result.outcomes.get(dep)
            if dep_outcome and dep_outcome.status == TaskStatus.COMPLETED:
                dependencies[dep] = dep_outcome.output
        payload["dependencies"] = dependencies
        payload["node_id"] = node.node_id
        payload["job_id"] = result.job_id
        return payload

    def _mark_downstream_cancelled(
        self,
        graph: TaskGraph,
        failed_node_id: str,
        cancelled: set[str],
        result: SchedulerResult,
    ) -> None:
        pending_ids = set(graph.node_ids()) - set(result.outcomes.keys()) - cancelled
        changed = True
        while changed:
            changed = False
            for node_id in list(pending_ids):
                node = graph.get_node(node_id)
                if failed_node_id in node.depends_on or any(dep in cancelled for dep in node.depends_on):
                    cancelled.add(node_id)
                    result.outcomes[node_id] = TaskOutcome(
                        node_id=node_id,
                        status=TaskStatus.CANCELLED,
                        reason_code="UPSTREAM_FAILED",
                    )
                    self._emit(
                        job_id=result.job_id,
                        event="scheduler.node_cancelled",
                        message=f"Node '{node_id}' cancelled due to upstream failure",
                        context={"node_id": node_id, "failed_upstream": failed_node_id},
                        level=LogLevel.WARNING,
                    )
                    pending_ids.remove(node_id)
                    changed = True

    def _emit(
        self,
        job_id: str,
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
                correlation_id=job_id,
                context=context,
            )
        if self._timeline is not None:
            self._timeline.append(correlation_id=job_id, event=event, payload=context)

    def _set_queue_depth(self, job_id: str, queue_depth: int) -> None:
        if self._metrics is not None:
            self._metrics.set_gauge("scheduler.queue_depth", float(max(queue_depth, 0)))
        self._emit(
            job_id=job_id,
            event="scheduler.queue_depth",
            message="Updated scheduler queue depth",
            context={"queue_depth": max(queue_depth, 0)},
            level=LogLevel.DEBUG,
        )

    def _start_span(
        self,
        correlation_id: str,
        name: str,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        if self._tracer is None:
            return ""
        return self._tracer.start_span(
            correlation_id=correlation_id,
            name=name,
            parent_span_id=parent_span_id,
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


def _task_status_from_checkpoint(status: CheckpointStatus) -> TaskStatus:
    mapping = {
        CheckpointStatus.PENDING: TaskStatus.PENDING,
        CheckpointStatus.RUNNING: TaskStatus.RUNNING,
        CheckpointStatus.COMPLETED: TaskStatus.COMPLETED,
        CheckpointStatus.FAILED: TaskStatus.FAILED,
        CheckpointStatus.CANCELLED: TaskStatus.CANCELLED,
    }
    return mapping[status]
