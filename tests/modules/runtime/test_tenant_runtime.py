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

import asyncio
import logging
import time
from typing import Any

import pytest

from tests.constants import BYOC_WORKER_JWT_SECRET

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
from collections.abc import AsyncIterator

from src.runtime.adapter_factory import OPENAI_ADAPTER_CANONICAL_CLASS_REF
from src.runtime.capability_map import HealthState, HealthStatus, ProviderCapabilityMap, SecurityTier
from src.runtime.custom_runtime import CustomRuntimeAdapter
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.runtime.runtime_adapter import RuntimeAdapter, SessionHandle


def _openai_agents_runtime_adapter_types() -> tuple[type, ...]:
    """In-tree and (when importable) portable OpenAI adapter classes — lazy to avoid collection-order ImportErrors."""
    types: list[type] = [OpenAIAgentsRuntimeAdapter]
    try:
        from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter as PackagedOpenAIAgentsRuntimeAdapter
    except ImportError:
        return tuple(types)
    types.append(PackagedOpenAIAgentsRuntimeAdapter)
    return tuple(types)
from src.runtime.tenant_runtime import (
    TenantRuntimeContext,
    TenantRuntimeFactory,
    _log_adapter_start_session_done,
)
from src.schemas.events import RuntimeEvent
from src.runtime.tool_wiring import build_agent_tools
from src.schemas.tool_io import RiskTier, ToolResult
from src.tools.execution_adapter import ToolExecutionAdapter
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
        adapter_class=OPENAI_ADAPTER_CANONICAL_CLASS_REF,
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


