"""
File: test_scheduler_checkpoint_resume.py
Path: tests/modules/core/test_scheduler_checkpoint_resume.py
Role: Integration tests for scheduler checkpoint resume and auditable failure reasons.
Used By:
 - pytest
Depends On:
 - src/core/scheduler.py
 - src/core/task_graph.py
 - src/core/worker_pool.py
 - src/core/checkpoint_store.py
Notes:
 - Confirms deterministic replay by skipping completed nodes on resume.
"""

from __future__ import annotations

import asyncio

from src.core.checkpoint_store import InMemoryCheckpointStore
from src.core.scheduler import TaskScheduler
from src.core.task_graph import TaskGraph, TaskNode, TaskStatus
from src.core.worker_pool import WorkerPool
from src.persistence.contracts import CheckpointRecord, CheckpointStatus


def test_scheduler_resume_skips_completed_nodes() -> None:
    calls = {"a": 0, "b": 0}

    async def node_a(_: dict) -> dict:
        calls["a"] += 1
        return {"a": 1}

    async def node_b(payload: dict) -> dict:
        calls["b"] += 1
        return {"b": payload["dependencies"]["a"]["a"] + 1}

    graph = TaskGraph(
        [
            TaskNode(node_id="a", handler=node_a),
            TaskNode(node_id="b", handler=node_b, depends_on=["a"]),
        ]
    )
    checkpoints = InMemoryCheckpointStore()
    scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=2), checkpoint_store=checkpoints)

    first = asyncio.run(scheduler.execute(job_id="job_resume", graph=graph))
    assert first.outcomes["a"].status == TaskStatus.COMPLETED
    assert first.outcomes["b"].status == TaskStatus.COMPLETED
    assert calls == {"a": 1, "b": 1}

    second = asyncio.run(scheduler.execute(job_id="job_resume", graph=graph, resume=True))
    assert second.outcomes["a"].status == TaskStatus.COMPLETED
    assert second.outcomes["b"].status == TaskStatus.COMPLETED
    assert calls == {"a": 1, "b": 1}


def test_scheduler_resume_retries_failed_checkpoint_nodes() -> None:
    calls = {"fragile": 0}

    async def node_recoverable(_: dict) -> dict:
        calls["fragile"] += 1
        return {"ok": True}

    async def _scenario() -> None:
        graph = TaskGraph([TaskNode(node_id="fragile", handler=node_recoverable)])
        checkpoints = InMemoryCheckpointStore()
        scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=1), checkpoint_store=checkpoints)
        await checkpoints.save_checkpoint(
            CheckpointRecord(
                job_id="job_failed_ckpt",
                node_id="fragile",
                status=CheckpointStatus.FAILED,
                attempt=1,
                reason_code="PREVIOUS_FAILURE",
                tenant_id="default",
            )
        )
        result = await scheduler.execute(job_id="job_failed_ckpt", graph=graph, resume=True)
        assert "fragile" in result.outcomes
        assert result.outcomes["fragile"].status == TaskStatus.COMPLETED
        assert calls["fragile"] == 1
        assert result.failed is False

    asyncio.run(_scenario())


def test_scheduler_execute_propagates_when_checkpoint_list_raises() -> None:
    class _BoomStore(InMemoryCheckpointStore):
        async def list_checkpoints(self, job_id: str, tenant_id: str = "default") -> list[CheckpointRecord]:
            raise RuntimeError("checkpoint store unavailable")

    async def node(_: dict) -> dict:
        return {"ok": True}

    graph = TaskGraph([TaskNode(node_id="n1", handler=node)])
    scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=1), checkpoint_store=_BoomStore())
    try:
        asyncio.run(scheduler.execute(job_id="job_boom", graph=graph, resume=True))
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "unavailable" in str(exc)


def test_scheduler_marks_timeout_with_task_timeout_reason() -> None:
    async def slow(_: dict) -> dict:
        await asyncio.sleep(0.2)
        return {"late": True}

    graph = TaskGraph([TaskNode(node_id="slow", handler=slow, timeout_ms=20, retry_limit=0)])
    checkpoints = InMemoryCheckpointStore()
    scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=1), checkpoint_store=checkpoints)
    result = asyncio.run(scheduler.execute(job_id="job_timeout", graph=graph))
    assert result.outcomes["slow"].status == TaskStatus.FAILED
    assert result.outcomes["slow"].reason_code == "TASK_TIMEOUT"


def test_scheduler_failure_emits_checkpoint_reason_code() -> None:
    async def failing(_: dict) -> dict:
        raise RuntimeError("boom")

    graph = TaskGraph([TaskNode(node_id="failing", handler=failing)])
    checkpoints = InMemoryCheckpointStore()
    scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=1), checkpoint_store=checkpoints)

    result = asyncio.run(scheduler.execute(job_id="job_fail_reason", graph=graph))
    checkpoint = asyncio.run(checkpoints.get_checkpoint("job_fail_reason", "failing"))

    assert result.outcomes["failing"].status == TaskStatus.FAILED
    assert result.outcomes["failing"].reason_code == "TASK_EXECUTION_ERROR"
    assert checkpoint is not None
    assert checkpoint.status == CheckpointStatus.FAILED
    assert checkpoint.reason_code == "TASK_EXECUTION_ERROR"
