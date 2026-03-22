"""
File: test_runtime_adapter_contract.py
Path: tests/modules/runtime/test_runtime_adapter_contract.py
Role: Contract tests for runtime adapters.
Used By:
 - pytest
Depends On:
 - src/runtime/openai_agents_runtime.py
 - src/runtime/runtime_adapter.py
Notes:
 - Ensures adapters implement required interface behavior.
"""

import asyncio
from collections.abc import AsyncIterator

from src.runtime.custom_runtime import CustomRuntimeAdapter
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.runtime.openai_compatible_runtime import OpenAICompatibleRuntimeAdapter
from src.runtime.runtime_adapter import RuntimeAdapter, SessionHandle
from src.schemas.events import RuntimeEventType
from src.schemas.tool_io import ToolResult


def test_openai_adapter_implements_runtime_interface() -> None:
    adapter = OpenAIAgentsRuntimeAdapter()
    assert isinstance(adapter, RuntimeAdapter)


def test_openai_adapter_contract_methods_work() -> None:
    adapter = OpenAIAgentsRuntimeAdapter()

    async def _run() -> None:
        session = await adapter.start_session("sess_contract", metadata={"source": "test"})
        assert session.session_id == "sess_contract"
        assert adapter.get_capabilities().provider_id == "openai"
        assert (await adapter.healthcheck()).state.value == "healthy"

        stream = adapter.run_turn("sess_contract", "hello", {"run_id": "run_contract"})
        assert isinstance(stream, AsyncIterator)

    asyncio.run(_run())


def test_openai_compatible_adapter_contract_methods_work() -> None:
    adapter = OpenAICompatibleRuntimeAdapter()

    async def _run() -> None:
        session = await adapter.start_session("sess_compatible", metadata={"source": "test"})
        assert session.provider_id == "openai_compatible"
        assert adapter.get_capabilities().supports_openai_compatible_api is True
        assert (await adapter.healthcheck()).state.value == "healthy"

        stream = adapter.run_turn("sess_compatible", "hello", {"run_id": "run_compatible"})
        assert isinstance(stream, AsyncIterator)

    asyncio.run(_run())


def test_custom_adapter_contract_methods_work() -> None:
    adapter = CustomRuntimeAdapter()

    async def _run() -> None:
        session = await adapter.start_session("sess_custom", metadata={"source": "test"})
        assert session.provider_id == "custom"
        assert adapter.get_capabilities().provider_id == "custom"
        assert (await adapter.healthcheck()).state.value == "healthy"

        stream = adapter.run_turn("sess_custom", "hello", {"run_id": "run_custom"})
        assert isinstance(stream, AsyncIterator)

    asyncio.run(_run())


async def _collect_submit_events(adapter, tool_results) -> list:
    out = []
    async for event in adapter.submit_tool_results("s1", "r1", tool_results=tool_results):  # type: ignore[arg-type]
        out.append(event)
    return out


def test_custom_adapter_submit_tool_results_rejects_non_list_payload() -> None:
    adapter = CustomRuntimeAdapter()

    async def _run() -> None:
        events = await _collect_submit_events(adapter, tool_results="not-a-list")  # type: ignore[arg-type]
        assert events
        assert events[0].event_type == RuntimeEventType.ERROR

    asyncio.run(_run())


def test_openai_compatible_adapter_submit_tool_results_rejects_non_list_payload() -> None:
    adapter = OpenAICompatibleRuntimeAdapter()

    async def _run() -> None:
        events = await _collect_submit_events(adapter, tool_results={})  # type: ignore[arg-type]
        assert events
        assert events[0].event_type == RuntimeEventType.ERROR

    asyncio.run(_run())


def test_custom_adapter_submit_tool_results_accepts_empty_list() -> None:
    adapter = CustomRuntimeAdapter()

    async def _run() -> None:
        events = await _collect_submit_events(adapter, tool_results=[])
        assert len(events) == 1
        assert events[0].event_type == RuntimeEventType.RUN_COMPLETE

    asyncio.run(_run())


def test_openai_compatible_adapter_submit_tool_results_accepts_empty_list() -> None:
    adapter = OpenAICompatibleRuntimeAdapter()

    async def _run() -> None:
        events = await _collect_submit_events(adapter, tool_results=[])
        assert len(events) == 1
        assert events[0].event_type == RuntimeEventType.RUN_COMPLETE

    asyncio.run(_run())


