"""
File: test_openai_agents_runtime_sdk_path.py
Path: tests/modules/runtime/test_openai_agents_runtime_sdk_path.py
Role: Unit tests for OpenAI adapter SDK and fallback execution branches.
Used By:
 - pytest
Depends On:
 - src/runtime/openai_agents_runtime.py
 - src/schemas/events.py
Notes:
 - Uses module doubles to cover SDK stream branches without network calls.
"""

from __future__ import annotations

import asyncio
import sys
import types

from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.schemas.events import RuntimeEventType
from src.runtime.capability_map import HealthState
from src.tools.registry import ToolRegistry


def _install_fake_agents_modules(monkeypatch) -> None:
    agents_mod = types.ModuleType("agents")
    stream_mod = types.ModuleType("agents.stream_events")
    items_mod = types.ModuleType("agents.items")

    class MessageOutputItem:
        def __init__(self, text: str) -> None:
            self.text = text

    class ToolCallItem:
        def __init__(self, call_id: str, name: str) -> None:
            self.raw_item = types.SimpleNamespace(call_id=call_id, name=name)

    class ToolCallOutputItem:
        pass

    class RunItemStreamEvent:
        def __init__(self, item) -> None:
            self.item = item

    class RawResponsesStreamEvent:
        pass

    class ItemHelpers:
        @staticmethod
        def text_message_output(item: MessageOutputItem) -> str:
            return item.text

    class Agent:
        def __init__(self, name: str, instructions: str, model: str, tools) -> None:
            self.name = name
            self.instructions = instructions
            self.model = model
            self.tools = tools

    class FunctionTool:  # pragma: no cover - import shim for src.runtime.tool_wiring
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

    class _RunResult:
        def __init__(self) -> None:
            self.final_output = "final answer"

        async def stream_events(self):
            yield RunItemStreamEvent(MessageOutputItem("hello from sdk"))
            yield RunItemStreamEvent(ToolCallItem("tc_sdk", "math_tool"))
            yield RunItemStreamEvent(ToolCallOutputItem())

    class Runner:
        @staticmethod
        def run_streamed(agent: Agent, user_input: str):
            _ = (agent, user_input)
            return _RunResult()

    agents_mod.Agent = Agent
    agents_mod.Runner = Runner
    agents_mod.FunctionTool = FunctionTool
    stream_mod.RawResponsesStreamEvent = RawResponsesStreamEvent
    stream_mod.RunItemStreamEvent = RunItemStreamEvent
    items_mod.MessageOutputItem = MessageOutputItem
    items_mod.ToolCallItem = ToolCallItem
    items_mod.ToolCallOutputItem = ToolCallOutputItem
    items_mod.ItemHelpers = ItemHelpers

    monkeypatch.setitem(sys.modules, "agents", agents_mod)
    monkeypatch.setitem(sys.modules, "agents.stream_events", stream_mod)
    monkeypatch.setitem(sys.modules, "agents.items", items_mod)


