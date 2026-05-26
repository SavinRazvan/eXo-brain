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
 - src/runtime/runtime_adapter.py
 - src/policies/middleware.py
 - src/tenancy/quotas.py
 - src/tools/executor.py
 - src/tools/registry.py
 Notes:
 - TenantRuntimeContext holds ONLY tenant-scoped state. Orchestrator and host_adapter
   are per-session, not per-tenant — they live in TenantRuntimeFactory._session_runtimes.
 - Session adapter/runtime caches honor idle TTL and max entry limits when configured.
 - Optional cap on cached tenant contexts (`tenant_runtime_max_cached_contexts`) evicts LRU tenants.
 - Background `start_session` tasks log failures via done-callback (no silent asyncio failures).
 - create_session_runtime resolves AgentSpec here so adapters never need agent_registry.
 - build_agent_tools is called inside run_turn (late binding) — not here.
 - If session_store is passed to TenantRuntimeFactory, all tenants share that store
   (SQLite handles per-tenant isolation via tenant_id column).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Coroutine
from typing import Any
import asyncio
import logging
import time

from src.agents.registry import AgentRegistry
from src.config.provider_registry import ProviderRegistry
from src.config.settings import AppSettings
from src.core.orchestrator import Orchestrator
from src.core.session_store import InMemorySessionStore, SessionStore
from src.integration.host_adapter import OrchestratorHostAdapter
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.runtime.runtime_adapter import RuntimeAdapter
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