def test_runtime_adapters_normalize_turn_errors_for_invalid_user_input() -> None:
    adapters = (
        OpenAIAgentsRuntimeAdapter(),
        OpenAICompatibleRuntimeAdapter(),
        CustomRuntimeAdapter(),
    )

    async def _run() -> None:
        for adapter in adapters:
            await adapter.start_session("sess_bad_turn", metadata={"source": "test"})
            events = [
                event
                async for event in adapter.run_turn(
                    "sess_bad_turn",
                    {"text": "hello"},  # type: ignore[arg-type]
                    {"run_id": "run_bad_turn"},
                )
            ]
            assert events
            assert events[-1].event_type == RuntimeEventType.ERROR
            assert events[-1].payload.get("code") == "RUNTIME_TURN_ERROR"

    asyncio.run(_run())


def test_runtime_adapters_normalize_submit_tool_result_errors() -> None:
    adapters = (
        OpenAIAgentsRuntimeAdapter(),
        OpenAICompatibleRuntimeAdapter(),
        CustomRuntimeAdapter(),
    )

    async def _run() -> None:
        for adapter in adapters:
            await adapter.start_session("sess_bad_result", metadata={"source": "test"})
            events = [event async for event in adapter.submit_tool_results("sess_bad_result", "run_bad_result", None)]  # type: ignore[arg-type]
            assert events
            assert events[-1].event_type == RuntimeEventType.ERROR
            assert events[-1].payload.get("code") == "RUNTIME_TOOL_RESULT_ERROR"

    asyncio.run(_run())


def test_openai_agents_adapter_normalizes_malformed_planned_tool_call() -> None:
    adapter = OpenAIAgentsRuntimeAdapter()

    async def _run() -> None:
        await adapter.start_session("sess_bad_planned_call", metadata={"source": "test"})
        events = [
            event
            async for event in adapter.run_turn(
                "sess_bad_planned_call",
                "hello",
                {"run_id": "run_bad_planned_call", "planned_tool_call": {"arguments": {"x": 1}}},
            )
        ]
        assert events[-1].event_type == RuntimeEventType.ERROR
        assert events[-1].payload.get("code") == "RUNTIME_TURN_ERROR"

    asyncio.run(_run())


def test_runtime_adapter_abstract_method_bodies_raise_not_implemented() -> None:
    class _AbstractBodyProbe(RuntimeAdapter):
        async def start_session(self, session_id: str, metadata: dict | None = None) -> SessionHandle:
            return await RuntimeAdapter.start_session(self, session_id, metadata)

        async def run_turn(self, session_id: str, user_input: str, context: dict) -> AsyncIterator:
            return await RuntimeAdapter.run_turn(self, session_id, user_input, context)

        async def submit_tool_results(
            self,
            session_id: str,
            run_id: str,
            tool_results: list[ToolResult],
        ) -> AsyncIterator:
            return await RuntimeAdapter.submit_tool_results(self, session_id, run_id, tool_results)

        def get_capabilities(self):  # type: ignore[override]
            return RuntimeAdapter.get_capabilities(self)

        async def healthcheck(self):
            return await RuntimeAdapter.healthcheck(self)

    adapter = _AbstractBodyProbe()

    async def _run() -> None:
        try:
            await adapter.start_session("sess_probe", metadata={})
            assert False, "Expected NotImplementedError for start_session body"
        except NotImplementedError:
            pass

        try:
            await adapter.run_turn("sess_probe", "hello", {})
            assert False, "Expected NotImplementedError for run_turn body"
        except NotImplementedError:
            pass

        try:
            await adapter.submit_tool_results("sess_probe", "run_probe", [])
            assert False, "Expected NotImplementedError for submit_tool_results body"
        except NotImplementedError:
            pass

        try:
            adapter.get_capabilities()
            assert False, "Expected NotImplementedError for get_capabilities body"
        except NotImplementedError:
            pass

        try:
            await adapter.healthcheck()
            assert False, "Expected NotImplementedError for healthcheck body"
        except NotImplementedError:
            pass

    asyncio.run(_run())
