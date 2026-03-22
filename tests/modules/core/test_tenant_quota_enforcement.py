"""
File: test_tenant_quota_enforcement.py
Path: tests/modules/core/test_tenant_quota_enforcement.py
Role: Integration tests for tenant quota checks in background runtime.
Used By:
 - pytest
Depends On:
 - src/core/background_runtime.py
 - src/core/scheduler.py
 - src/core/task_graph.py
 - src/core/checkpoint_store.py
 - src/core/worker_pool.py
 - src/tenancy/quotas.py
Notes:
 - Enforces deterministic quota rejection on over-limit submissions.
"""

import asyncio

import pytest

from src.core.background_runtime import BackgroundRuntime
from src.core.checkpoint_store import InMemoryCheckpointStore
from src.core.scheduler import TaskScheduler
from src.core.task_graph import TaskGraph, TaskNode
from src.core.worker_pool import WorkerPool
from src.tenancy.quotas import TenantQuotaManager


def test_background_runtime_rejects_submission_when_tenant_quota_exceeded() -> None:
    async def slow_node(_: dict) -> dict:
        await asyncio.sleep(0.2)
        return {"ok": True}

    async def scenario() -> None:
        scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=1), checkpoint_store=InMemoryCheckpointStore())
        runtime = BackgroundRuntime(
            scheduler=scheduler,
            tenant_quota_manager=TenantQuotaManager(max_active_jobs_per_tenant=1, hard_enforcement=True),
        )
        graph = TaskGraph([TaskNode(node_id="n1", handler=slow_node)])
        runtime.submit(graph=graph, payload={"tenant_id": "tenant_q"})
        try:
            runtime.submit(graph=graph, payload={"tenant_id": "tenant_q"})
            assert False, "Expected quota enforcement ValueError"
        except ValueError as exc:
            assert "TENANT_QUOTA_EXCEEDED" in str(exc)

    asyncio.run(scenario())


def test_background_runtime_allows_new_submission_after_completion() -> None:
    async def quick_node(_: dict) -> dict:
        await asyncio.sleep(0.02)
        return {"ok": True}

    async def scenario() -> None:
        scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=1), checkpoint_store=InMemoryCheckpointStore())
        runtime = BackgroundRuntime(
            scheduler=scheduler,
            tenant_quota_manager=TenantQuotaManager(max_active_jobs_per_tenant=1, hard_enforcement=True),
        )
        graph = TaskGraph([TaskNode(node_id="n1", handler=quick_node)])

        async def wait_terminal(job_id: str) -> None:
            while runtime.get_job(job_id).status.value in {"pending", "running"}:
                await asyncio.sleep(0.01)

        first_job = runtime.submit(graph=graph, payload={"tenant_id": "tenant_q2"})
        await wait_terminal(first_job)
        second_job = runtime.submit(graph=graph, payload={"tenant_id": "tenant_q2"})
        await wait_terminal(second_job)
        assert runtime.get_job(second_job).status.value == "completed"

    asyncio.run(scenario())


def test_tenant_quota_manager_soft_enforcement_returns_reason() -> None:
    manager = TenantQuotaManager(max_active_jobs_per_tenant=1, hard_enforcement=False)
    decision = manager.check_submission(tenant_id="tenant_soft", active_jobs=1)
    assert decision.allowed is True
    assert decision.reason_code == "TENANT_QUOTA_SOFT_LIMIT"


def test_tenant_quota_manager_set_limit_rejects_negative() -> None:
    manager = TenantQuotaManager(max_active_jobs_per_tenant=2, hard_enforcement=True)
    with pytest.raises(ValueError, match="max_active_jobs"):
        manager.set_limit(-1)


def test_tenant_quota_manager_limit_update_applies_on_next_check() -> None:
    manager = TenantQuotaManager(max_active_jobs_per_tenant=2, hard_enforcement=True)
    assert manager.check_submission(tenant_id="tenant_limit", active_jobs=1).allowed is True
    manager.set_limit(1)
    decision = manager.check_submission(tenant_id="tenant_limit", active_jobs=1)
    assert decision.allowed is False
    assert decision.reason_code == "TENANT_QUOTA_EXCEEDED"