def test_openai_adapter_sdk_branch_emits_message_tool_intent_and_completion(monkeypatch) -> None:
    _install_fake_agents_modules(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    observed = {}

    def _fake_build_agent_tools(**kwargs):
        observed.update(kwargs)
        return []

    monkeypatch.setattr("src.runtime.tool_wiring.build_agent_tools", _fake_build_agent_tools)

    adapter = OpenAIAgentsRuntimeAdapter(
        provider_id="openai-test",
        tool_registry=ToolRegistry(),
        tool_executor=object(),  # type: ignore[arg-type]
    )

    async def _run():
        await adapter.start_session(
            "sess_sdk",
            metadata={
                "agent_id": "agent_sdk",
                "instructions": "be helpful",
                "model": "gpt-4o-mini",
                "tenant_id": "tenant_sdk",
            },
        )
        return [
            event
            async for event in adapter.run_turn(
                "sess_sdk",
                "hello",
                {"run_id": "run_sdk", "correlation_id": "corr_sdk"},
            )
        ]

    events = asyncio.run(_run())
    assert [event.event_type for event in events] == [
        RuntimeEventType.OUTPUT_DELTA,
        RuntimeEventType.TOOL_INTENT,
        RuntimeEventType.RUN_COMPLETE,
    ]
    assert events[0].payload["text"] == "hello from sdk"
    assert events[1].tool_call is not None
    assert events[1].tool_call.call_id == "tc_sdk"
    assert events[1].tool_call.tool_name == "math_tool"
    assert events[2].payload["output"] == "final answer"
    assert observed["session_id"] == "sess_sdk"
    assert observed["agent_id"] == "agent_sdk"
    assert observed["provider_id"] == "openai-test"
    assert observed["tenant_id"] == "tenant_sdk"


def test_openai_adapter_falls_back_to_echo_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    adapter = OpenAIAgentsRuntimeAdapter(
        provider_id="openai-test",
        tool_registry=ToolRegistry(),
        tool_executor=object(),  # type: ignore[arg-type]
    )

    async def _run():
        await adapter.start_session("sess_echo")
        return [event async for event in adapter.run_turn("sess_echo", "ping", {"run_id": "run_echo"})]

    events = asyncio.run(_run())
    assert len(events) == 2
    assert events[0].event_type == RuntimeEventType.OUTPUT_DELTA
    assert events[0].payload["text"] == "openai-adapter-echo: ping"
    assert events[1].event_type == RuntimeEventType.RUN_COMPLETE


def test_openai_adapter_planned_tool_call_emits_tool_intent() -> None:
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")

    async def _run():
        await adapter.start_session("sess_plan")
        return [
            event
            async for event in adapter.run_turn(
                "sess_plan",
                "invoke tool",
                {
                    "run_id": "run_plan",
                    "planned_tool_call": {
                        "tool_name": "math_tool",
                        "call_id": "tc_plan",
                        "arguments": {"x": 1},
                        "risk_tier": "medium",
                        "is_state_changing": True,
                    },
                    "identity": {"subject": "user_1", "roles": ["admin"]},
                },
            )
        ]

    events = asyncio.run(_run())
    assert len(events) == 1
    assert events[0].event_type == RuntimeEventType.TOOL_INTENT
    assert events[0].tool_call is not None
    assert events[0].tool_call.call_id == "tc_plan"
    assert events[0].tool_call.tool_name == "math_tool"
    assert events[0].tool_call.arguments == {"x": 1}
    assert events[0].tool_call.identity_subject == "user_1"
    assert events[0].tool_call.identity_roles == ["admin"]


def test_openai_adapter_planned_tool_call_requires_object() -> None:
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")

    async def _run():
        await adapter.start_session("sess_bad_plan")
        return [
            event
            async for event in adapter.run_turn(
                "sess_bad_plan",
                "invoke tool",
                {"run_id": "run_bad_plan", "planned_tool_call": "not-an-object"},
            )
        ]

    events = asyncio.run(_run())
    assert events[-1].event_type == RuntimeEventType.ERROR
    assert events[-1].payload["code"] == "RUNTIME_TURN_ERROR"
    assert "planned_tool_call must be an object" in events[-1].payload["message"]


def test_openai_adapter_planned_tool_call_requires_tool_name() -> None:
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")

    async def _run():
        await adapter.start_session("sess_missing_tool_name")
        return [
            event
            async for event in adapter.run_turn(
                "sess_missing_tool_name",
                "invoke tool",
                {"run_id": "run_missing_tool_name", "planned_tool_call": {"arguments": {"x": 1}}},
            )
        ]

    events = asyncio.run(_run())
    assert events[-1].event_type == RuntimeEventType.ERROR
    assert "planned_tool_call.tool_name is required" in events[-1].payload["message"]


def test_openai_adapter_submit_tool_results_success_and_error_paths() -> None:
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")

    async def _run_success():
        await adapter.start_session("sess_results_success")
        return [
            event
            async for event in adapter.submit_tool_results(
                "sess_results_success",
                "run_results_success",
                [],
            )
        ]

    async def _run_error():
        await adapter.start_session("sess_results_error")
        return [
            event
            async for event in adapter.submit_tool_results(  # type: ignore[arg-type]
                "sess_results_error",
                "run_results_error",
                None,
            )
        ]

    success_events = asyncio.run(_run_success())
    assert [event.event_type for event in success_events] == [
        RuntimeEventType.OUTPUT_DELTA,
        RuntimeEventType.RUN_COMPLETE,
    ]
    assert success_events[1].payload["tool_results_count"] == 0

    error_events = asyncio.run(_run_error())
    assert error_events[-1].event_type == RuntimeEventType.ERROR
    assert error_events[-1].payload["code"] == "RUNTIME_TOOL_RESULT_ERROR"


def test_openai_adapter_capabilities_and_healthcheck() -> None:
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    capabilities = adapter.get_capabilities()
    assert capabilities.provider_id == "openai-test"
    assert capabilities.supports_agents_sdk_native is True
    assert capabilities.recommended_runtime_mode == "hybrid"

    health = asyncio.run(adapter.healthcheck())
    assert health.state == HealthState.HEALTHY


def test_openai_adapter_requires_string_user_input() -> None:
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")

    async def _run():
        await adapter.start_session("sess_bad_input")
        return [
            event
            async for event in adapter.run_turn(  # type: ignore[arg-type]
                "sess_bad_input",
                {"text": "hello"},
                {"run_id": "run_bad_input"},
            )
        ]

    events = asyncio.run(_run())
    assert events[-1].event_type == RuntimeEventType.ERROR
    assert events[-1].payload["code"] == "RUNTIME_TURN_ERROR"
    assert "user_input must be a string" in events[-1].payload["message"]
