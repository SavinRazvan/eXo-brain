"""
File: test_orchestrator_turn.py
Path: tests/modules/core/test_orchestrator_turn.py
Role: Integration test for one-turn orchestrator flow with deterministic tool execution.
Used By:
 - pytest
Depends On:
 - src/core/orchestrator.py
 - src/runtime/openai_agents_runtime.py
 - src/policies/middleware.py
 - src/tools/registry.py
 - src/tools/executor.py
Notes:
 - Validates tool-intent handoff through deterministic path and submit_tool_results.
"""

from src.core.orchestrator import Orchestrator
from src.policies.middleware import DeterministicFirstPolicyMiddleware, PolicyMiddleware
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.schemas.events import RuntimeEventType
from tests.constants import BYOC_WORKER_JWT_SECRET
from src.schemas.tool_io import (
    PolicyAction,
    PolicyDecision,
    RiskTier,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
    ToolStatus,
)
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry
from src.tools.byoc.connector_runtime import TenantByocConnectorRuntime
from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolResultEnvelope


async def _collect_events(orchestrator: Orchestrator, session_id: str, context: dict) -> list:
    events = []
    async for event in orchestrator.run_turn(session_id=session_id, user_input="execute", context=context):
        events.append(event)
    return events


def test_orchestrator_executes_high_risk_tool_deterministically() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="multiply",
            handler=lambda a, b: a * b,
            risk_tier=RiskTier.HIGH,
            is_state_changing=True,
        )
    )

    orchestrator = Orchestrator(
        runtime_adapter=OpenAIAgentsRuntimeAdapter(),
        policy_middleware=DeterministicFirstPolicyMiddleware(),
        tool_executor=DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware()),
    )

    context = {
        "run_id": "run_integration",
        "job_id": "job_integration",
        "task_id": "task_integration",
        "agent_id": "agent_executor",
        "planned_tool_call": {
            "call_id": "tc_integration",
            "tool_name": "multiply",
            "arguments": {"a": 4, "b": 5},
            "risk_tier": RiskTier.HIGH.value,
            "is_state_changing": True,
        },
    }

    import asyncio

    events = asyncio.run(_collect_events(orchestrator, session_id="sess_integration", context=context))
    event_types = [event.event_type for event in events]
    assert RuntimeEventType.OUTPUT_DELTA in event_types
    assert RuntimeEventType.RUN_COMPLETE in event_types


def test_orchestrator_emits_tool_progress_state_machine_for_deterministic_calls() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="add",
            handler=lambda a, b: a + b,
            risk_tier=RiskTier.HIGH,
            is_state_changing=True,
        )
    )

    orchestrator = Orchestrator(
        runtime_adapter=OpenAIAgentsRuntimeAdapter(),
        policy_middleware=DeterministicFirstPolicyMiddleware(),
        tool_executor=DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware()),
    )
    context = {
        "run_id": "run_progress",
        "job_id": "job_progress",
        "task_id": "task_progress",
        "agent_id": "agent_progress",
        "planned_tool_call": {
            "call_id": "tc_progress_1",
            "tool_name": "add",
            "arguments": {"a": 1, "b": 2},
                "risk_tier": RiskTier.HIGH.value,
                "is_state_changing": True,
        },
    }
    import asyncio

    events = asyncio.run(_collect_events(orchestrator, session_id="sess_progress", context=context))
    progress = [event.payload for event in events if event.event_type == RuntimeEventType.TOOL_PROGRESS]
    assert [entry["state"] for entry in progress] == ["queued", "running", "completed"]
    assert all(entry["call_id"] == "tc_progress_1" for entry in progress)
    assert all(entry["tool_name"] == "add" for entry in progress)


def test_orchestrator_emits_byoc_adapter_progress_states() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="add",
            handler=lambda a, b: a + b,
            risk_tier=RiskTier.HIGH,
            is_state_changing=True,
            timeout_ms=3000,
        )
    )
    byoc_adapter = TenantByocConnectorRuntime(worker_jwt_secret=BYOC_WORKER_JWT_SECRET)
    policy = DeterministicFirstPolicyMiddleware()
    orchestrator = Orchestrator(
        runtime_adapter=OpenAIAgentsRuntimeAdapter(),
        policy_middleware=policy,
        tool_executor=DeterministicToolExecutor(
            registry=registry,
            policy=policy,
            execution_adapter=byoc_adapter,
            enable_hosted_runtime=True,
        ),
    )
    token = byoc_adapter.issue_worker_token(tenant_id="default", worker_id="worker-progress")
    context = {
        "run_id": "run_byoc_progress",
        "job_id": "job_byoc_progress",
        "task_id": "task_byoc_progress",
        "agent_id": "agent_byoc_progress",
        "planned_tool_call": {
            "call_id": "tc_byoc_progress_1",
            "tool_name": "add",
            "arguments": {"a": 3, "b": 4},
            "risk_tier": RiskTier.HIGH.value,
            "is_state_changing": True,
        },
    }
    result_holder: dict[str, list] = {}

    def _run() -> None:
        import asyncio

        result_holder["events"] = asyncio.run(
            _collect_events(orchestrator, session_id="sess_byoc_progress", context=context)
        )

    import threading
    import time

    thread = threading.Thread(target=_run)
    thread.start()
    deadline = time.time() + 2.0
    claimed = None
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        claimed = byoc_adapter.claim_next_job(
            tenant_id="default",
            worker_token=token,
            request_nonce=f"nonce-byoc-progress-{attempt}",
        )
        if claimed is not None:
            break
        time.sleep(0.02)
    assert claimed is not None
    outcome = byoc_adapter.submit_result(
        tenant_id="default",
        worker_token=token,
        request_nonce="nonce-byoc-progress-submit-1",
        result=ByocToolResultEnvelope(
            job_id=str(claimed["job_id"]),
            tenant_id="default",
            run_id=str(claimed["run_id"]),
            call_id=str(claimed["call_id"]),
            tool_name=str(claimed["tool_name"]),
            status=ByocResultStatus.SUCCESS,
            output={"value": 7},
            idempotency_key=str(claimed["idempotency_key"]),
            lease_token=str(claimed["lease_token"]),
        ),
    )
    assert outcome.accepted is True
    thread.join(timeout=4.0)
    events = result_holder.get("events", [])
    progress = [event.payload for event in events if event.event_type == RuntimeEventType.TOOL_PROGRESS]
    assert [entry["state"] for entry in progress] == ["queued", "running", "completed"]
    assert all(entry["call_id"] == "tc_byoc_progress_1" for entry in progress)
    assert all(entry["tool_name"] == "add" for entry in progress)
    assert all(str(entry.get("job_id", "")).startswith("job_") for entry in progress)
    running = next(entry for entry in progress if entry["state"] == "running")
    assert str(running.get("lease_token", "")).startswith("lease_")
    assert str(running.get("lease_expires_at_epoch", "")).isdigit()
    assert str(running.get("claim_attempt", "")) == "1"


