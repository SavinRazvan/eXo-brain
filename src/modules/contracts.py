"""
File: contracts.py
Path: src/modules/contracts.py
Role: Canonical module catalog and dependency rules for the modular monolith.
Used By:
 - scripts/architecture/validate_layers.py
 - src/modules/platform_bootstrap/service.py
Depends On:
 - dataclasses
Notes:
 - Boundary checks are strict for files under `src/modules/` and advisory for legacy ownership mappings.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    name: str
    public_api_imports: tuple[str, ...]
    allowed_dependencies: tuple[str, ...]
    path_prefixes: tuple[str, ...]
    import_prefixes: tuple[str, ...]


MODULE_SPECS: dict[str, ModuleSpec] = {
    "identity_access": ModuleSpec(
        name="identity_access",
        public_api_imports=("src.modules.identity_access.service",),
        allowed_dependencies=("shared_kernel",),
        path_prefixes=(
            "src/modules/identity_access/",
            "src/identity/",
            "src/access_control/",
            "src/api/middleware/auth.py",
            "src/api/routers/admin_keys.py",
        ),
        import_prefixes=(
            "src.modules.identity_access",
            "src.identity",
            "src.access_control",
            "src.api.middleware.auth",
            "src.api.routers.admin_keys",
        ),
    ),
    "tenant_governance": ModuleSpec(
        name="tenant_governance",
        public_api_imports=("src.modules.tenant_governance.service",),
        allowed_dependencies=("shared_kernel", "identity_access", "audit_observability"),
        path_prefixes=(
            "src/modules/tenant_governance/",
            "src/tenancy/",
            "src/policies/",
            "src/api/middleware/entitlements.py",
        ),
        import_prefixes=(
            "src.modules.tenant_governance",
            "src.tenancy",
            "src.policies",
            "src.api.middleware.entitlements",
        ),
    ),
    "provider_management": ModuleSpec(
        name="provider_management",
        public_api_imports=("src.modules.provider_management.service",),
        allowed_dependencies=("shared_kernel", "identity_access", "adapter_contracts"),
        path_prefixes=(
            "src/modules/provider_management/",
            "src/config/provider_registry.py",
            "src/runtime/adapter_factory.py",
            "src/runtime/capability_map.py",
            "src/api/routers/providers.py",
        ),
        import_prefixes=(
            "src.modules.provider_management",
            "src.config.provider_registry",
            "src.runtime.adapter_factory",
            "src.runtime.capability_map",
            "src.api.routers.providers",
        ),
    ),
    "agent_management": ModuleSpec(
        name="agent_management",
        public_api_imports=("src.modules.agent_management.service",),
        allowed_dependencies=("shared_kernel",),
        path_prefixes=("src/modules/agent_management/", "src/agents/", "src/api/routers/agents.py"),
        import_prefixes=("src.modules.agent_management", "src.agents", "src.api.routers.agents"),
    ),
    "tool_management": ModuleSpec(
        name="tool_management",
        public_api_imports=("src.modules.tool_management.service",),
        allowed_dependencies=("shared_kernel", "tenant_governance", "audit_observability"),
        path_prefixes=(
            "src/modules/tool_management/",
            "src/api/routers/tools.py",
            "src/tools/registry.py",
            "src/tools/artifact_store.py",
            "src/tools/version_projection.py",
            "src/tools/user_tool_contracts.py",
            "src/tools/user_tools.py",
        ),
        import_prefixes=(
            "src.modules.tool_management",
            "src.api.routers.tools",
            "src.tools.registry",
            "src.tools.artifact_store",
            "src.tools.version_projection",
            "src.tools.user_tool_contracts",
            "src.tools.user_tools",
        ),
    ),
    "session_runtime": ModuleSpec(
        name="session_runtime",
        public_api_imports=("src.modules.session_runtime.service",),
        allowed_dependencies=(
            "shared_kernel",
            "agent_management",
            "tool_management",
            "provider_management",
            "tenant_governance",
            "adapter_contracts",
            "turn_execution",
        ),
        path_prefixes=(
            "src/modules/session_runtime/",
            "src/api/routers/sessions.py",
            "src/api/routers/runtime_control.py",
            "src/runtime/tenant_runtime.py",
            "src/core/session_store.py",
            "src/core/run_control_registry.py",
        ),
        import_prefixes=(
            "src.modules.session_runtime",
            "src.api.routers.sessions",
            "src.api.routers.runtime_control",
            "src.runtime.tenant_runtime",
            "src.core.session_store",
            "src.core.run_control_registry",
        ),
    ),
    "turn_execution": ModuleSpec(
        name="turn_execution",
        public_api_imports=("src.modules.turn_execution.service",),
        allowed_dependencies=(
            "shared_kernel",
            "tenant_governance",
            "audit_observability",
            "adapter_contracts",
            "tool_management",
        ),
        path_prefixes=(
            "src/modules/turn_execution/",
            "src/api/routers/turns.py",
            "src/core/orchestrator.py",
            "src/runtime/mode_selector.py",
            "src/integration/host_adapter.py",
            "src/tools/executor.py",
            "src/tools/execution_adapter.py",
        ),
        import_prefixes=(
            "src.modules.turn_execution",
            "src.api.routers.turns",
            "src.core.orchestrator",
            "src.runtime.mode_selector",
            "src.integration.host_adapter",
            "src.tools.executor",
            "src.tools.execution_adapter",
        ),
    ),
    "audit_observability": ModuleSpec(
        name="audit_observability",
        public_api_imports=("src.modules.audit_observability.service",),
        allowed_dependencies=("shared_kernel",),
        path_prefixes=(
            "src/modules/audit_observability/",
            "src/api/routers/audit.py",
            "src/observability/",
            "src/audit/",
            "src/compliance/",
            "src/persistence/audit_store.py",
            "src/persistence/adapters/sqlite_audit.py",
        ),
        import_prefixes=(
            "src.modules.audit_observability",
            "src.api.routers.audit",
            "src.observability",
            "src.audit",
            "src.compliance",
            "src.persistence.audit_store",
            "src.persistence.adapters.sqlite_audit",
        ),
    ),
    "platform_bootstrap": ModuleSpec(
        name="platform_bootstrap",
        public_api_imports=("src.modules.platform_bootstrap.service",),
        allowed_dependencies=(
            "identity_access",
            "tenant_governance",
            "provider_management",
            "agent_management",
            "tool_management",
            "session_runtime",
            "turn_execution",
            "audit_observability",
            "adapter_contracts",
            "shared_kernel",
        ),
        path_prefixes=(
            "src/modules/platform_bootstrap/",
            "src/api/app.py",
            "src/api/bootstrap.py",
            "src/api/startup.py",
            "src/api/readiness.py",
            "src/api/routers/prometheus_metrics.py",
            "src/config/settings.py",
        ),
        import_prefixes=(
            "src.modules.platform_bootstrap",
            "src.api.app",
            "src.api.bootstrap",
            "src.api.startup",
            "src.api.readiness",
            "src.api.routers.prometheus_metrics",
            "src.config.settings",
        ),
    ),
    "shared_kernel": ModuleSpec(
        name="shared_kernel",
        public_api_imports=("src.schemas",),
        allowed_dependencies=(),
        path_prefixes=("src/schemas/", "src/identity/contracts.py"),
        import_prefixes=("src.schemas", "src.identity.contracts"),
    ),
    "adapter_contracts": ModuleSpec(
        name="adapter_contracts",
        public_api_imports=("src.runtime.runtime_adapter", "src.tools.execution_adapter"),
        allowed_dependencies=("shared_kernel",),
        path_prefixes=("src/runtime/runtime_adapter.py", "src/tools/execution_adapter.py"),
        import_prefixes=("src.runtime.runtime_adapter", "src.tools.execution_adapter"),
    ),
}


def all_module_names() -> tuple[str, ...]:
    return tuple(MODULE_SPECS.keys())


def module_name_for_import(import_path: str) -> str | None:
    normalized = str(import_path or "").strip()
    if not normalized:
        return None
    matched: tuple[str, int] | None = None
    for name, spec in MODULE_SPECS.items():
        for prefix in spec.import_prefixes:
            if normalized == prefix or normalized.startswith(f"{prefix}."):
                prefix_len = len(prefix)
                if matched is None or prefix_len > matched[1]:
                    matched = (name, prefix_len)
    return matched[0] if matched is not None else None


def module_name_for_path(repo_relative_path: str) -> str | None:
    normalized = str(repo_relative_path or "").replace("\\", "/").strip()
    if not normalized:
        return None
    matched: tuple[str, int] | None = None
    for name, spec in MODULE_SPECS.items():
        for prefix in spec.path_prefixes:
            if normalized == prefix or normalized.startswith(prefix):
                prefix_len = len(prefix)
                if matched is None or prefix_len > matched[1]:
                    matched = (name, prefix_len)
    return matched[0] if matched is not None else None


def allowed_dependencies_for_module(module_name: str) -> set[str]:
    spec = MODULE_SPECS.get(module_name)
    if spec is None:
        return set()
    return set(spec.allowed_dependencies)


def is_public_module_import(import_path: str) -> bool:
    normalized = str(import_path or "").strip()
    if not normalized:
        return False
    for spec in MODULE_SPECS.values():
        for prefix in spec.public_api_imports:
            if normalized == prefix or normalized.startswith(f"{prefix}."):
                return True
    return False