class _FailingStartSessionAdapter(CustomRuntimeAdapter):
    async def start_session(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionHandle:
        raise RuntimeError("intentional start_session failure for tests")


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


def test_tenant_factory_keeps_local_executor_when_hosted_runtime_flag_disabled() -> None:
    factory = _make_factory()
    ctx = factory.get_or_create("tenant-local-runtime")
    assert getattr(ctx.tool_executor, "_enable_hosted_runtime") is False
    assert getattr(ctx.tool_executor, "_execution_adapter") is None


def test_tenant_factory_wires_hosted_runtime_stub_when_flag_enabled() -> None:
    settings = _make_settings()
    settings.runtime.enable_hosted_tool_runtime = True
    factory = TenantRuntimeFactory(
        provider_registry=_make_provider_registry(),
        settings=settings,
    )
    ctx = factory.get_or_create("tenant-hosted-runtime")
    adapter = getattr(ctx.tool_executor, "_execution_adapter")
    assert getattr(ctx.tool_executor, "_enable_hosted_runtime") is True
    assert isinstance(adapter, ToolExecutionAdapter)
    assert adapter.backend_id == "hosted_sandbox_runtime"


def test_tenant_factory_enables_process_isolation_when_flag_enabled() -> None:
    settings = _make_settings()
    settings.runtime.enable_hosted_tool_runtime = True
    settings.runtime.enable_hosted_tool_process_isolation = True
    factory = TenantRuntimeFactory(
        provider_registry=_make_provider_registry(),
        settings=settings,
    )
    ctx = factory.get_or_create("tenant-hosted-runtime-process")
    adapter = getattr(ctx.tool_executor, "_execution_adapter")
    assert isinstance(adapter, ToolExecutionAdapter)
    assert getattr(adapter, "_enable_process_isolation") is True


def test_tenant_factory_defaults_to_hosted_runtime_when_byoc_disabled() -> None:
    settings = _make_settings()
    settings.runtime.enable_hosted_tool_runtime = True
    settings.runtime.enable_byoc_tool_runtime = False
    factory = TenantRuntimeFactory(
        provider_registry=_make_provider_registry(),
        settings=settings,
    )
    ctx = factory.get_or_create("tenant-hosted-default")
    adapter = getattr(ctx.tool_executor, "_execution_adapter")
    assert isinstance(adapter, ToolExecutionAdapter)
    assert adapter.backend_id == "hosted_sandbox_runtime"


def test_tenant_factory_uses_byoc_runtime_when_flag_enabled() -> None:
    settings = _make_settings()
    settings.runtime.enable_hosted_tool_runtime = True
    settings.runtime.enable_byoc_tool_runtime = True
    settings.runtime.byoc_worker_jwt_secret = BYOC_WORKER_JWT_SECRET
    factory = TenantRuntimeFactory(
        provider_registry=_make_provider_registry(),
        settings=settings,
    )
    ctx = factory.get_or_create("tenant-byoc-runtime")
    adapter = getattr(ctx.tool_executor, "_execution_adapter")
    assert isinstance(adapter, ToolExecutionAdapter)
    assert adapter.backend_id == "byoc_pull_worker_runtime"


def test_tenant_factory_byoc_invalid_conflict_strategy_falls_back_to_first_write_wins(
    tmp_path,
) -> None:
    settings = _make_settings()
    settings.runtime.enable_byoc_tool_runtime = True
    settings.runtime.byoc_worker_jwt_secret = BYOC_WORKER_JWT_SECRET
    settings.runtime.byoc_result_conflict_strategy = "not-a-valid-strategy"
    settings.runtime.byoc_store_backend = "sqlite"
    settings.runtime.byoc_sqlite_db_path = str(tmp_path / "byoc_conflict.db")
    factory = TenantRuntimeFactory(
        provider_registry=_make_provider_registry(),
        settings=settings,
    )
    ctx = factory.get_or_create("tenant-byoc-bad-strategy")
    adapter = getattr(ctx.tool_executor, "_execution_adapter")
    assert getattr(adapter, "_result_store").conflict_strategy_name() == "first_write_wins"


def test_tenant_factory_byoc_in_memory_invalid_conflict_strategy_falls_back() -> None:
    settings = _make_settings()
    settings.runtime.enable_byoc_tool_runtime = True
    settings.runtime.byoc_worker_jwt_secret = BYOC_WORKER_JWT_SECRET
    settings.runtime.byoc_store_backend = "memory"
    settings.runtime.byoc_result_conflict_strategy = "@@@"
    factory = TenantRuntimeFactory(
        provider_registry=_make_provider_registry(),
        settings=settings,
    )
    ctx = factory.get_or_create("tenant-byoc-mem-bad")
    adapter = getattr(ctx.tool_executor, "_execution_adapter")
    assert getattr(adapter, "_result_store").conflict_strategy_name() == "first_write_wins"


def test_tenant_factory_uses_sqlite_backed_byoc_stores_when_configured(tmp_path) -> None:
    from src.tools.byoc.sqlite_store import SQLiteByocJobQueueStore, SQLiteByocResultStore, SQLiteReplayGuard

    settings = _make_settings()
    settings.runtime.enable_byoc_tool_runtime = True
    settings.runtime.byoc_store_backend = "sqlite"
    settings.runtime.byoc_sqlite_db_path = str(tmp_path / "tenant_byoc.db")
    settings.runtime.byoc_worker_jwt_secret = BYOC_WORKER_JWT_SECRET
    factory = TenantRuntimeFactory(
        provider_registry=_make_provider_registry(),
        settings=settings,
    )
    ctx = factory.get_or_create("tenant-byoc-sqlite")
    adapter = getattr(ctx.tool_executor, "_execution_adapter")
    assert isinstance(adapter, ToolExecutionAdapter)
    assert adapter.backend_id == "byoc_pull_worker_runtime"
    assert isinstance(getattr(adapter, "_job_store"), SQLiteByocJobQueueStore)
    assert isinstance(getattr(adapter, "_result_store"), SQLiteByocResultStore)
    assert isinstance(getattr(adapter, "_replay_guard"), SQLiteReplayGuard)


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


def test_create_session_runtime_prefers_record_adapter_class_ref() -> None:
    provider_id = "provider-loader"
    settings = _make_settings(provider_id)
    record = ProviderRecord(
        provider_id=provider_id,
        display_name="Loader Provider",
        adapter_class=OPENAI_ADAPTER_CANONICAL_CLASS_REF,
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="https://api.openai.com", api_type=EndpointApiType.OPENAI_NATIVE),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="gpt-4o-mini"),
    )
    registry = ProviderRegistry(
        settings=settings,
        providers=[record],
        # Intentionally bind a different runtime type to prove class-ref loading is used.
        adapters={provider_id: CustomRuntimeAdapter(provider_id=provider_id)},
    )
    factory = TenantRuntimeFactory(provider_registry=registry, settings=settings)
    ctx = factory.get_or_create("tenant-loader")
    ctx.agent_registry.register(AgentSpec(agent_id="agent-loader", role="assistant"))

    factory.create_session_runtime(
        ctx,
        agent_id="agent-loader",
        provider_id=provider_id,
        session_id="sess-loader",
    )

    adapter = factory.get_session_adapter("sess-loader")
    assert isinstance(adapter, _openai_agents_runtime_adapter_types())
    assert adapter._tool_registry is ctx.tool_registry
    assert adapter._tool_executor is ctx.tool_executor


