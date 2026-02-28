"""
File: scheduler.py
Path: src/core/scheduler.py
Role: Executes task graphs with retries, checkpointing, and resume support.
Used By:
 - src/core/background_runtime.py
Depends On:
 - src/core/task_graph.py
 - src/core/worker_pool.py
 - src/persistence/contracts.py
Notes:
 - Scheduler stops dependents when an upstream node fails.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from src.core.task_graph import TaskGraph, TaskNode, TaskOutcome, TaskStatus
from src.core.worker_pool import WorkerPool
from src.persistence.contracts import CheckpointRecord, CheckpointStatus, CheckpointStoreContract


@dataclass(slots=True)
class SchedulerResult:
    job_id: str
    outcomes: dict[str, TaskOutcome] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return any(outcome.status == TaskStatus.FAILED for outcome in self.outcomes.values())


class TaskScheduler:
    def __init__(self, worker_pool: WorkerPool, checkpoint_store: CheckpointStoreContract) -> None:
        self._worker_pool = worker_pool
        self._checkpoints = checkpoint_store

    async def execute(
        self,
        job_id: str,
        graph: TaskGraph,
        initial_payload: dict[str, Any] | None = None,
        resume: bool = False,
    ) -> SchedulerResult:
        result = SchedulerResult(job_id=job_id)
        completed: set[str] = set()
        running: set[str] = set()
        failed: set[str] = set()
        cancelled: set[str] = set()

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

        return result

    async def _run_node(
        self,
        job_id: str,
        node: TaskNode,
        result: SchedulerResult,
        base_payload: dict[str, Any],
    ) -> TaskOutcome:
        attempts = 0
        max_attempts = max(1, node.retry_limit + 1)
        input_payload = self._build_input_payload(node, result, base_payload)
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
                return TaskOutcome(
                    node_id=node.node_id,
                    status=TaskStatus.FAILED,
                    reason_code=reason,
                    error_message=message,
                    attempts=attempts,
                )

        return TaskOutcome(node_id=node.node_id, status=TaskStatus.FAILED, reason_code="UNEXPECTED_SCHEDULER_STATE")

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
                    pending_ids.remove(node_id)
                    changed = True


def _task_status_from_checkpoint(status: CheckpointStatus) -> TaskStatus:
    mapping = {
        CheckpointStatus.PENDING: TaskStatus.PENDING,
        CheckpointStatus.RUNNING: TaskStatus.RUNNING,
        CheckpointStatus.COMPLETED: TaskStatus.COMPLETED,
        CheckpointStatus.FAILED: TaskStatus.FAILED,
        CheckpointStatus.CANCELLED: TaskStatus.CANCELLED,
    }
    return mapping[status]
