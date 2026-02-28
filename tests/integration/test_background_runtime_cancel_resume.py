"""
File: test_background_runtime_cancel_resume.py
Path: tests/integration/test_background_runtime_cancel_resume.py
Role: Integration tests for background runtime cancel and resume API surface.
Used By:
 - pytest
Depends On:
 - src/core/background_runtime.py
 - src/core/scheduler.py
 - src/core/checkpoint_store.py
Notes:
 - Ensures cancelled jobs can resume deterministically from checkpoints.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.core.background_runtime import BackgroundRuntime, JobStatus
from src.core.checkpoint_store import InMemoryCheckpointStore
from src.core.scheduler import TaskScheduler
from src.core.task_graph import TaskGraph, TaskNode, TaskStatus
from src.core.worker_pool import WorkerPool


async def _wait_for_status(runtime: BackgroundRuntime, job_id: str, expected: JobStatus, timeout_s: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        if runtime.get_job(job_id).status == expected:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"Job '{job_id}' did not reach status '{expected.value}' within timeout")


def test_background_runtime_cancel_then_resume_job() -> None:
    calls: dict[str, int] = {"first": 0, "second": 0}

    async def first(_: dict[str, Any]) -> dict[str, Any]:
        calls["first"] += 1
        await asyncio.sleep(0.2)
        return {"value": 3}

    async def second(payload: dict[str, Any]) -> dict[str, Any]:
        calls["second"] += 1
        return {"value": payload["dependencies"]["first"]["value"] + 2}

    async def scenario() -> None:
        graph = TaskGraph(
            [
                TaskNode(node_id="first", handler=first),
                TaskNode(node_id="second", handler=second, depends_on=["first"]),
            ]
        )
        runtime = BackgroundRuntime(
            scheduler=TaskScheduler(
                worker_pool=WorkerPool(max_concurrency=1),
                checkpoint_store=InMemoryCheckpointStore(),
            )
        )

        job_id = runtime.submit(graph=graph, payload={"seed": "x"}, job_id="job_cancel_resume")
        await _wait_for_status(runtime, job_id, JobStatus.RUNNING)
        assert runtime.cancel_job(job_id) is True
        await _wait_for_status(runtime, job_id, JobStatus.CANCELLED)

        resumed_job_id = runtime.resume_job(job_id)
        assert resumed_job_id == job_id
        await _wait_for_status(runtime, job_id, JobStatus.COMPLETED)

        job = runtime.get_job(job_id)
        assert job.result is not None
        assert job.result.outcomes["first"].status == TaskStatus.COMPLETED
        assert job.result.outcomes["second"].status == TaskStatus.COMPLETED
        assert job.result.outcomes["second"].output["value"] == 5

    asyncio.run(scenario())
    assert calls["first"] >= 1
    assert calls["second"] == 1


def test_background_runtime_cancel_unknown_job_returns_false() -> None:
    runtime = BackgroundRuntime(
        scheduler=TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
    )
    assert runtime.cancel_job("missing-job") is False
