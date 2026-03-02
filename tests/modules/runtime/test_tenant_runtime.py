"""
File: test_tenant_runtime.py
Path: tests/modules/runtime/test_tenant_runtime.py
Role: Acceptance tests for Slice 0 — tenant isolation, session runtime lifecycle,
      agent spec resolution, tool wiring pre-reqs, and ProviderRegistry integration.
Used By:
 - pytest
Depends On:
 - src/runtime/tenant_runtime.py
 - src/runtime/tool_wiring.py
 - src/tools/registry.py
 - src/agents/contracts.py
 - src/agents/registry.py
 - src/config/provider_registry.py
 - src/config/settings.py
"""

from __future__ import annotations

import pytest

from src.agents.contracts import AgentCapabilityTag, AgentSpec, HandoffFallbackPolicy, HandoffRoute
from src.agents.registry import AgentRegistry
from src.config.provider_registry import (
    AuthConfig,
    EndpointApiType,
    EndpointConfig,
    ModelDefaults,
    ProviderProfile,
    ProviderRecord,
    ProviderRegistry,
)
from src.config.settings import AppSettings, RuntimeSettings
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.runtime.tenant_runtime import TenantRuntimeContext, TenantRuntimeFactory
from src.runtime.tool_wiring import build_agent_tools
from src.schemas.tool_io import RiskTier
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(provider_id: str = "openai-test") -> AppSettings:
    return AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id=provider_id,
            allowed_provider_ids=[provider_id],
            require_provider_healthcheck_on_start=False,
        ),
    )


def _make_provider_registry(provider_id: str = "openai-test") -> ProviderRegistry:
    adapter = OpenAIAgentsRuntimeAdapter(provider_id=provider_id)
    record = ProviderRecord(
        provider_id=provider_id,
        display_name="Test OpenAI",
        adapter_class="OpenAIAgentsRuntimeAdapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="https://api.openai.com", api_type=EndpointApiType.OPENAI_NATIVE),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="gpt-4o-mini"),
    )
    return ProviderRegistry(
        settings=_make_settings(provider_id),
        providers=[record],
        adapters={provider_id: adapter},
    )


def _make_factory(provider_id: str = "openai-test") -> TenantRuntimeFactory:
    return TenantRuntimeFactory(
        provider_registry=_make_provider_registry(provider_id),
        settings=_make_settings(provider_id),
    )


# ---------------------------------------------------------------------------
# Pre-req: AgentSpec.instructions (pre-req #2)
# ---------------------------------------------------------------------------


def test_agent_spec_instructions_field_defaults_to_empty() -> None:
    spec = AgentSpec(agent_id="a1", role="assistant")
    assert spec.instructions == ""


def test_agent_spec_instructions_round_trips_through_registry() -> None:
    registry = AgentRegistry()
    spec = AgentSpec(agent_id="math-agent", role="math", instructions="You are a math assistant.")
    registry.register(spec)
    retrieved = registry.get("math-agent")
    assert retrieved.instructions == "You are a math assistant."


# ---------------------------------------------------------------------------
# Pre-req: ToolRegistry additions (pre-reqs #3, #4, #5)
# ---------------------------------------------------------------------------


def test_tool_registry_list_descriptors_returns_sorted() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="zap", handler=lambda: None))
    registry.register(ToolDescriptor(name="add", handler=lambda a, b: a + b))
    names = [d.name for d in registry.list_descriptors()]
    assert names == ["add", "zap"]


def test_tool_registry_list_descriptors_empty_registry() -> None:
    registry = ToolRegistry()
    assert registry.list_descriptors() == []


def test_tool_descriptor_description_and_parameters_schema_fields() -> None:
    schema = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}
    desc = ToolDescriptor(
        name="compute",
        handler=lambda x: x * 2,
        description="Doubles a number.",
        parameters_schema=schema,
    )
    registry = ToolRegistry()
    registry.register(desc)
    retrieved = registry.resolve("compute")
    assert retrieved.description == "Doubles a number."
    assert retrieved.parameters_schema == schema


def test_tool_registry_unregister_removes_tool() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="my_tool", handler=lambda: None))
    registry.unregister("my_tool")
    assert "my_tool" not in registry.list_tools()
    with pytest.raises(KeyError):
        registry.resolve("my_tool")


