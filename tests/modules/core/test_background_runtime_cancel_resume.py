"""
File: test_background_runtime_cancel_resume.py
Path: tests/modules/core/test_background_runtime_cancel_resume.py
Role: Integration tests for background runtime cancel/resume workflow behavior.
Used By:
 - pytest
Depends On:
 - src/core/background_runtime.py
 - src/core/scheduler.py
 - src/core/task_graph.py
 - src/core/worker_pool.py
 - src/core/checkpoint_store.py
 - src/observability/tracing.py
Notes:
 - Confirms cancelled jobs can be resumed with scheduler checkpoint semantics.
"""

from __future__ import annotations

import asyncio

from src.core.background_runtime import BackgroundRuntime, JobStatus
from src.core.checkpoint_store import InMemoryCheckpointStore
from src.core.scheduler import TaskScheduler
from src.core.task_graph import TaskGraph, TaskNode
from src.core.worker_pool import WorkerPool
from src.observability.tracing import RuntimeTracer


async def _wait_for_status(runtime: BackgroundRuntime, job_id: str, statuses: set[JobStatus], timeout_s: float = 1.0) -> JobStatus:
    elapsed = 0.0
    step = 0.01
    while elapsed < timeout_s:
        status = runtime.get_job(job_id).status
        if status in statuses:
            return status
        await asyncio.sleep(step)
        elapsed += step
    return runtime.get_job(job_id).status


def test_background_runtime_cancel_and_resume_job() -> None:
    calls = {"n1": 0}

    async def slow_node(_: dict) -> dict:
        calls["n1"] += 1
        await asyncio.sleep(0.2)
        return {"ok": True}

    async def scenario() -> None:
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        runtime = BackgroundRuntime(scheduler=scheduler)
        graph = TaskGraph([TaskNode(node_id="n1", handler=slow_node)])

        job_id = runtime.submit(graph=graph, payload={"input": "x"})
        await asyncio.sleep(0.03)

        assert runtime.cancel_job(job_id) is True
        cancelled_status = await _wait_for_status(runtime, job_id, {JobStatus.CANCELLED})
        assert cancelled_status == JobStatus.CANCELLED

        resumed_job_id = runtime.resume_job(job_id)
        assert resumed_job_id == job_id
        finished_status = await _wait_for_status(runtime, job_id, {JobStatus.COMPLETED, JobStatus.FAILED}, timeout_s=1.5)

        assert finished_status == JobStatus.COMPLETED
        assert runtime.get_job(job_id).result is not None
        assert calls["n1"] >= 1

    asyncio.run(scenario())


def test_background_runtime_rejects_resume_for_completed_job() -> None:
    async def node(_: dict) -> dict:
        return {"ok": True}

    async def scenario() -> None:
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        runtime = BackgroundRuntime(scheduler=scheduler)
        graph = TaskGraph([TaskNode(node_id="n1", handler=node)])

        job_id = runtime.submit(graph=graph)
        final_status = await _wait_for_status(runtime, job_id, {JobStatus.COMPLETED, JobStatus.FAILED}, timeout_s=1.0)
        assert final_status == JobStatus.COMPLETED

        try:
            runtime.resume_job(job_id)
            assert False, "Expected RuntimeError when resuming a completed job"
        except RuntimeError as exc:
            assert "cannot be resumed" in str(exc)

    asyncio.run(scenario())


def test_background_runtime_emits_trace_spans() -> None:
    async def node(_: dict) -> dict:
        return {"ok": True}

    async def scenario() -> None:
        tracer = RuntimeTracer()
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
            tracer=tracer,
        )
        runtime = BackgroundRuntime(scheduler=scheduler, tracer=tracer)
        graph = TaskGraph([TaskNode(node_id="n1", handler=node)])

        job_id = runtime.submit(graph=graph, job_id="job_trace")
        final_status = await _wait_for_status(runtime, job_id, {JobStatus.COMPLETED, JobStatus.FAILED}, timeout_s=1.0)
        assert final_status == JobStatus.COMPLETED

        spans = tracer.spans_for(job_id)
        assert any(span.name == "background.run_job" and span.status == "ok" for span in spans)
        assert any(span.name == "scheduler.execute" and span.status == "ok" for span in spans)
        assert any(span.name == "scheduler.run_node" and span.status == "ok" for span in spans)
        background_span = next(span for span in spans if span.name == "background.run_job")
        scheduler_span = next(span for span in spans if span.name == "scheduler.execute")
        assert scheduler_span.parent_span_id == background_span.span_id

    asyncio.run(scenario())
