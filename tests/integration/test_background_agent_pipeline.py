"""
File: test_background_agent_pipeline.py
Path: tests/integration/test_background_agent_pipeline.py
Role: End-to-end integration test for host-driven background pipeline execution and observability evidence.
Used By:
 - pytest
Depends On:
 - src/integration/host_adapter.py
 - src/core/orchestrator.py
 - src/core/background_runtime.py
 - src/core/scheduler.py
 - src/tools/executor.py
 - src/policies/middleware.py
 - src/observability/*
Notes:
 - Validates one vertical slice from host input to background completion with deterministic tool execution.
"""

from __future__ import annotations

import asyncio

from src.core.background_runtime import BackgroundRuntime, JobStatus
from src.core.checkpoint_store import InMemoryCheckpointStore
from src.core.orchestrator import Orchestrator
from src.core.scheduler import TaskScheduler
from src.core.session_context import SessionContext
from src.core.task_graph import TaskGraph, TaskNode, TaskStatus
from src.core.worker_pool import WorkerPool
from src.integration.host_adapter import OrchestratorHostAdapter
from src.observability.logging import StructuredLogger
from src.observability.metrics import RuntimeMetrics
from src.observability.timeline import RuntimeTimeline
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.schemas.events import RuntimeEventType
from src.schemas.tool_io import RiskTier, ToolCallContext, ToolStatus
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


async def _wait_for_status(runtime: BackgroundRuntime, job_id: str, statuses: set[JobStatus], timeout_s: float = 2.0) -> JobStatus:
    elapsed = 0.0
    step = 0.01
    while elapsed < timeout_s:
        status = runtime.get_job(job_id).status
        if status in statuses:
            return status
        await asyncio.sleep(step)
        elapsed += step
    return runtime.get_job(job_id).status


def test_background_agent_pipeline_end_to_end() -> None:
    def summarize_turn(text: str) -> dict[str, int | str]:
        return {"normalized": text.strip().lower(), "length": len(text.strip())}

    async def scenario() -> None:
        logger = StructuredLogger()
        metrics = RuntimeMetrics()
        timeline = RuntimeTimeline()

        registry = ToolRegistry()
        registry.register(
            ToolDescriptor(
                name="summarize_turn",
                handler=summarize_turn,
                metadata={"required_args": ["text"]},
            )
        )
        policy = DeterministicFirstPolicyMiddleware()
        executor = DeterministicToolExecutor(registry=registry, policy=policy, metrics=metrics)

        orchestrator = Orchestrator(
            runtime_adapter=OpenAIAgentsRuntimeAdapter(),
            policy_middleware=policy,
            tool_executor=executor,
        )
        host = OrchestratorHostAdapter(orchestrator=orchestrator)
        session = SessionContext(
            session_id="sess_bg_e2e",
            run_id="run_bg_e2e",
            job_id="job_bg_e2e",
            task_id="task_bg_e2e",
            agent_id="agent_bg_e2e",
            provider_id="openai",
            correlation_id="corr_bg_e2e",
            metadata={"channel": "integration"},
        )

        host_events = []
        async for event in host.submit_turn(session=session, user_input="  Hello Background Pipeline  "):
            host_events.append(event)

        assert RuntimeEventType.OUTPUT_DELTA in {event.event_type for event in host_events}
        assert RuntimeEventType.RUN_COMPLETE in {event.event_type for event in host_events}

        scheduler = TaskScheduler(
            worker_pool=WorkerPool(max_concurrency=2),
            checkpoint_store=InMemoryCheckpointStore(),
            logger=logger,
            metrics=metrics,
            timeline=timeline,
        )
        runtime = BackgroundRuntime(
            scheduler=scheduler,
            logger=logger,
            metrics=metrics,
            timeline=timeline,
        )

        async def prepare(payload: dict) -> dict:
            return {
                "prepared_text": str(payload["host_input"]).strip(),
                "events_seen": int(payload["host_event_count"]),
            }

        async def enrich_with_tool(payload: dict) -> dict:
            prepared = payload["dependencies"]["prepare"]["prepared_text"]
            call = ToolCallContext(
                schema_version="1.0",
                call_id=f"call_{payload['job_id']}_summary",
                session_id="sess_bg_e2e",
                run_id="run_bg_e2e",
                job_id=str(payload["job_id"]),
                task_id="task_enrich_a",
                agent_id="agent_tools",
                provider_id="openai",
                tool_name="summarize_turn",
                arguments={"text": prepared},
                risk_tier=RiskTier.HIGH,
                is_state_changing=True,
            )
            tool_result = executor.execute(call)
            assert tool_result.status == ToolStatus.SUCCESS
            return {
                "summary": tool_result.result["value"],
                "policy_reason": tool_result.audit.decision_reason_code,
            }

        async def enrich_metadata(payload: dict) -> dict:
            prepared = payload["dependencies"]["prepare"]
            return {"echo_events_seen": prepared["events_seen"]}

        async def finalize(payload: dict) -> dict:
            from_tool = payload["dependencies"]["enrich_a"]["summary"]
            from_meta = payload["dependencies"]["enrich_b"]["echo_events_seen"]
            return {"normalized": from_tool["normalized"], "length": from_tool["length"], "events_seen": from_meta}

        graph = TaskGraph(
            [
                TaskNode(node_id="prepare", handler=prepare),
                TaskNode(node_id="enrich_a", handler=enrich_with_tool, depends_on=["prepare"]),
                TaskNode(node_id="enrich_b", handler=enrich_metadata, depends_on=["prepare"]),
                TaskNode(node_id="finalize", handler=finalize, depends_on=["enrich_a", "enrich_b"]),
            ]
        )

        job_id = runtime.submit(
            graph=graph,
            payload={"host_input": "  Hello Background Pipeline  ", "host_event_count": len(host_events)},
            job_id="job_bg_pipeline",
        )

        final_status = await _wait_for_status(runtime, job_id, {JobStatus.COMPLETED, JobStatus.FAILED}, timeout_s=3.0)
        assert final_status == JobStatus.COMPLETED

        job = runtime.get_job(job_id)
        assert job.result is not None
        assert job.result.outcomes["finalize"].status == TaskStatus.COMPLETED
        assert job.result.outcomes["finalize"].output == {
            "normalized": "hello background pipeline",
            "length": 25,
            "events_seen": len(host_events),
        }
        assert job.result.outcomes["enrich_a"].output["policy_reason"] == "RISK_WRITE_REQUIRES_DETERMINISTIC"

        assert metrics.counters.get("background.job.submitted", 0) >= 1
        assert metrics.counters.get("background.job.completed", 0) >= 1
        assert metrics.counters.get("scheduler.node.success", 0) >= 4
        assert metrics.counters.get("tool.call.success", 0) >= 1

        timeline_events = [entry.event for entry in timeline.entries_for(job_id)]
        assert "background.job_submitted" in timeline_events
        assert "scheduler.job_started" in timeline_events
        assert "scheduler.job_completed" in timeline_events
        assert "background.job_finished" in timeline_events

        log_events = [record.event for record in logger.records() if record.correlation_id == job_id]
        assert "background.job_submitted" in log_events
        assert "scheduler.node_completed" in log_events
        assert "background.job_finished" in log_events

    asyncio.run(scenario())
