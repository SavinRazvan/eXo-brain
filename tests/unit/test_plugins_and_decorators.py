"""
File: test_plugins_and_decorators.py
Path: tests/unit/test_plugins_and_decorators.py
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

from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.executor import DeterministicToolExecutor
from src.tools.plugins.plugin_contract import PluginManifest, ToolPlugin
from src.tools.plugins.plugin_manager import PluginManager
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
