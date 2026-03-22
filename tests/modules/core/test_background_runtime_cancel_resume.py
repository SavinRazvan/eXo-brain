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

from src.core.agent_scaler import AgentScaler, AgentScalerConfig
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


def test_background_runtime_scales_up_worker_pool_when_backlog_grows() -> None:
    gate = asyncio.Event()

    async def slow_node(_: dict) -> dict:
        await gate.wait()
        return {"ok": True}

    async def scenario() -> None:
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        scaler = AgentScaler(
            AgentScalerConfig(
                enabled=True,
                min_concurrency=1,
                max_concurrency=3,
                scale_up_backlog_threshold=1,
                scale_up_step=1,
                backpressure_backlog_threshold=50,
            )
        )
        runtime = BackgroundRuntime(scheduler=scheduler, agent_scaler=scaler)
        graph = TaskGraph([TaskNode(node_id="n1", handler=slow_node)])

        first = runtime.submit(graph=graph, payload={"tenant_id": "t1"})
        second = runtime.submit(graph=graph, payload={"tenant_id": "t1"})
        assert first != second
        assert scheduler.worker_pool_concurrency == 2
        gate.set()
        await _wait_for_status(runtime, first, {JobStatus.COMPLETED, JobStatus.FAILED}, timeout_s=1.5)
        await _wait_for_status(runtime, second, {JobStatus.COMPLETED, JobStatus.FAILED}, timeout_s=1.5)

    asyncio.run(scenario())


def test_background_runtime_get_job_raises_keyerror_for_unknown_id() -> None:
    scheduler = TaskScheduler(
        worker_pool=WorkerPool(max_concurrency=1),
        checkpoint_store=InMemoryCheckpointStore(),
    )
    runtime = BackgroundRuntime(scheduler=scheduler)
    try:
        runtime.get_job("missing-job")
        raise AssertionError("expected KeyError")
    except KeyError as exc:
        assert "missing-job" in str(exc)


def test_background_runtime_cancel_raises_keyerror_for_unknown_job() -> None:
    scheduler = TaskScheduler(
        worker_pool=WorkerPool(max_concurrency=1),
        checkpoint_store=InMemoryCheckpointStore(),
    )
    runtime = BackgroundRuntime(scheduler=scheduler)
    try:
        runtime.cancel_job("missing-job")
        raise AssertionError("expected KeyError")
    except KeyError as exc:
        assert "missing-job" in str(exc)


def test_background_runtime_cancel_returns_false_for_completed_job() -> None:
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
        await _wait_for_status(runtime, job_id, {JobStatus.COMPLETED}, timeout_s=1.0)
        assert runtime.cancel_job(job_id) is False

    asyncio.run(scenario())


def test_background_runtime_cancel_returns_false_when_task_handle_missing() -> None:
    gate = asyncio.Event()

    async def slow(_: dict) -> dict:
        await gate.wait()
        return {"ok": True}

    async def scenario() -> None:
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        runtime = BackgroundRuntime(scheduler=scheduler)
        graph = TaskGraph([TaskNode(node_id="n1", handler=slow)])
        job_id = runtime.submit(graph=graph, payload={"tenant_id": "t1"})
        await asyncio.sleep(0.02)
        runtime._job_tasks.pop(job_id, None)
        assert runtime.cancel_job(job_id) is False
        gate.set()

    asyncio.run(scenario())


def test_background_runtime_resume_raises_keyerror_for_unknown_job() -> None:
    scheduler = TaskScheduler(
        worker_pool=WorkerPool(max_concurrency=1),
        checkpoint_store=InMemoryCheckpointStore(),
    )
    runtime = BackgroundRuntime(scheduler=scheduler)
    try:
        runtime.resume_job("missing-job")
        raise AssertionError("expected KeyError")
    except KeyError as exc:
        assert "missing-job" in str(exc)


def test_background_runtime_resume_rejects_when_graph_metadata_invalid() -> None:
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
        await _wait_for_status(runtime, job_id, {JobStatus.COMPLETED}, timeout_s=1.0)
        job = runtime.get_job(job_id)
        job.status = JobStatus.FAILED
        job.metadata["graph"] = "not-a-graph"
        try:
            runtime.resume_job(job_id)
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert "graph metadata" in str(exc).lower()

    asyncio.run(scenario())


def test_background_runtime_scaler_scale_up_increments_metrics() -> None:
    gate = asyncio.Event()

    async def slow_node(_: dict) -> dict:
        await gate.wait()
        return {"ok": True}

    async def scenario() -> None:
        class _Metrics:
            def __init__(self) -> None:
                self.incs: list[str] = []
                self.gauges: list[tuple[str, float]] = []

            def inc(self, name: str) -> None:
                self.incs.append(name)

            def set_gauge(self, name: str, value: float) -> None:
                self.gauges.append((name, value))

        metrics = _Metrics()
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        scaler = AgentScaler(
            AgentScalerConfig(
                enabled=True,
                min_concurrency=1,
                max_concurrency=3,
                scale_up_backlog_threshold=1,
                scale_up_step=1,
                backpressure_backlog_threshold=50,
            )
        )
        runtime = BackgroundRuntime(scheduler=scheduler, agent_scaler=scaler, metrics=metrics)
        graph = TaskGraph([TaskNode(node_id="n1", handler=slow_node)])
        runtime.submit(graph=graph, payload={"tenant_id": "t1"})
        runtime.submit(graph=graph, payload={"tenant_id": "t1"})
        assert "background.scaler.scale_up" in metrics.incs
        assert any(name == "background.scaler.target_concurrency" for name, _ in metrics.gauges)
        gate.set()

    asyncio.run(scenario())