def test_create_session_runtime_accepts_legacy_short_adapter_class_ref() -> None:
    provider_id = "provider-legacy-short"
    settings = _make_settings(provider_id)
    record = ProviderRecord(
        provider_id=provider_id,
        display_name="Legacy Short Ref Provider",
        adapter_class="OpenAIAgentsRuntimeAdapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="https://api.openai.com", api_type=EndpointApiType.OPENAI_NATIVE),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="gpt-4o-mini"),
    )
    registry = ProviderRegistry(
        settings=settings,
        providers=[record],
        adapters={provider_id: CustomRuntimeAdapter(provider_id=provider_id)},
    )
    factory = TenantRuntimeFactory(provider_registry=registry, settings=settings)
    ctx = factory.get_or_create("tenant-legacy-short")
    ctx.agent_registry.register(AgentSpec(agent_id="agent-legacy-short", role="assistant"))

    factory.create_session_runtime(
        ctx,
        agent_id="agent-legacy-short",
        provider_id=provider_id,
        session_id="sess-legacy-short",
    )

    adapter = factory.get_session_adapter("sess-legacy-short")
    assert isinstance(adapter, _openai_agents_runtime_adapter_types())


def test_get_session_runtime_raises_for_unknown_session() -> None:
    factory = _make_factory()
    with pytest.raises(KeyError, match="sess-unknown"):
        factory.get_session_runtime("sess-unknown")


def test_get_session_adapter_raises_for_unknown_session() -> None:
    factory = _make_factory()
    with pytest.raises(KeyError, match="No session adapter"):
        factory.get_session_adapter("missing-adapter-session")


def test_evict_sessions_for_provider_removes_matching_sessions() -> None:
    provider_id = "openai-test"
    factory = _make_factory(provider_id)
    ctx = factory.get_or_create("tenant-evict-prov")
    ctx.agent_registry.register(AgentSpec(agent_id="agent-evict", role="assistant"))
    factory.create_session_runtime(ctx, "agent-evict", provider_id, "sess-evict-1")
    factory.create_session_runtime(ctx, "agent-evict", provider_id, "sess-evict-2")
    removed = factory.evict_sessions_for_provider(provider_id)
    assert removed == 2
    with pytest.raises(KeyError):
        factory.get_session_runtime("sess-evict-1")


def test_session_runtime_max_cached_sessions_evicts_lru_before_add() -> None:
    provider_id = "openai-test"
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id=provider_id,
            allowed_provider_ids=[provider_id],
            require_provider_healthcheck_on_start=False,
            session_runtime_max_cached_sessions=1,
        ),
    )
    registry = _make_provider_registry(provider_id)
    factory = TenantRuntimeFactory(provider_registry=registry, settings=settings)
    ctx = factory.get_or_create("tenant-cap")
    ctx.agent_registry.register(AgentSpec(agent_id="agent-cap", role="assistant"))
    factory.create_session_runtime(ctx, "agent-cap", provider_id, "sess-cap-1")
    factory.create_session_runtime(ctx, "agent-cap", provider_id, "sess-cap-2")
    with pytest.raises(KeyError):
        factory.get_session_runtime("sess-cap-1")
    assert factory.get_session_runtime("sess-cap-2") is not None


def test_tenant_runtime_max_cached_contexts_evicts_lru_tenant() -> None:
    provider_id = "openai-test"
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id=provider_id,
            allowed_provider_ids=[provider_id],
            require_provider_healthcheck_on_start=False,
            tenant_runtime_max_cached_contexts=2,
        ),
    )
    registry = _make_provider_registry(provider_id)
    factory = TenantRuntimeFactory(provider_registry=registry, settings=settings)
    ctx_a = factory.get_or_create("tenant-lru-a")
    factory.get_or_create("tenant-lru-b")
    assert factory.get_or_create("tenant-lru-a") is ctx_a
    factory.get_or_create("tenant-lru-c")
    assert "tenant-lru-b" not in factory.list_tenants()
    assert "tenant-lru-a" in factory.list_tenants()
    assert "tenant-lru-c" in factory.list_tenants()


def test_log_adapter_start_session_done_noop_for_cancelled() -> None:
    async def _run() -> None:
        async def _slow() -> None:
            await asyncio.sleep(10)

        task = asyncio.create_task(_slow())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        _log_adapter_start_session_done(task, session_id="sess-cancelled")

    asyncio.run(_run())


