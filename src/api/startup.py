"""
File: startup.py
Path: src/api/startup.py
Role: App startup hydration — restores persisted tools, agents, and providers into in-memory registries.
Used By:
 - src/api/bootstrap.py (lifespan startup hook)
Depends On:
 - src/persistence/contracts.py
 - src/config/provider_registry.py
 - src/runtime/adapter_factory.py
 - src/tools/registry.py
 - src/agents/contracts.py
 - src/schemas/tool_io.py
Notes:
 - Called once at app startup; idempotent (skips already-registered entries).
 - Tools with unresolvable handler_refs are logged and skipped — server still starts.
 - Handler resolution uses the same 'module.path:function_name' format as the tools router.
 - Providers are loaded from ProviderStore and registered via adapter_factory.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Callable

from src.agents.contracts import AgentCapabilityTag, AgentSpec
from src.config.provider_registry import (
    AuthConfig,
    EndpointApiType,
    EndpointConfig,
    ModelDefaults,
    ProviderProfile,
    ProviderRecord,
)
from src.persistence.contracts import PersistedAgentRecord, PersistedProviderRecord, PersistedToolRecord
from src.runtime.adapter_factory import load_adapter
from src.schemas.tool_io import RiskTier
from src.tools.registry import ToolDescriptor

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _resolve_handler_ref(handler_ref: str) -> Callable | None:
    """Resolve 'module.path:function_name' to a callable.

    Returns None and logs a warning if the ref cannot be resolved.
    """
    if not handler_ref or ":" not in handler_ref:
        logger.warning("Skipping tool with invalid handler_ref format: %r", handler_ref)
        return None
    module_path, func_name = handler_ref.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        logger.warning("Cannot resolve handler_ref %r: module %r not found", handler_ref, module_path)
        return None
    func = getattr(module, func_name, None)
    if func is None or not callable(func):
        logger.warning("Cannot resolve handler_ref %r: %r not callable in %r", handler_ref, func_name, module_path)
        return None
    return func


def _tool_record_to_descriptor(record: PersistedToolRecord) -> ToolDescriptor | None:
    """Convert a PersistedToolRecord to a ToolDescriptor, resolving the handler.

    Returns None if the handler cannot be resolved.
    """
    handler = _resolve_handler_ref(record.handler_ref)
    if handler is None:
        return None
    try:
        risk_tier = RiskTier(record.risk_tier)
    except ValueError:
        risk_tier = RiskTier.LOW
    return ToolDescriptor(
        name=record.name,
        handler=handler,
        risk_tier=risk_tier,
        is_state_changing=record.is_state_changing,
        timeout_ms=record.timeout_ms,
        description=record.description,
        parameters_schema=record.parameters_schema,
        metadata=record.metadata,
    )


def _provider_record_to_runtime(record: PersistedProviderRecord) -> tuple[ProviderRecord, "RuntimeAdapter"] | None:
    """Convert PersistedProviderRecord to (ProviderRecord, RuntimeAdapter).

    Returns None if the adapter cannot be loaded (e.g. missing module).
    """
    try:
        adapter = load_adapter(record.adapter_class, provider_id=record.provider_id)
    except (ValueError, ImportError) as exc:
        logger.warning("Cannot load adapter for provider %r: %s", record.provider_id, exc)
        return None
    try:
        profile = ProviderProfile(record.profile)
    except ValueError:
        profile = ProviderProfile.MANAGED_VENDOR
    try:
        api_type = EndpointApiType(record.endpoint_api_type)
    except ValueError:
        api_type = EndpointApiType.OPENAI_NATIVE
    rec = ProviderRecord(
        provider_id=record.provider_id,
        display_name=record.display_name,
        adapter_class=record.adapter_class,
        enabled=record.enabled,
        profile=profile,
        priority=record.priority,
        endpoint=EndpointConfig(base_url=record.endpoint_base_url, api_type=api_type),
        auth=AuthConfig(type=record.auth_type, api_key_env_var=record.auth_api_key_env_var),
        model_defaults=ModelDefaults(
            model=record.model,
            temperature=record.temperature,
            max_output_tokens=record.max_output_tokens,
        ),
    )
    return rec, adapter


def _agent_record_to_spec(record: PersistedAgentRecord) -> AgentSpec:
    """Convert a PersistedAgentRecord to an AgentSpec."""
    valid_tags = {t.value for t in AgentCapabilityTag}
    capability_tags = {AgentCapabilityTag(v) for v in record.capability_tags if v in valid_tags}
    return AgentSpec(
        agent_id=record.agent_id,
        role=record.role,
        capability_tags=capability_tags,
        instructions=record.instructions,
        metadata=record.metadata,
    )


async def hydrate_tenant_registries(app: "FastAPI") -> None:
    """Load all persisted tools and agents from stores into tenant in-memory registries.

    Called once at app startup. Safe to call when stores are None (no-op).
    """
    tool_store = getattr(app.state, "tool_store", None)
    agent_store = getattr(app.state, "agent_store", None)
    factory = getattr(app.state, "tenant_factory", None)

    if factory is None:
        logger.warning("hydrate_tenant_registries: tenant_factory not on app.state — skipping")
        return

    tenant_ids: set[str] = set()
    if tool_store is not None:
        tenant_ids.update(await tool_store.list_tenant_ids())
    if agent_store is not None:
        tenant_ids.update(await agent_store.list_tenant_ids())

    for tenant_id in sorted(tenant_ids):
        ctx = factory.get_or_create(tenant_id)

        if tool_store is not None:
            tool_records = await tool_store.list_tools(tenant_id)
            hydrated_tools = 0
            for record in tool_records:
                if record.name in ctx.tool_registry.list_tools():
                    continue
                descriptor = _tool_record_to_descriptor(record)
                if descriptor is None:
                    continue
                ctx.tool_registry.register(descriptor)
                hydrated_tools += 1
            if hydrated_tools:
                logger.info("Hydrated %d tool(s) for tenant %r", hydrated_tools, tenant_id)

        if agent_store is not None:
            agent_records = await agent_store.list_agents(tenant_id)
            hydrated_agents = 0
            for record in agent_records:
                try:
                    ctx.agent_registry.get(record.agent_id)
                    continue  # already present
                except KeyError:
                    pass
                spec = _agent_record_to_spec(record)
                try:
                    ctx.agent_registry.register(spec)
                    hydrated_agents += 1
                except ValueError:
                    pass  # duplicate guard — should not happen given the get() check
            if hydrated_agents:
                logger.info("Hydrated %d agent(s) for tenant %r", hydrated_agents, tenant_id)

    # Hydrate providers (dynamic registration)
    provider_store = getattr(app.state, "provider_store", None)
    provider_registry = getattr(app.state, "provider_registry", None)
    if provider_store is not None and provider_registry is not None:
        persisted = await provider_store.list_providers()
        hydrated_providers = 0
        for record in persisted:
            if record.provider_id in provider_registry._providers:
                continue
            result = _provider_record_to_runtime(record)
            if result is None:
                continue
            rec, adapter = result
            provider_registry.register(rec, adapter)
            hydrated_providers += 1
        if hydrated_providers:
            logger.info("Hydrated %d provider(s) from store", hydrated_providers)