def test_background_runtime_backpressure_increments_metrics_when_configured() -> None:
    gate = asyncio.Event()

    async def slow_node(_: dict) -> dict:
        await gate.wait()
        return {"ok": True}

    async def scenario() -> None:
        class _Metrics:
            def __init__(self) -> None:
                self.incs: list[str] = []

            def inc(self, name: str) -> None:
                self.incs.append(name)

        metrics = _Metrics()
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        scaler = AgentScaler(
            AgentScalerConfig(
                enabled=True,
                min_concurrency=1,
                max_concurrency=1,
                scale_up_backlog_threshold=50,
                backpressure_backlog_threshold=1,
                backpressure_active_ratio_threshold=1.0,
            )
        )
        runtime = BackgroundRuntime(scheduler=scheduler, agent_scaler=scaler, metrics=metrics)
        graph = TaskGraph([TaskNode(node_id="n1", handler=slow_node)])
        runtime.submit(graph=graph, payload={"tenant_id": "t1"})
        try:
            runtime.submit(graph=graph, payload={"tenant_id": "t1"})
        except ValueError:
            pass
        assert "background.scaler.backpressure_rejected" in metrics.incs
        gate.set()

    asyncio.run(scenario())


def test_background_runtime_failed_job_increments_failed_metric() -> None:
    async def boom(_: dict) -> dict:
        raise RuntimeError("node failed")

    async def scenario() -> None:
        class _Metrics:
            def __init__(self) -> None:
                self.incs: list[str] = []

            def inc(self, name: str) -> None:
                self.incs.append(name)

        metrics = _Metrics()
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        runtime = BackgroundRuntime(scheduler=scheduler, metrics=metrics)
        graph = TaskGraph([TaskNode(node_id="n1", handler=boom, retry_limit=0)])
        job_id = runtime.submit(graph=graph)
        await _wait_for_status(runtime, job_id, {JobStatus.FAILED}, timeout_s=1.0)
        assert "background.job.failed" in metrics.incs

    asyncio.run(scenario())


def test_background_runtime_cancelled_job_increments_cancelled_metric() -> None:
    class _Metrics:
        def __init__(self) -> None:
            self.incs: list[str] = []

        def inc(self, name: str) -> None:
            self.incs.append(name)

    async def slow_node(_: dict) -> dict:
        await asyncio.sleep(0.2)
        return {"ok": True}

    async def scenario() -> None:
        metrics = _Metrics()
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        runtime = BackgroundRuntime(scheduler=scheduler, metrics=metrics)
        graph = TaskGraph([TaskNode(node_id="n1", handler=slow_node)])
        job_id = runtime.submit(graph=graph)
        await asyncio.sleep(0.03)
        assert runtime.cancel_job(job_id) is True
        await _wait_for_status(runtime, job_id, {JobStatus.CANCELLED}, timeout_s=1.0)
        assert "background.job.cancel.requested" in metrics.incs
        assert "background.job.cancelled" in metrics.incs

    asyncio.run(scenario())


def test_background_runtime_resume_increments_resume_requested_metric() -> None:
    class _Metrics:
        def __init__(self) -> None:
            self.incs: list[str] = []

        def inc(self, name: str) -> None:
            self.incs.append(name)

    async def fail_node(_: dict) -> dict:
        raise RuntimeError("planned failure")

    async def ok_node(_: dict) -> dict:
        return {"ok": True}

    async def scenario() -> None:
        metrics = _Metrics()
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        runtime = BackgroundRuntime(scheduler=scheduler, metrics=metrics)
        graph = TaskGraph([TaskNode(node_id="n1", handler=fail_node, retry_limit=0)])
        job_id = runtime.submit(graph=graph)
        await _wait_for_status(runtime, job_id, {JobStatus.FAILED}, timeout_s=1.0)
        job = runtime.get_job(job_id)
        job.metadata["graph"] = TaskGraph([TaskNode(node_id="n1", handler=ok_node)])
        runtime.resume_job(job_id)
        assert "background.job.resume.requested" in metrics.incs
        await _wait_for_status(runtime, job_id, {JobStatus.COMPLETED}, timeout_s=1.0)

    asyncio.run(scenario())


def test_background_runtime_rejects_submission_on_backpressure_threshold() -> None:
    gate = asyncio.Event()

    async def slow_node(_: dict) -> dict:
        await gate.wait()
        return {"ok": True}

    async def scenario() -> None:
        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=1),
            checkpoint_store=InMemoryCheckpointStore(),
        )
        scaler = AgentScaler(
            AgentScalerConfig(
                enabled=True,
                min_concurrency=1,
                max_concurrency=1,
                scale_up_backlog_threshold=50,
                backpressure_backlog_threshold=1,
                backpressure_active_ratio_threshold=1.0,
            )
        )
        runtime = BackgroundRuntime(scheduler=scheduler, agent_scaler=scaler)
        graph = TaskGraph([TaskNode(node_id="n1", handler=slow_node)])

        runtime.submit(graph=graph, payload={"tenant_id": "t1"})
        try:
            runtime.submit(graph=graph, payload={"tenant_id": "t1"})
            assert False, "Expected backpressure rejection"
        except ValueError as exc:
            assert "BACKPRESSURE_THRESHOLD_EXCEEDED" in str(exc)
        finally:
            gate.set()

    asyncio.run(scenario())