class TenantContextBuilder:
    """Build tenant-scoped registries and tool-runtime wiring."""

    def __init__(
        self,
        *,
        settings: AppSettings,
        session_store: SessionStore | None,
        sandbox_pool: TenantSandboxPool | None,
    ) -> None:
        self._settings = settings
        self._session_store = session_store
        self._sandbox_pool = sandbox_pool

    def build(self, tenant_id: str) -> TenantRuntimeContext:
        tool_registry = ToolRegistry()
        policy_middleware = DeterministicFirstPolicyMiddleware()
        execution_adapter = self._build_execution_adapter()
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

    def _build_execution_adapter(self):
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

            strategy_raw = str(self._settings.runtime.byoc_result_conflict_strategy).strip().lower()
            try:
                conflict_strategy = ByocResultConflictStrategy(strategy_raw)
            except ValueError:
                conflict_strategy = ByocResultConflictStrategy.FIRST_WRITE_WINS

            if self._settings.runtime.byoc_store_backend == "sqlite":
                db_path = Path(self._settings.runtime.byoc_sqlite_db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                job_store = SQLiteByocJobQueueStore(str(db_path))
                result_store = SQLiteByocResultStore(str(db_path), conflict_strategy=conflict_strategy)
                replay_guard = SQLiteReplayGuard(str(db_path))
            else:
                job_store = InMemoryByocJobQueueStore()
                result_store = InMemoryByocResultStore(conflict_strategy=conflict_strategy)
                replay_guard = InMemoryReplayGuard()

            return TenantByocConnectorRuntime(
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
                budget_partition_scope=self._settings.runtime.byoc_budget_partition_scope,
                budget_partition_limits_microunits=self._settings.runtime.byoc_budget_partition_limits_microunits,
                fair_admission_enabled=self._settings.runtime.byoc_fair_admission_enabled,
                fair_admission_max_inflight_global=self._settings.runtime.byoc_fair_admission_max_inflight_global,
                fair_admission_wait_timeout_ms=self._settings.runtime.byoc_fair_admission_wait_timeout_ms,
                fair_admission_backend=self._settings.runtime.byoc_fair_admission_backend,
                fair_admission_sqlite_db_path=self._settings.runtime.control_state_sqlite_db_path,
                non_blocking_execute=self._settings.runtime.byoc_non_blocking_execute,
                job_store=job_store,
                result_store=result_store,
                replay_guard=replay_guard,
            )
        if self._settings.runtime.enable_hosted_tool_runtime:
            from src.tools.sandbox.runtime import TenantSandboxToolRuntime

            return TenantSandboxToolRuntime(
                runtime_pool=self._sandbox_pool,
                enable_process_isolation=self._settings.runtime.enable_hosted_tool_process_isolation,
            )
        return None


class SessionAdapterResolver:
    """Resolve a fresh session adapter from provider-management state."""

    def __init__(self, provider_registry: ProviderRegistry) -> None:
        self._provider_registry = provider_registry

    def resolve(
        self,
        *,
        tenant_context: TenantRuntimeContext,
        provider_id: str,
    ) -> RuntimeAdapter:
        from src.runtime.adapter_factory import load_adapter

        provider = self._provider_registry.get(provider_id)
        adapter_class_ref = str(provider.adapter_class).strip()
        init_kwargs = {
            "tool_registry": tenant_context.tool_registry,
            "tool_executor": tenant_context.tool_executor,
        }

        try:
            return load_adapter(adapter_class_ref, provider_id=provider_id, **init_kwargs)
        except TypeError:
            return load_adapter(adapter_class_ref, provider_id=provider_id)
        except (ImportError, ValueError):
            pass

        registered_adapter = self._provider_registry.get_adapter(provider_id)
        adapter_cls = type(registered_adapter)
        try:
            return adapter_cls(provider_id=provider_id, **init_kwargs)  # type: ignore[call-arg]
        except TypeError:
            try:
                return adapter_cls(provider_id=provider_id)  # type: ignore[call-arg]
            except TypeError:
                return adapter_cls()


_LOGGER = logging.getLogger(__name__)


def _log_adapter_start_session_done(task: asyncio.Task[Any], *, session_id: str) -> None:
    """Log exceptions from background `start_session` tasks; ignore cancellation."""

    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        _LOGGER.error(
            "adapter.start_session failed session_id=%s: %s",
            session_id,
            exc,
            exc_info=exc,
        )


class SessionRuntimeAssembler:
    """Create per-session orchestrator/host-adapter pairs."""

    def __init__(self, adapter_resolver: SessionAdapterResolver) -> None:
        self._adapter_resolver = adapter_resolver

    @staticmethod
    def _schedule_start_session(coro: Coroutine[Any, Any, Any], *, session_id: str) -> None:
        """Run start_session; schedule under running loop with error logging, or block with asyncio.run."""

        def _on_done(t: asyncio.Task[Any]) -> None:
            _log_adapter_start_session_done(t, session_id=session_id)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return
        task = loop.create_task(coro)
        task.add_done_callback(_on_done)

    def create(
        self,
        *,
        tenant_context: TenantRuntimeContext,
        agent_id: str,
        provider_id: str,
        session_id: str,
    ) -> tuple[OrchestratorHostAdapter, RuntimeAdapter]:
        spec = tenant_context.agent_registry.get(agent_id)
        adapter = self._adapter_resolver.resolve(
            tenant_context=tenant_context,
            provider_id=provider_id,
        )

        coro = adapter.start_session(
            session_id=session_id,
            metadata={
                "instructions": spec.instructions,
                "agent_id": spec.agent_id,
                "model": spec.metadata.get("model", "gpt-4o-mini"),
                "tenant_id": tenant_context.tenant_id,
            },
        )
        self._schedule_start_session(coro, session_id=session_id)

        orchestrator = Orchestrator(
            runtime_adapter=adapter,
            policy_middleware=tenant_context.policy_middleware,
            tool_executor=tenant_context.tool_executor,
            agent_registry=tenant_context.agent_registry,
        )
        return OrchestratorHostAdapter(orchestrator), adapter


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
        self._tenant_last_touch: dict[str, float] = {}
        self._session_runtimes: dict[str, OrchestratorHostAdapter] = {}
        self._session_adapters: dict[str, RuntimeAdapter] = {}
        self._session_tenant: dict[str, str] = {}
        self._session_last_access: dict[str, float] = {}
        self._sandbox_pool: TenantSandboxPool | None = (
            TenantSandboxPool(max_workers_per_tenant=1)
            if self._settings.runtime.enable_hosted_tool_runtime
            else None
        )
        self._context_builder = TenantContextBuilder(
            settings=self._settings,
            session_store=self._session_store,
            sandbox_pool=self._sandbox_pool,
        )
        self._adapter_resolver = SessionAdapterResolver(self._provider_registry)
        self._session_runtime_assembler = SessionRuntimeAssembler(self._adapter_resolver)

    # ------------------------------------------------------------------
    # Tenant context
    # ------------------------------------------------------------------

    def _evict_idle_sessions_only(self) -> None:
        ttl = int(self._settings.runtime.session_runtime_idle_ttl_seconds)
        if ttl <= 0:
            return
        now = time.monotonic()
        stale = [sid for sid, ts in self._session_last_access.items() if now - ts > ttl]
        for sid in stale:
            self._session_runtimes.pop(sid, None)
            self._session_adapters.pop(sid, None)
            self._session_tenant.pop(sid, None)
            self._session_last_access.pop(sid, None)

    def _evict_lru_until_under_cap(self) -> None:
        max_sess = int(self._settings.runtime.session_runtime_max_cached_sessions)
        if max_sess <= 0:
            return
        sorted_sids = sorted(self._session_last_access.items(), key=lambda item: item[1])
        for sid, _ in sorted_sids:
            if len(self._session_runtimes) < max_sess:
                break
            if sid in self._session_runtimes:
                self._session_runtimes.pop(sid, None)
                self._session_adapters.pop(sid, None)
                self._session_tenant.pop(sid, None)
                self._session_last_access.pop(sid, None)

    def _touch_session(self, session_id: str) -> None:
        self._session_last_access[session_id] = time.monotonic()

    def _evict_tenant_contexts_over_capacity(self, incoming_tenant_id: str) -> None:
        cap = int(self._settings.runtime.tenant_runtime_max_cached_contexts)
        if cap <= 0:
            return
        if incoming_tenant_id in self._contexts:
            return
        while len(self._contexts) >= cap and self._contexts:
            victim = min(self._contexts.keys(), key=lambda tid: self._tenant_last_touch.get(tid, 0.0))
            self.destroy(victim)

    def get_or_create(self, tenant_id: str) -> TenantRuntimeContext:
        """Return cached context or build fresh tenant-scoped runtime state."""
        self._evict_idle_sessions_only()
        self._evict_tenant_contexts_over_capacity(tenant_id)
        if tenant_id not in self._contexts:
            self._contexts[tenant_id] = self._build_context(tenant_id)
        self._tenant_last_touch[tenant_id] = time.monotonic()
        return self._contexts[tenant_id]

    def _build_context(self, tenant_id: str) -> TenantRuntimeContext:
        return self._context_builder.build(tenant_id)

    # ------------------------------------------------------------------
    # Session runtime
    # ------------------------------------------------------------------

    def _instantiate_session_adapter(
        self,
        tenant_context: TenantRuntimeContext,
        provider_id: str,
    ) -> RuntimeAdapter:
        """Resolve and instantiate a fresh adapter for a session.

        Preferred path: use provider_record.adapter_class via adapter_factory.
        Compatibility path: if adapter_class is legacy/non-dotted, instantiate from
        the currently registered adapter type.
        """
        return self._adapter_resolver.resolve(
            tenant_context=tenant_context,
            provider_id=provider_id,
        )

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
        self._evict_idle_sessions_only()
        self._evict_lru_until_under_cap()
        host_adapter, adapter = self._session_runtime_assembler.create(
            tenant_context=tenant_context,
            agent_id=agent_id,
            provider_id=provider_id,
            session_id=session_id,
        )
        self._session_runtimes[session_id] = host_adapter
        self._session_adapters[session_id] = adapter
        self._session_tenant[session_id] = tenant_context.tenant_id
        self._touch_session(session_id)
        return host_adapter

    def get_session_adapter(self, session_id: str) -> RuntimeAdapter:
        """Return the runtime adapter for a session — used in tests and diagnostics."""
        self._evict_idle_sessions_only()
        adapter = self._session_adapters.get(session_id)
        if adapter is None:
            raise KeyError(f"No session adapter found for session_id '{session_id}'")
        self._touch_session(session_id)
        return adapter

    def get_session_runtime(self, session_id: str) -> OrchestratorHostAdapter:
        """Return cached session runtime or raise KeyError."""
        self._evict_idle_sessions_only()
        runtime = self._session_runtimes.get(session_id)
        if runtime is None:
            raise KeyError(f"No session runtime found for session_id '{session_id}'")
        self._touch_session(session_id)
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
            self._session_last_access.pop(sid, None)
        self._contexts.pop(tenant_id, None)
        self._tenant_last_touch.pop(tenant_id, None)

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
            self._session_last_access.pop(sid, None)
            removed += 1
        return removed