def test_tool_registry_unregister_raises_for_unknown_tool() -> None:
    registry = ToolRegistry()
    with pytest.raises(KeyError, match="Tool 'unknown' is not registered"):
        registry.unregister("unknown")


# ---------------------------------------------------------------------------
# Tenant isolation (Problem 2 fix)
# ---------------------------------------------------------------------------


def test_tenant_runtime_context_has_no_orchestrator_field() -> None:
    """TenantRuntimeContext must NOT contain orchestrator or host_adapter."""
    factory = _make_factory()
    ctx = factory.get_or_create("tenant-a")
    assert not hasattr(ctx, "orchestrator")
    assert not hasattr(ctx, "host_adapter")


def test_tool_registered_in_tenant_a_not_visible_in_tenant_b() -> None:
    factory = _make_factory()
    ctx_a = factory.get_or_create("tenant-a")
    ctx_b = factory.get_or_create("tenant-b")

    ctx_a.tool_registry.register(ToolDescriptor(name="exclusive_tool", handler=lambda: None))

    assert "exclusive_tool" in ctx_a.tool_registry.list_tools()
    assert "exclusive_tool" not in ctx_b.tool_registry.list_tools()


def test_get_or_create_returns_same_context_for_same_tenant() -> None:
    factory = _make_factory()
    ctx1 = factory.get_or_create("tenant-x")
    ctx2 = factory.get_or_create("tenant-x")
    assert ctx1 is ctx2


def test_list_tenants_returns_registered_tenant_ids() -> None:
    factory = _make_factory()
    factory.get_or_create("tenant-1")
    factory.get_or_create("tenant-2")
    assert sorted(factory.list_tenants()) == ["tenant-1", "tenant-2"]


# ---------------------------------------------------------------------------
# Session runtime lifecycle (Problem 3 fix)
# ---------------------------------------------------------------------------


def test_create_session_runtime_stores_and_retrieves_host_adapter() -> None:
    factory = _make_factory()
    ctx = factory.get_or_create("tenant-sess")
    agent = AgentSpec(agent_id="agent-1", role="assistant", instructions="Help me.")
    ctx.agent_registry.register(agent)

    host = factory.create_session_runtime(ctx, agent_id="agent-1", provider_id="openai-test", session_id="sess-001")
    retrieved = factory.get_session_runtime("sess-001")
    assert retrieved is host


def test_get_session_runtime_raises_for_unknown_session() -> None:
    factory = _make_factory()
    with pytest.raises(KeyError, match="sess-unknown"):
        factory.get_session_runtime("sess-unknown")


def test_destroy_evicts_tenant_context_and_session_runtimes() -> None:
    factory = _make_factory()
    ctx = factory.get_or_create("tenant-destroy")
    agent = AgentSpec(agent_id="agent-d", role="destroyer")
    ctx.agent_registry.register(agent)
    factory.create_session_runtime(ctx, agent_id="agent-d", provider_id="openai-test", session_id="sess-d1")

    factory.destroy("tenant-destroy")

    assert "tenant-destroy" not in factory.list_tenants()
    with pytest.raises(KeyError):
        factory.get_session_runtime("sess-d1")


# ---------------------------------------------------------------------------
# Agent spec resolution (Problem 4 fix)
# ---------------------------------------------------------------------------


def test_create_session_runtime_raises_key_error_for_unknown_agent() -> None:
    factory = _make_factory()
    ctx = factory.get_or_create("tenant-ag")
    with pytest.raises(KeyError):
        factory.create_session_runtime(ctx, agent_id="nonexistent", provider_id="openai-test", session_id="sess-ag1")


def test_adapter_receives_instructions_and_model_from_agent_spec() -> None:
    """Adapter _session_metadata must contain instructions and model after create_session_runtime."""
    factory = _make_factory()
    ctx = factory.get_or_create("tenant-meta")
    agent = AgentSpec(
        agent_id="meta-agent",
        role="meta",
        instructions="You are a meta assistant.",
        metadata={"model": "gpt-4o"},
    )
    ctx.agent_registry.register(agent)
    factory.create_session_runtime(ctx, agent_id="meta-agent", provider_id="openai-test", session_id="sess-meta")

    adapter = factory.get_session_adapter("sess-meta")
    meta = adapter._session_metadata.get("sess-meta", {})
    assert meta.get("instructions") == "You are a meta assistant."
    assert meta.get("model") == "gpt-4o"
    assert meta.get("agent_id") == "meta-agent"


