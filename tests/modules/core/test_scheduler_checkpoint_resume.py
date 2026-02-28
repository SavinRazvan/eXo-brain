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
from src.persistence.contracts import CheckpointStatus


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