def test_log_adapter_start_session_done_logs_failed_task(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)

    async def _run() -> None:
        async def _bad() -> None:
            raise RuntimeError("boom")

        task = asyncio.create_task(_bad())
        await asyncio.sleep(0)
        _log_adapter_start_session_done(task, session_id="sess-bad")

    asyncio.run(_run())
    assert any("adapter.start_session failed" in r.message for r in caplog.records)


def test_start_session_background_failure_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    provider_id = "fail-start-provider"
    settings = _make_settings(provider_id)
    record = ProviderRecord(
        provider_id=provider_id,
        display_name="Failing Start",
        adapter_class="definitely_missing_module_xyz.NoSuchAdapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="https://example.com", api_type=EndpointApiType.OPENAI_NATIVE),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="gpt-4o-mini"),
    )
    registry = ProviderRegistry(
        settings=settings,
        providers=[record],
        adapters={provider_id: _FailingStartSessionAdapter(provider_id=provider_id)},
    )
    factory = TenantRuntimeFactory(provider_registry=registry, settings=settings)
    ctx = factory.get_or_create("tenant-fail-bg")
    ctx.agent_registry.register(AgentSpec(agent_id="agent-fail-bg", role="assistant"))

    async def _run() -> None:
        factory.create_session_runtime(
            ctx,
            agent_id="agent-fail-bg",
            provider_id=provider_id,
            session_id="sess-fail-bg",
        )
        await asyncio.sleep(0.05)

    asyncio.run(_run())
    assert any("adapter.start_session failed" in r.message for r in caplog.records)


def test_create_session_runtime_schedules_start_session_when_loop_running() -> None:
    provider_id = "async-loop-provider"
    settings = _make_settings(provider_id)
    record = ProviderRecord(
        provider_id=provider_id,
        display_name="Async Provider",
        adapter_class=OPENAI_ADAPTER_CANONICAL_CLASS_REF,
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="https://api.openai.com", api_type=EndpointApiType.OPENAI_NATIVE),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="gpt-4o-mini"),
    )
    registry = ProviderRegistry(
        settings=settings,
        providers=[record],
        adapters={provider_id: CustomRuntimeAdapter(provider_id=provider_id)},
    )
    factory = TenantRuntimeFactory(provider_registry=registry, settings=settings)
    ctx = factory.get_or_create("tenant-async")
    ctx.agent_registry.register(AgentSpec(agent_id="agent-async", role="assistant"))

    async def _run() -> None:
        factory.create_session_runtime(
            ctx,
            agent_id="agent-async",
            provider_id=provider_id,
            session_id="sess-async-loop",
        )
        await asyncio.sleep(0.01)

    asyncio.run(_run())
    host = factory.get_session_runtime("sess-async-loop")
    assert host is not None


def test_instantiate_session_adapter_import_error_falls_back_to_registered_adapter() -> None:
    provider_id = "broken-import-provider"
    settings = _make_settings(provider_id)
    record = ProviderRecord(
        provider_id=provider_id,
        display_name="Broken Import",
        adapter_class="definitely_missing_module_xyz.NoSuchAdapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="https://example.com", api_type=EndpointApiType.OPENAI_NATIVE),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="gpt-4o-mini"),
    )
    bound = CustomRuntimeAdapter(provider_id=provider_id)
    registry = ProviderRegistry(
        settings=settings,
        providers=[record],
        adapters={provider_id: bound},
    )
    factory = TenantRuntimeFactory(provider_registry=registry, settings=settings)
    ctx = factory.get_or_create("tenant-fallback-adapter")
    ctx.agent_registry.register(AgentSpec(agent_id="agent-fb", role="assistant"))
    factory.create_session_runtime(ctx, "agent-fb", provider_id, "sess-fallback-import")
    adapter = factory.get_session_adapter("sess-fallback-import")
    assert isinstance(adapter, CustomRuntimeAdapter)
    assert adapter._provider_id == provider_id


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


def test_session_adapter_load_retries_without_tool_wiring_kwargs() -> None:
    adapter = CustomRuntimeAdapter(provider_id="custom-p")
    record = ProviderRecord(
        provider_id="custom-p",
        display_name="Custom",
        adapter_class="src.runtime.custom_runtime.CustomRuntimeAdapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="http://localhost", api_type=EndpointApiType.OPENAI_COMPATIBLE),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="stub"),
    )
    registry = ProviderRegistry(
        settings=_make_settings("custom-p"),
        providers=[record],
        adapters={"custom-p": adapter},
    )
    factory = TenantRuntimeFactory(provider_registry=registry, settings=_make_settings("custom-p"))
    ctx = factory.get_or_create("tenant-custom")
    resolved = factory._instantiate_session_adapter(ctx, "custom-p")
    assert isinstance(resolved, CustomRuntimeAdapter)