def test_two_sessions_use_independent_metadata() -> None:
    factory = _make_factory()
    ctx = factory.get_or_create("tenant-two-sess")

    agent_a = AgentSpec(agent_id="agent-a", role="role-a", instructions="Instructions A")
    agent_b = AgentSpec(agent_id="agent-b", role="role-b", instructions="Instructions B")
    ctx.agent_registry.register(agent_a)
    ctx.agent_registry.register(agent_b)

    factory.create_session_runtime(ctx, agent_id="agent-a", provider_id="openai-test", session_id="sess-two-a")
    factory.create_session_runtime(ctx, agent_id="agent-b", provider_id="openai-test", session_id="sess-two-b")

    adapter_a = factory.get_session_adapter("sess-two-a")
    adapter_b = factory.get_session_adapter("sess-two-b")
    assert adapter_a._session_metadata["sess-two-a"]["instructions"] == "Instructions A"
    assert adapter_b._session_metadata["sess-two-b"]["instructions"] == "Instructions B"


# ---------------------------------------------------------------------------
# Late binding tools (Problem 5 fix)
# ---------------------------------------------------------------------------


def test_build_agent_tools_returns_function_tool_for_each_descriptor() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(
        name="add",
        handler=lambda a, b: a + b,
        description="Adds two numbers.",
        parameters_schema={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ))
    registry.register(ToolDescriptor(name="noop", handler=lambda: None))

    from src.policies.middleware import DeterministicFirstPolicyMiddleware
    executor = DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware())
    tools = build_agent_tools(registry, executor)

    assert len(tools) == 2
    tool_names = {t.name for t in tools}
    assert tool_names == {"add", "noop"}


def test_build_agent_tools_empty_registry_returns_empty_list() -> None:
    registry = ToolRegistry()
    from src.policies.middleware import DeterministicFirstPolicyMiddleware
    executor = DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware())
    tools = build_agent_tools(registry, executor)
    assert tools == []


def test_tool_registered_after_start_session_appears_in_next_build() -> None:
    """Late binding: tools added after session creation are visible on next build_agent_tools call."""
    registry = ToolRegistry()
    from src.policies.middleware import DeterministicFirstPolicyMiddleware
    executor = DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware())

    tools_before = build_agent_tools(registry, executor)
    assert len(tools_before) == 0

    registry.register(ToolDescriptor(name="late_tool", handler=lambda: "late"))
    tools_after = build_agent_tools(registry, executor)
    assert len(tools_after) == 1
    assert tools_after[0].name == "late_tool"


# ---------------------------------------------------------------------------
# AgentRegistry new methods
# ---------------------------------------------------------------------------


def _make_two_agent_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(AgentSpec(
        agent_id="a1",
        role="source",
        capability_tags={AgentCapabilityTag.TOOL_USE},
    ))
    registry.register(AgentSpec(
        agent_id="a2",
        role="target",
        capability_tags={AgentCapabilityTag.TOOL_USE},
    ))
    return registry


def test_list_routes_returns_registered_routes() -> None:
    registry = _make_two_agent_registry()
    route = HandoffRoute(source_role="source", target_role="target", reason="test")
    registry.add_handoff_route(route)
    routes = registry.list_routes()
    assert len(routes) == 1
    assert routes[0].source_role == "source"
    assert routes[0].target_role == "target"


def test_list_routes_empty_when_no_routes() -> None:
    registry = AgentRegistry()
    assert registry.list_routes() == []


def test_list_fallback_policies_returns_registered_policies() -> None:
    registry = _make_two_agent_registry()
    policy = HandoffFallbackPolicy(source_role="source", target_role="target")
    registry.set_handoff_fallback_policy(policy)
    policies = registry.list_fallback_policies()
    assert len(policies) == 1
    assert policies[0].source_role == "source"
    assert policies[0].target_role == "target"


def test_list_fallback_policies_empty_when_no_policies() -> None:
    registry = AgentRegistry()
    assert registry.list_fallback_policies() == []