class OutputGuardPolicy(PolicyMiddleware):
    def __init__(self) -> None:
        self.output_calls = 0

    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        return PolicyDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="ALLOW_FOR_TEST",
            message="allowed",
            enforced_mode=ToolExecutionMode.DETERMINISTIC,
        )

    def after_tool_call(self, result: ToolResult) -> ToolResult:
        return result

    def before_output(self, output: dict[str, object]) -> dict[str, object]:
        self.output_calls += 1
        output["policy_checked"] = True
        return output


class ProviderNativePolicy(PolicyMiddleware):
    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        return PolicyDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="ALLOW_NATIVE_FOR_TEST",
            message="allowed",
            enforced_mode=ToolExecutionMode.PROVIDER_NATIVE,
        )

    def after_tool_call(self, result: ToolResult) -> ToolResult:
        return result

    def before_output(self, output: dict[str, object]) -> dict[str, object]:
        return output


class CapturingOpenAIAgentsRuntimeAdapter(OpenAIAgentsRuntimeAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.submitted_results: list[ToolResult] = []

    async def submit_tool_results(self, session_id: str, run_id: str, tool_results: list[ToolResult]):
        self.submitted_results.extend(tool_results)
        async for event in super().submit_tool_results(session_id=session_id, run_id=run_id, tool_results=tool_results):
            yield event


def test_orchestrator_runs_before_output_on_runtime_events() -> None:
    policy = OutputGuardPolicy()
    registry = ToolRegistry()
    orchestrator = Orchestrator(
        runtime_adapter=OpenAIAgentsRuntimeAdapter(),
        policy_middleware=policy,
        tool_executor=DeterministicToolExecutor(registry=registry, policy=policy),
    )
    context = {
        "run_id": "run_output_policy",
        "job_id": "job_output_policy",
        "task_id": "task_output_policy",
        "agent_id": "agent_output_policy",
    }

    import asyncio

    events = asyncio.run(_collect_events(orchestrator, session_id="sess_output_policy", context=context))
    output_events = [event for event in events if event.event_type in {RuntimeEventType.OUTPUT_DELTA, RuntimeEventType.RUN_COMPLETE}]
    assert len(output_events) == 2
    assert policy.output_calls == 2
    for event in output_events:
        assert event.payload["policy_checked"] is True


def test_orchestrator_blocks_provider_native_state_changing_with_deterministic_envelope(monkeypatch) -> None:
    adapter = CapturingOpenAIAgentsRuntimeAdapter()
    policy = ProviderNativePolicy()
    registry = ToolRegistry()
    orchestrator = Orchestrator(
        runtime_adapter=adapter,
        policy_middleware=policy,
        tool_executor=DeterministicToolExecutor(registry=registry, policy=policy),
    )
    context = {
        "run_id": "run_native_state_change_block",
        "job_id": "job_native_state_change_block",
        "task_id": "task_native_state_change_block",
        "agent_id": "agent_native_state_change_block",
        "planned_tool_call": {
            "call_id": "tc_native_state_change_block",
            "tool_name": "mutate_store",
            "arguments": {"value": 1},
            "risk_tier": RiskTier.CRITICAL.value,
            "is_state_changing": True,
        },
    }

    # Force provider-native mode selection to validate orchestrator hardening guard.
    monkeypatch.setattr("src.core.orchestrator.select_execution_mode", lambda **_: ToolExecutionMode.PROVIDER_NATIVE)

    import asyncio

    events = asyncio.run(_collect_events(orchestrator, session_id="sess_native_state_change_block", context=context))
    event_types = [event.event_type for event in events]
    assert RuntimeEventType.TOOL_INTENT not in event_types
    assert RuntimeEventType.OUTPUT_DELTA in event_types
    assert RuntimeEventType.RUN_COMPLETE in event_types

    assert len(adapter.submitted_results) == 1
    blocked = adapter.submitted_results[0]
    assert blocked.status == ToolStatus.BLOCKED
    assert blocked.execution.mode_used == ToolExecutionMode.DETERMINISTIC
    assert blocked.error.details == {"reason_code": "PROVIDER_NATIVE_STATE_CHANGE_BLOCKED"}