class _BareInitAdapter(RuntimeAdapter):
    """Adapter whose class can only be constructed with a no-arg __init__."""

    def __init__(self) -> None:
        self._provider_id = "bare"

    async def start_session(
        self,
        session_id: str,
        metadata: dict | None = None,
    ) -> SessionHandle:
        return SessionHandle(session_id=session_id, provider_id=self._provider_id, metadata=dict(metadata or {}))

    async def run_turn(
        self,
        session_id: str,
        user_input: str,
        context: dict,
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent.run_complete(session_id=session_id, run_id="r1", output={})

    async def submit_tool_results(
        self,
        session_id: str,
        run_id: str,
        tool_results: list[ToolResult],
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent.run_complete(session_id=session_id, run_id=run_id, output={})

    def get_capabilities(self) -> ProviderCapabilityMap:
        return ProviderCapabilityMap(provider_id=self._provider_id, security_tier=SecurityTier.LOCAL_ONLY)

    async def healthcheck(self) -> HealthStatus:
        return HealthStatus(state=HealthState.HEALTHY, reason="test")


def test_session_adapter_uses_bare_constructor_when_registered_type_rejects_provider_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bare = _BareInitAdapter()
    record = ProviderRecord(
        provider_id="bare-p",
        display_name="Bare",
        adapter_class="unresolvable.bare.Adapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="http://localhost", api_type=EndpointApiType.CUSTOM),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="stub"),
    )
    registry = ProviderRegistry(
        settings=_make_settings("bare-p"),
        providers=[record],
        adapters={"bare-p": bare},
    )
    factory = TenantRuntimeFactory(provider_registry=registry, settings=_make_settings("bare-p"))
    ctx = factory.get_or_create("tenant-bare")

    def _boom(*_a, **_k):
        raise ImportError("forced")

    monkeypatch.setattr("src.runtime.adapter_factory.load_adapter", _boom)
    resolved = factory._instantiate_session_adapter(ctx, "bare-p")
    assert isinstance(resolved, _BareInitAdapter)
    assert resolved is not bare


def test_session_adapter_falls_back_to_registered_adapter_when_load_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _make_factory()
    ctx = factory.get_or_create("tenant-fallback")

    def _boom(*_a, **_k):
        raise ImportError("forced")

    monkeypatch.setattr("src.runtime.adapter_factory.load_adapter", _boom)
    resolved = factory._instantiate_session_adapter(ctx, "openai-test")
    assert isinstance(resolved, OpenAIAgentsRuntimeAdapter)


def test_tenant_runtime_factory_evicts_idle_sessions_when_ttl_configured() -> None:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
            session_runtime_idle_ttl_seconds=30,
        ),
    )
    factory = TenantRuntimeFactory(
        provider_registry=_make_provider_registry(),
        settings=settings,
    )
    factory.get_or_create("t-evict-idle")
    factory._session_runtimes["sess-old"] = object()
    factory._session_adapters["sess-old"] = object()
    factory._session_tenant["sess-old"] = "t-evict-idle"
    factory._session_last_access["sess-old"] = time.monotonic() - 9999.0
    factory._evict_idle_sessions_only()
    assert "sess-old" not in factory._session_runtimes
    assert "sess-old" not in factory._session_adapters


def test_tenant_runtime_factory_evicts_lru_when_over_max_cached_sessions() -> None:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
            session_runtime_max_cached_sessions=2,
        ),
    )
    factory = TenantRuntimeFactory(
        provider_registry=_make_provider_registry(),
        settings=settings,
    )
    factory.get_or_create("t-lru")
    t_old = time.monotonic() - 200.0
    t_mid = time.monotonic() - 100.0
    t_new = time.monotonic() - 10.0
    for sid, ts in (("a", t_old), ("b", t_mid), ("c", t_new)):
        factory._session_runtimes[sid] = object()
        factory._session_adapters[sid] = object()
        factory._session_tenant[sid] = "t-lru"
        factory._session_last_access[sid] = ts
    factory._evict_lru_until_under_cap()
    assert len(factory._session_runtimes) == 1
    assert "c" in factory._session_runtimes
    assert "a" not in factory._session_runtimes
    assert "b" not in factory._session_runtimes
