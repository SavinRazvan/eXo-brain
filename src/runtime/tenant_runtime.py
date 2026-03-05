"""
File: tenant_runtime.py
Path: src/runtime/tenant_runtime.py
Role: Tenant-scoped runtime context and factory for per-tenant, per-session isolation.
Used By:
 - src/api/bootstrap.py
 - src/api/dependencies.py
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
 - If session_store is passed to TenantRuntimeFactory, all tenants share that store
   (SQLite handles per-tenant isolation via tenant_id column).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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
from src.tools.sandbox.pool import TenantSandboxPool


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
        session_store: SessionStore | None = None,
    ) -> None:
        self._provider_registry = provider_registry
        self._settings = settings
        self._session_store = session_store
        self._contexts: dict[str, TenantRuntimeContext] = {}
        self._session_runtimes: dict[str, OrchestratorHostAdapter] = {}
        self._session_adapters: dict[str, "RuntimeAdapter"] = {}
        self._session_tenant: dict[str, str] = {}
        self._sandbox_pool: TenantSandboxPool | None = (
            TenantSandboxPool(max_workers_per_tenant=1)
            if self._settings.runtime.enable_hosted_tool_runtime
            else None
        )

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
        execution_adapter = None
        if self._settings.runtime.enable_byoc_tool_runtime:
            from src.tools.byoc import TenantByocConnectorRuntime
            from src.tools.byoc.result_store import (
                ByocResultConflictStrategy,
                InMemoryByocResultStore,
                InMemoryReplayGuard,
            )
            from src.tools.byoc.job_store import InMemoryByocJobQueueStore
            from src.tools.byoc.sqlite_store import (
                SQLiteByocJobQueueStore,
                SQLiteByocResultStore,
                SQLiteReplayGuard,
            )

            if self._settings.runtime.byoc_store_backend == "sqlite":
                db_path = Path(self._settings.runtime.byoc_sqlite_db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                strategy_raw = str(self._settings.runtime.byoc_result_conflict_strategy).strip().lower()
                try:
                    conflict_strategy = ByocResultConflictStrategy(strategy_raw)
                except ValueError:
                    conflict_strategy = ByocResultConflictStrategy.FIRST_WRITE_WINS
                job_store = SQLiteByocJobQueueStore(str(db_path))
                result_store = SQLiteByocResultStore(str(db_path), conflict_strategy=conflict_strategy)
                replay_guard = SQLiteReplayGuard(str(db_path))
            else:
                strategy_raw = str(self._settings.runtime.byoc_result_conflict_strategy).strip().lower()
                try:
                    conflict_strategy = ByocResultConflictStrategy(strategy_raw)
                except ValueError:
                    conflict_strategy = ByocResultConflictStrategy.FIRST_WRITE_WINS
                job_store = InMemoryByocJobQueueStore()
                result_store = InMemoryByocResultStore(conflict_strategy=conflict_strategy)
                replay_guard = InMemoryReplayGuard()

            execution_adapter = TenantByocConnectorRuntime(
                worker_jwt_secret=self._settings.runtime.byoc_worker_jwt_secret,
                worker_token_ttl_seconds=self._settings.runtime.byoc_worker_token_ttl_seconds,
                lease_ttl_seconds=self._settings.runtime.byoc_lease_ttl_seconds,
                replay_ttl_seconds=self._settings.runtime.byoc_replay_ttl_seconds,
                cleanup_interval_seconds=self._settings.runtime.byoc_cleanup_interval_seconds,
                completed_ttl_seconds=self._settings.runtime.byoc_completed_ttl_seconds,
                cancelled_ttl_seconds=self._settings.runtime.byoc_cancelled_ttl_seconds,
                result_ttl_seconds=self._settings.runtime.byoc_result_ttl_seconds,
                idempotency_ttl_seconds=self._settings.runtime.byoc_idempotency_ttl_seconds,
                max_completed_records=self._settings.runtime.byoc_max_completed_records,
                max_cancelled_records=self._settings.runtime.byoc_max_cancelled_records,
                max_result_records=self._settings.runtime.byoc_max_result_records,
                max_claim_attempts_before_dlq=self._settings.runtime.byoc_max_claim_attempts_before_dlq,
                cost_limit_microunits_per_tenant=self._settings.runtime.byoc_cost_limit_microunits_per_tenant,
                enforce_cost_limit=self._settings.runtime.byoc_enforce_cost_limit,
                enable_cost_window_policy=self._settings.runtime.byoc_enable_cost_window_policy,
                cost_window_seconds=self._settings.runtime.byoc_cost_window_seconds,
                cost_success_microunits=self._settings.runtime.byoc_cost_success_microunits,
                cost_error_microunits=self._settings.runtime.byoc_cost_error_microunits,
                cost_timeout_microunits=self._settings.runtime.byoc_cost_timeout_microunits,
                cost_cancelled_microunits=self._settings.runtime.byoc_cost_cancelled_microunits,
                fair_admission_enabled=self._settings.runtime.byoc_fair_admission_enabled,
                fair_admission_max_inflight_global=self._settings.runtime.byoc_fair_admission_max_inflight_global,
                fair_admission_wait_timeout_ms=self._settings.runtime.byoc_fair_admission_wait_timeout_ms,
                job_store=job_store,
                result_store=result_store,
                replay_guard=replay_guard,
            )
        elif self._settings.runtime.enable_hosted_tool_runtime:
            from src.tools.sandbox.runtime import TenantSandboxToolRuntime

            execution_adapter = TenantSandboxToolRuntime(
                runtime_pool=self._sandbox_pool,
                enable_process_isolation=self._settings.runtime.enable_hosted_tool_process_isolation,
            )
        tool_executor = DeterministicToolExecutor(
            registry=tool_registry,
            policy=policy_middleware,
            execution_adapter=execution_adapter,
            enable_hosted_runtime=(
                self._settings.runtime.enable_hosted_tool_runtime
                or self._settings.runtime.enable_byoc_tool_runtime
            ),
        )
        agent_registry = AgentRegistry()
        session_store: SessionStore = self._session_store or InMemorySessionStore()
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
                "tenant_id": tenant_context.tenant_id,
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

    def evict_sessions_for_provider(self, provider_id: str) -> int:
        """Remove cached session runtimes currently bound to provider_id."""
        removed = 0
        sessions_to_remove: list[str] = []
        for sid, adapter in self._session_adapters.items():
            adapter_provider = str(getattr(adapter, "_provider_id", "")).strip()
            if adapter_provider == provider_id:
                sessions_to_remove.append(sid)
        for sid in sessions_to_remove:
            self._session_runtimes.pop(sid, None)
            self._session_adapters.pop(sid, None)
            self._session_tenant.pop(sid, None)
            removed += 1
        return removed
