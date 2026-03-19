"""
File: test_startup_hydration.py
Path: tests/modules/api/test_startup_hydration.py
Role: Unit tests for startup hydration helpers and branch guards.
Used By:
 - pytest
Depends On:
 - src/api/startup.py
 - src/persistence/contracts.py
Notes:
 - Uses lightweight doubles to exercise no-op/skip/fallback paths without full app bootstrap.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.api import startup
from src.persistence.contracts import (
    PersistedAgentRecord,
    PersistedProviderRecord,
    PersistedToolRecord,
    ToolPackageManifest,
    ToolValidationResult,
    ToolValidationState,
    ToolVersionRecord,
)


class _ToolStore:
    def __init__(self, tenant_ids: list[str], records: dict[str, list[PersistedToolRecord]]) -> None:
        self._tenant_ids = tenant_ids
        self._records = records

    async def list_tenant_ids(self) -> list[str]:
        return self._tenant_ids

    async def list_tools(self, tenant_id: str) -> list[PersistedToolRecord]:
        return self._records.get(tenant_id, [])


class _ToolVersionStore:
    def __init__(self, tenant_ids: list[str], records: dict[str, list[ToolVersionRecord]]) -> None:
        self._tenant_ids = tenant_ids
        self._records = records

    async def list_tenant_ids(self) -> list[str]:
        return self._tenant_ids

    async def list_active_tool_versions(self, tenant_id: str) -> list[ToolVersionRecord]:
        return self._records.get(tenant_id, [])


class _AgentStore:
    def __init__(self, tenant_ids: list[str], records: dict[str, list[PersistedAgentRecord]]) -> None:
        self._tenant_ids = tenant_ids
        self._records = records

    async def list_tenant_ids(self) -> list[str]:
        return self._tenant_ids

    async def list_agents(self, tenant_id: str) -> list[PersistedAgentRecord]:
        return self._records.get(tenant_id, [])


class _ProviderStore:
    def __init__(self, records: list[PersistedProviderRecord]) -> None:
        self._records = records

    async def list_providers(self) -> list[PersistedProviderRecord]:
        return self._records


class _ToolRegistry:
    def __init__(self) -> None:
        self._descriptors: dict[str, object] = {}

    def list_tools(self) -> list[str]:
        return sorted(self._descriptors.keys())

    def register(self, descriptor) -> None:
        self._descriptors[descriptor.name] = descriptor

    def unregister(self, tool_name: str) -> None:
        if tool_name not in self._descriptors:
            raise KeyError(tool_name)
        del self._descriptors[tool_name]


class _AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, object] = {}

    def get(self, agent_id: str):
        if agent_id not in self._agents:
            raise KeyError(agent_id)
        return self._agents[agent_id]

    def register(self, spec) -> None:
        if spec.agent_id in self._agents:
            raise ValueError("duplicate")
        self._agents[spec.agent_id] = spec


class _TenantFactory:
    def __init__(self) -> None:
        self._ctx: dict[str, object] = {}

    def get_or_create(self, tenant_id: str):
        if tenant_id not in self._ctx:
            self._ctx[tenant_id] = SimpleNamespace(tool_registry=_ToolRegistry(), agent_registry=_AgentRegistry())
        return self._ctx[tenant_id]


def _persisted_provider(provider_id: str, *, profile: str = "managed_vendor", api_type: str = "openai_native"):
    return PersistedProviderRecord(
        provider_id=provider_id,
        display_name=f"Provider {provider_id}",
        adapter_class="OpenAIAgentsRuntimeAdapter",
        enabled=True,
        profile=profile,
        priority=1,
        endpoint_base_url="https://api.openai.com",
        endpoint_api_type=api_type,
        auth_type="api_key",
        auth_api_key_env_var="",
        model="gpt-4o-mini",
        temperature=0.2,
        max_output_tokens=1024,
    )


def test_resolve_handler_ref_invalid_paths_return_none() -> None:
    assert startup._resolve_handler_ref("bad-format") is None
    assert startup._resolve_handler_ref("missing.module:run") is None
    assert startup._resolve_handler_ref("math:pi") is None
    assert startup._resolve_handler_ref("math:sqrt") is not None


def test_tool_record_to_descriptor_handles_unknown_risk_tier() -> None:
    record = PersistedToolRecord(
        name="tool_a",
        handler_ref="math:sqrt",
        tenant_id="t1",
        risk_tier="not-a-tier",
        timeout_ms=10,
        parameters_schema={"type": "object"},
    )
    descriptor = startup._tool_record_to_descriptor(record)
    assert descriptor is not None
    assert descriptor.risk_tier.value == "low"


def test_provider_record_to_runtime_fallbacks_and_load_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    rec = _persisted_provider("p1", profile="invalid", api_type="invalid")
    out = startup._provider_record_to_runtime(rec)
    assert out is not None
    provider_record, _ = out
    assert provider_record.profile.value == "managed_vendor"
    assert provider_record.endpoint.api_type.value == "openai_native"

    monkeypatch.setattr("src.api.startup.load_adapter", lambda *a, **k: (_ for _ in ()).throw(ImportError("boom")))
    assert startup._provider_record_to_runtime(_persisted_provider("p2")) is None


def test_hydrate_noops_when_factory_missing() -> None:
    app = SimpleNamespace(state=SimpleNamespace())
    asyncio.run(startup.hydrate_tenant_registries(app))


def test_hydrate_skips_unresolvable_tool_and_invalid_active_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_factory = _TenantFactory()
    tool_store = _ToolStore(
        ["t1"],
        {"t1": [PersistedToolRecord(name="broken", handler_ref="bad-format", tenant_id="t1")]},
    )
    tool_version_store = _ToolVersionStore(
        ["t1"],
        {
            "t1": [
                ToolVersionRecord(
                    tenant_id="t1",
                    tool_name="vtool",
                    version="1.0.0",
                    manifest=ToolPackageManifest(tool_name="vtool", version="1.0.0", input_schema={"type": "object"}),
                    validation=ToolValidationResult(
                        tool_name="vtool",
                        version="1.0.0",
                        state=ToolValidationState.VALID,
                    ),
                    active=True,
                )
            ]
        },
    )
    agent_store = _AgentStore(
        ["t1"],
        {"t1": [PersistedAgentRecord(agent_id="a1", role="assistant", tenant_id="t1", capability_tags=[])]},
    )
    provider_registry = SimpleNamespace(_providers={}, register=lambda rec, adapter: None)
    provider_store = _ProviderStore([_persisted_provider("p1")])

    # Force descriptor projection to fail for active tool version hydration branch.
    monkeypatch.setattr("src.api.startup.descriptor_from_tool_version", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad version")))
    # Force provider hydration to skip one provider.
    monkeypatch.setattr("src.api.startup._provider_record_to_runtime", lambda record: None if record.provider_id == "p1" else None)

    app = SimpleNamespace(
        state=SimpleNamespace(
            tool_store=tool_store,
            tool_version_store=tool_version_store,
            agent_store=agent_store,
            tenant_factory=tenant_factory,
            provider_store=provider_store,
            provider_registry=provider_registry,
            settings=SimpleNamespace(limits=SimpleNamespace(tool_artifact_signing_secret="secret")),
        )
    )
    asyncio.run(startup.hydrate_tenant_registries(app))


def test_hydrate_agent_duplicate_registration_guard() -> None:
    tenant_factory = _TenantFactory()
    ctx = tenant_factory.get_or_create("t1")
    ctx.agent_registry.register(startup._agent_record_to_spec(PersistedAgentRecord(agent_id="dup", role="assistant", tenant_id="t1")))

    agent_store = _AgentStore(
        ["t1"],
        {"t1": [PersistedAgentRecord(agent_id="dup", role="assistant", tenant_id="t1")]},
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            tool_store=None,
            tool_version_store=None,
            agent_store=agent_store,
            tenant_factory=tenant_factory,
            provider_store=None,
            provider_registry=None,
            settings=SimpleNamespace(limits=SimpleNamespace(tool_artifact_signing_secret="secret")),
        )
    )
    asyncio.run(startup.hydrate_tenant_registries(app))


def test_hydrate_success_paths_and_provider_registration() -> None:
    tenant_factory = _TenantFactory()
    tool_store = _ToolStore(
        ["t1"],
        {
            "t1": [
                PersistedToolRecord(name="ok_tool", handler_ref="math:sqrt", tenant_id="t1"),
                PersistedToolRecord(name="ok_tool", handler_ref="math:sqrt", tenant_id="t1"),  # duplicate name skip
            ]
        },
    )
    version_store = _ToolVersionStore(
        ["t1"],
        {
            "t1": [
                ToolVersionRecord(
                    tenant_id="t1",
                    tool_name="vtool",
                    version="1.0.0",
                    manifest=ToolPackageManifest(tool_name="vtool", version="1.0.0", input_schema={"type": "object"}),
                    validation=ToolValidationResult(tool_name="vtool", version="1.0.0", state=ToolValidationState.VALID),
                    active=True,
                )
            ]
        },
    )

    class _RaisingAgentRegistry(_AgentRegistry):
        def get(self, agent_id: str):
            raise KeyError(agent_id)

        def register(self, spec) -> None:
            raise ValueError("duplicate guard")

    # Prebuild context so custom registry is used.
    ctx = tenant_factory.get_or_create("t1")
    ctx.agent_registry = _RaisingAgentRegistry()

    agent_store = _AgentStore(
        ["t1"],
        {"t1": [PersistedAgentRecord(agent_id="a_dup", role="assistant", tenant_id="t1")]},
    )

    provider_store = _ProviderStore([_persisted_provider("existing"), _persisted_provider("new-provider")])
    registered: list[str] = []

    provider_registry = SimpleNamespace(
        _providers={"existing": object()},
        register=lambda rec, adapter: registered.append(rec.provider_id),
    )

    app = SimpleNamespace(
        state=SimpleNamespace(
            tool_store=tool_store,
            tool_version_store=version_store,
            agent_store=agent_store,
            tenant_factory=tenant_factory,
            provider_store=provider_store,
            provider_registry=provider_registry,
            settings=SimpleNamespace(limits=SimpleNamespace(tool_artifact_signing_secret="secret")),
        )
    )
    asyncio.run(startup.hydrate_tenant_registries(app))
    # Existing provider skipped; new provider registered.
    assert registered == ["new-provider"]
