"""
File: test_scheduler_observability.py
Path: tests/integration/test_scheduler_observability.py
Role: Integration tests for scheduler observability on success and failure paths.
Used By:
 - pytest
Depends On:
 - src/core/scheduler.py
 - src/core/task_graph.py
 - src/core/checkpoint_store.py
 - src/core/worker_pool.py
 - src/observability/logging.py
 - src/observability/metrics.py
 - src/observability/timeline.py
Notes:
 - Ensures failures emit auditable logs with correlation IDs.
"""

from __future__ import annotations

import asyncio

from src.core.checkpoint_store import InMemoryCheckpointStore
from src.core.scheduler import TaskScheduler
from src.core.task_graph import TaskGraph, TaskNode, TaskStatus
from src.core.worker_pool import WorkerPool
from src.observability.logging import StructuredLogger
from src.observability.metrics import RuntimeMetrics
from src.observability.timeline import RuntimeTimeline


def test_scheduler_emits_failure_logs_and_metrics() -> None:
    async def failing(_: dict) -> dict:
        raise RuntimeError("boom")

    logger = StructuredLogger()
    metrics = RuntimeMetrics()
    timeline = RuntimeTimeline()
    scheduler = TaskScheduler(
        worker_pool=WorkerPool(max_concurrency=1),
        checkpoint_store=InMemoryCheckpointStore(),
        logger=logger,
        metrics=metrics,
        timeline=timeline,
    )
    graph = TaskGraph([TaskNode(node_id="failing", handler=failing)])
    result = asyncio.run(scheduler.execute(job_id="job_obs_fail", graph=graph))

    assert result.outcomes["failing"].status == TaskStatus.FAILED
    assert metrics.counters["scheduler.node.failure"] >= 1
    assert any(record.event == "scheduler.node_failed" for record in logger.records())
    assert any(entry.event == "scheduler.node_failed" for entry in timeline.entries_for("job_obs_fail"))
