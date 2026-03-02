"""
File: tenant_runtime.py
Path: src/runtime/tenant_runtime.py
Role: Tenant-scoped runtime context and factory for per-tenant, per-session isolation.
Used By:
 - src/api/bootstrap.py (future)
 - src/api/dependencies.py (future)
Depends On:
 - src/agents/registry.py
 - src/config/provider_registry.py
 - src/config/settings.py
 - src/core/orchestrator.py
 - src/core/session_store.py
 - src/integration/host_adapter.py
 - src/policies/middleware.py
 - src/tenancy/quotas.py
 - src/tools/executor.py
 - src/tools/registry.py
Notes:
 - TenantRuntimeContext holds ONLY tenant-scoped state. Orchestrator and host_adapter
   are per-session, not per-tenant — they live in TenantRuntimeFactory._session_runtimes.
 - create_session_runtime resolves AgentSpec here so adapters never need agent_registry.
 - build_agent_tools is called inside run_turn (late binding) — not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.agents.registry import AgentRegistry
from src.config.provider_registry import ProviderRegistry
from src.config.settings import AppSettings
from src.core.orchestrator import Orchestrator
from src.core.session_store import InMemorySessionStore, SessionStore
from src.integration.host_adapter import OrchestratorHostAdapter
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.tenancy.quotas import TenantQuotaManager
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolRegistry


@dataclass(slots=True)
class TenantRuntimeContext:
    """Tenant-scoped state only.

    orchestrator and host_adapter are intentionally absent — they are per-session
    and live in TenantRuntimeFactory._session_runtimes keyed by session_id.
    """

    tenant_id: str
    tool_registry: ToolRegistry
    policy_middleware: DeterministicFirstPolicyMiddleware
    tool_executor: DeterministicToolExecutor
    agent_registry: AgentRegistry
    session_store: SessionStore
    quota_manager: TenantQuotaManager


class TenantRuntimeFactory:
    """Creates and caches TenantRuntimeContext instances and per-session OrchestratorHostAdapters.

    One factory instance is shared for the lifetime of the application process.
    """

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        settings: AppSettings,
    ) -> None:
        self._provider_registry = provider_registry
        self._settings = settings
        self._contexts: dict[str, TenantRuntimeContext] = {}
        self._session_runtimes: dict[str, OrchestratorHostAdapter] = {}
        self._session_adapters: dict[str, "RuntimeAdapter"] = {}
        self._session_tenant: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Tenant context
    # ------------------------------------------------------------------

    def get_or_create(self, tenant_id: str) -> TenantRuntimeContext:
        """Return cached context or build fresh tenant-scoped runtime state."""
        if tenant_id not in self._contexts:
            self._contexts[tenant_id] = self._build_context(tenant_id)
        return self._contexts[tenant_id]

    def _build_context(self, tenant_id: str) -> TenantRuntimeContext:
        tool_registry = ToolRegistry()
        policy_middleware = DeterministicFirstPolicyMiddleware()
        tool_executor = DeterministicToolExecutor(
            registry=tool_registry,
            policy=policy_middleware,
        )
        agent_registry = AgentRegistry()
        session_store: SessionStore = InMemorySessionStore()
        quota_manager = TenantQuotaManager()
        return TenantRuntimeContext(
            tenant_id=tenant_id,
            tool_registry=tool_registry,
            policy_middleware=policy_middleware,
            tool_executor=tool_executor,
            agent_registry=agent_registry,
            session_store=session_store,
            quota_manager=quota_manager,
        )

    # ------------------------------------------------------------------
    # Session runtime
    # ------------------------------------------------------------------

    def create_session_runtime(
        self,
        tenant_context: TenantRuntimeContext,
        agent_id: str,
        provider_id: str,
        session_id: str,
    ) -> OrchestratorHostAdapter:
        """Build and cache a per-session OrchestratorHostAdapter.

        AgentSpec is resolved here so the adapter never needs agent_registry.
        Raises KeyError if agent_id or provider_id is not registered.
        """
        spec = tenant_context.agent_registry.get(agent_id)

        from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter

        adapter = OpenAIAgentsRuntimeAdapter(
            provider_id=provider_id,
            tool_registry=tenant_context.tool_registry,
            tool_executor=tenant_context.tool_executor,
        )

        import asyncio

        coro = adapter.start_session(
            session_id=session_id,
            metadata={
                "instructions": spec.instructions,
                "agent_id": spec.agent_id,
                "model": spec.metadata.get("model", "gpt-4o-mini"),
            },
        )
        try:
            loop = asyncio.get_running_loop()
            # If we're already inside a running event loop (async context), schedule
            # start_session as a fire-and-forget task.  The metadata dict is written
            # synchronously inside start_session before any await point, so the
            # session is immediately usable.
            loop.create_task(coro)
        except RuntimeError:
            # No running event loop — safe to run synchronously (e.g. in tests).
            asyncio.run(coro)

        orchestrator = Orchestrator(
            runtime_adapter=adapter,
            policy_middleware=tenant_context.policy_middleware,
            tool_executor=tenant_context.tool_executor,
            agent_registry=tenant_context.agent_registry,
        )
        host_adapter = OrchestratorHostAdapter(orchestrator)
        self._session_runtimes[session_id] = host_adapter
        self._session_adapters[session_id] = adapter
        self._session_tenant[session_id] = tenant_context.tenant_id
        return host_adapter

    def get_session_adapter(self, session_id: str) -> "RuntimeAdapter":
        """Return the runtime adapter for a session — used in tests and diagnostics."""
        adapter = self._session_adapters.get(session_id)
        if adapter is None:
            raise KeyError(f"No session adapter found for session_id '{session_id}'")
        return adapter

    def get_session_runtime(self, session_id: str) -> OrchestratorHostAdapter:
        """Return cached session runtime or raise KeyError."""
        runtime = self._session_runtimes.get(session_id)
        if runtime is None:
            raise KeyError(f"No session runtime found for session_id '{session_id}'")
        return runtime

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def list_tenants(self) -> list[str]:
        return sorted(self._contexts.keys())

    def destroy(self, tenant_id: str) -> None:
        """Evict tenant context and all session runtimes belonging to that tenant."""
        sessions_to_remove = [
            sid for sid, tid in self._session_tenant.items() if tid == tenant_id
        ]
        for sid in sessions_to_remove:
            del self._session_runtimes[sid]
            self._session_adapters.pop(sid, None)
            del self._session_tenant[sid]
        self._contexts.pop(tenant_id, None)
