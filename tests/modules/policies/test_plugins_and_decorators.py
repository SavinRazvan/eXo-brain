"""
File: test_plugins_and_decorators.py
Path: tests/modules/policies/test_plugins_and_decorators.py
Role: Unit tests for plugin lifecycle manager and execution decorators integration.
Used By:
 - pytest
Depends On:
 - src/tools/plugins/plugin_manager.py
 - src/tools/plugins/plugin_contract.py
 - src/tools/executor.py
 - src/tools/registry.py
 - src/policies/middleware.py
 - src/schemas/tool_io.py
Notes:
 - Covers load/unload/compatibility and retry/redaction/audit hooks.
"""

from __future__ import annotations

import pytest

from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.executor import DeterministicToolExecutor
from src.tools.plugins.plugin_contract import PluginManifest, ToolPlugin
from src.tools.plugins.plugin_manager import PluginManager
from src.tools.decorators import apply_execution_decorators, authz, validation
from src.tools.registry import ToolDescriptor, ToolRegistry


def _call(tool_name: str, arguments: dict) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="tc_plugin",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name=tool_name,
        arguments=arguments,
    )


def test_plugin_manager_load_and_unload() -> None:
    registry = ToolRegistry()
    manager = PluginManager(registry=registry, core_major_version=1)
    plugin = ToolPlugin(
        manifest=PluginManifest(
            plugin_id="math",
            version="1.0.0",
            compatible_core_major=1,
        ),
        tools=[ToolDescriptor(name="plus_one", handler=lambda x: x + 1)],
    )

    manager.load_plugin(plugin)
    assert manager.list_plugins() == ["math"]
    assert "plus_one" in registry.list_tools()

    manager.unload_plugin("math")
    assert manager.list_plugins() == []


def test_plugin_manager_blocks_incompatible_plugin() -> None:
    manager = PluginManager(registry=ToolRegistry(), core_major_version=1)
    incompatible = ToolPlugin(
        manifest=PluginManifest(
            plugin_id="future_plugin",
            version="2.0.0",
            compatible_core_major=2,
        ),
        tools=[],
    )
    try:
        manager.load_plugin(incompatible)
    except ValueError as exc:
        assert "requires core major" in str(exc)
    else:  # pragma: no cover - guard
        raise AssertionError("Expected compatibility failure")


def test_plugin_manager_branch_guards_and_reload_paths() -> None:
    registry = ToolRegistry()
    manager = PluginManager(registry=registry, core_major_version=1)
    plugin = ToolPlugin(
        manifest=PluginManifest(plugin_id="math", version="1.0.0", compatible_core_major=1),
        tools=[ToolDescriptor(name="plus_one", handler=lambda x: x + 1)],
    )
    manager.load_plugin(plugin)
    try:
        manager.load_plugin(plugin)
    except ValueError as exc:
        assert "already loaded" in str(exc)
    else:
        raise AssertionError("Expected duplicate load guard.")

    try:
        manager.unload_plugin("math", has_active_non_idempotent_tasks=True)
    except RuntimeError as exc:
        assert "active non-idempotent tasks" in str(exc)
    else:
        raise AssertionError("Expected active-work unload guard.")

    registry.unregister("plus_one")
    manager.unload_plugin("math")
    assert manager.list_plugins() == []

    try:
        manager.unload_plugin("missing")
    except KeyError as exc:
        assert "not loaded" in str(exc)
    else:
        raise AssertionError("Expected missing-plugin unload guard.")

    manager.load_plugin(plugin)
    manager.reload_plugin(plugin)
    assert manager.list_plugins() == ["math"]


def test_executor_applies_retry_redaction_and_audit_hooks() -> None:
    registry = ToolRegistry()
    calls = {"count": 0}
    audit_events: list[dict] = []

    def flaky_with_secret() -> dict:
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("retry me")
        return {"secret": "token", "status": "ok"}

    registry.register(
        ToolDescriptor(
            name="flaky_tool",
            handler=flaky_with_secret,
            metadata={
                "max_retries": 2,
                "redact_keys": ["secret"],
            },
        )
    )
    executor = DeterministicToolExecutor(
        registry=registry,
        policy=DeterministicFirstPolicyMiddleware(),
        audit_sink=audit_events.append,
    )
    result = executor.execute(_call("flaky_tool", {}))

    assert result.status == ToolStatus.SUCCESS
    assert result.result == {"value": {"secret": "***REDACTED***", "status": "ok"}}
    assert calls["count"] == 2
    assert any(event["event"] == "tool.flaky_tool.start" for event in audit_events)
    assert any(event["event"] == "tool.flaky_tool.success" for event in audit_events)


def test_validation_decorator_raises_on_missing_kwargs() -> None:
    @validation(required_args=["a"])
    def _fn(*, a: int) -> int:
        return a

    with pytest.raises(ValueError, match="Missing required arguments"):
        _fn()


def test_authz_decorator_blocks_state_changing_when_disallowed() -> None:
    @authz(allow_state_changing=False, is_state_changing_call=True)
    def _fn() -> str:
        return "ok"

    with pytest.raises(PermissionError, match="State-changing"):
        _fn()


def test_audit_logging_decorator_emits_error_event() -> None:
    events: list[dict] = []

    def _bad() -> None:
        raise RuntimeError("boom")

    wrapped = apply_execution_decorators(
        _bad,
        required_args=[],
        allow_state_changing=True,
        is_state_changing_call=False,
        max_attempts=1,
        redact_keys=[],
        audit_sink=events.append,
        event_prefix="t",
    )

    with pytest.raises(RuntimeError, match="boom"):
        wrapped()
    assert any(e.get("event") == "t.error" for e in events)
