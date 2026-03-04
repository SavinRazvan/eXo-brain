"""
File: tools.py
Path: src/api/routers/tools.py
Role: Tool management endpoints — register, list, get, and unregister tools per tenant.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/tool_schemas.py
 - src/runtime/tenant_runtime.py
 - src/tools/registry.py
 - src/persistence/contracts.py
Notes:
 - handler_ref is resolved via importlib at registration time; unresolvable refs return 422.
 - Tools are stored in the tenant-scoped ToolRegistry — one per tenant, fully isolated.
 - Write-through to ToolStore on register/unregister (no-op when store is None, e.g. in tests).
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.dependencies import (
    get_tenant_context,
    get_tool_store,
    get_tool_version_store,
    require_valid_identity,
)
from src.api.schemas.tool_schemas import (
    ToolGovernanceResponse,
    ToolImportSchemaRequest,
    ToolImportSchemaResponse,
    ToolListResponse,
    ToolRollbackRequest,
    ToolRegisterRequest,
    ToolResponse,
    ToolValidationResponse,
    ToolVersionListResponse,
    ToolVersionUploadRequest,
)
from src.identity.contracts import IdentityContext
from src.persistence.contracts import (
    PersistedToolRecord,
    ToolPackageManifest,
    ToolStore,
    ToolValidationResult,
    ToolValidationState,
    ToolVersionRecord,
    ToolVersionStore,
)
from src.runtime.tenant_runtime import TenantRuntimeContext
from src.tools.registry import ToolDescriptor
from src.policies.tool_package_policy import validate_tool_package_upload
from src.tools.user_tool_contracts import (
    SANDBOX_LIMITS_METADATA_KEY,
    default_handler_ref,
    normalize_manifest_metadata,
    normalize_tool_payload,
    parse_sandbox_limits,
    schema_fingerprint,
)

router = APIRouter(tags=["tools"])


def _resolve_handler(handler_ref: str) -> Callable:
    """Resolve 'module.path:function_name' via importlib.

    Raises ValueError if the module or function cannot be found.
    """
    if ":" not in handler_ref:
        raise ValueError(
            f"Invalid handler_ref format '{handler_ref}'. "
            "Expected 'module.path:function_name'."
        )
    module_path, func_name = handler_ref.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ValueError(f"Module '{module_path}' not found: {exc}") from exc
    func = getattr(module, func_name, None)
    if func is None:
        raise ValueError(f"Function '{func_name}' not found in module '{module_path}'")
    if not callable(func):
        raise ValueError(f"'{func_name}' in '{module_path}' is not callable")
    return func


def _descriptor_to_response(descriptor: ToolDescriptor) -> ToolResponse:
    return ToolResponse(
        name=descriptor.name,
        description=descriptor.description,
        handler_ref=descriptor.metadata.get("handler_ref", ""),
        risk_tier=descriptor.risk_tier,
        is_state_changing=descriptor.is_state_changing,
        timeout_ms=descriptor.timeout_ms,
        parameters_schema=descriptor.parameters_schema,
    )


def _to_validation_response(record: ToolVersionRecord) -> ToolValidationResponse:
    validation = record.validation or ToolValidationResult(
        tool_name=record.tool_name,
        version=record.version,
        state=ToolValidationState.PENDING,
    )
    return ToolValidationResponse(
        tenant_id=record.tenant_id,
        tool_name=record.tool_name,
        version=record.version,
        state=validation.state.value,
        errors=validation.errors,
        warnings=validation.warnings,
        normalized_schema_hash=validation.normalized_schema_hash,
        package_ref=record.package_ref,
        active=record.active,
        created_at=record.created_at,
    )


def _validation_for_manifest(manifest: ToolPackageManifest) -> ToolValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if not manifest.tool_name.strip():
        errors.append("tool_name is required")
    if not manifest.version.strip():
        errors.append("version is required")
    if not manifest.entry_file.endswith(".py"):
        errors.append("entry_file must be a .py file")
    if not manifest.entrypoint.strip():
        errors.append("entrypoint is required")
    if not isinstance(manifest.input_schema, dict):
        errors.append("input_schema must be an object")
    try:
        limits = parse_sandbox_limits(manifest.metadata)
        if limits is None:
            warnings.append(
                f"metadata.{SANDBOX_LIMITS_METADATA_KEY} is not provided; hosted runtime uses platform defaults"
            )
        elif limits.cpu_budget_ms is not None and limits.cpu_budget_ms > manifest.timeout_ms:
            warnings.append("sandbox_limits.cpu_budget_ms exceeds timeout_ms and may never be reached")
    except ValueError as exc:
        errors.append(str(exc))
    if manifest.entrypoint != "run":
        warnings.append("entrypoint is not the standard 'run'")
    state = ToolValidationState.VALID if not errors else ToolValidationState.INVALID
    return ToolValidationResult(
        tool_name=manifest.tool_name,
        version=manifest.version,
        state=state,
        errors=errors,
        warnings=warnings,
        normalized_schema_hash=schema_fingerprint(manifest.input_schema or {}),
    )


@router.post("/{tenant_id}/tools", status_code=201, response_model=ToolResponse)
async def register_tool(
    tenant_id: str,
    body: ToolRegisterRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_store: ToolStore | None = Depends(get_tool_store),
) -> ToolResponse:
    """Register a new tool in the tenant's tool registry.

    Resolves handler_ref via importlib at registration time.
    Returns 422 if handler_ref cannot be resolved.
    Returns 409 if a tool with the same name is already registered.
    """
    if body.name in ctx.tool_registry.list_tools():
        raise HTTPException(status_code=409, detail=f"Tool '{body.name}' is already registered")

    try:
        handler = _resolve_handler(body.handler_ref)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    descriptor = ToolDescriptor(
        name=body.name,
        handler=handler,
        risk_tier=body.risk_tier,
        is_state_changing=body.is_state_changing,
        timeout_ms=body.timeout_ms,
        description=body.description,
        parameters_schema=body.parameters_schema,
        metadata={"handler_ref": body.handler_ref},
    )
    ctx.tool_registry.register(descriptor)

    if tool_store is not None:
        record = PersistedToolRecord(
            name=descriptor.name,
            handler_ref=body.handler_ref,
            tenant_id=tenant_id,
            risk_tier=descriptor.risk_tier.value,
            is_state_changing=descriptor.is_state_changing,
            timeout_ms=descriptor.timeout_ms,
            description=descriptor.description,
            parameters_schema=descriptor.parameters_schema,
            metadata=descriptor.metadata,
        )
        await tool_store.save_tool(tenant_id, record)

    return _descriptor_to_response(descriptor)


@router.post("/{tenant_id}/tools/import-schema", response_model=ToolImportSchemaResponse)
async def import_tool_schema(
    tenant_id: str,
    body: ToolImportSchemaRequest,
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ToolImportSchemaResponse:
    """Normalize user-pasted tool JSON into canonical fields for registration."""
    _ = tenant_id
    try:
        normalized = normalize_tool_payload(body.payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    tool_name = (body.tool_name or normalized.name).strip()
    if not tool_name:
        raise HTTPException(status_code=422, detail="tool_name is required (explicitly or in payload.name)")
    description = body.description.strip() or normalized.description
    handler_ref = body.handler_ref.strip() or default_handler_ref(tool_name)
    params = normalized.parameters_schema
    return ToolImportSchemaResponse(
        tool_name=tool_name,
        description=description,
        handler_ref=handler_ref,
        parameters_schema=params,
        schema_fingerprint=schema_fingerprint(params),
    )


@router.post("/{tenant_id}/tools/upload", response_model=ToolValidationResponse, status_code=201)
async def upload_tool_package(
    tenant_id: str,
    request: Request,
    body: ToolVersionUploadRequest,
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_version_store: ToolVersionStore | None = Depends(get_tool_version_store),
) -> ToolValidationResponse:
    """Register a tenant tool package version and store validation state."""
    if tool_version_store is None:
        raise HTTPException(
            status_code=503,
            detail="Tool version store is not configured (memory backend).",
        )
    rate_limiter = getattr(request.app.state, "tool_upload_rate_limiter", None)
    if rate_limiter is not None:
        allowed, _ = rate_limiter.allow(tenant_id)
        if not allowed:
            pipeline = getattr(request.app.state, "tool_audit_pipeline", None)
            if pipeline is not None:
                await pipeline.emit(
                    event_type="tool_upload_rejected_rate_limit",
                    correlation_id=f"{tenant_id}:{body.manifest.tool_name}:{body.manifest.version}",
                    tenant_id=tenant_id,
                    payload={"runtime_id": "registry_api"},
                )
            raise HTTPException(
                status_code=429,
                detail="TENANT_UPLOAD_RATE_LIMIT_EXCEEDED: too many tool uploads in the current window",
            )

    normalized_metadata = body.manifest.metadata
    try:
        normalized_metadata = normalize_manifest_metadata(body.manifest.metadata)
    except ValueError:
        # Keep raw metadata so _validation_for_manifest can record deterministic error details.
        normalized_metadata = body.manifest.metadata

    manifest = ToolPackageManifest(
        tool_name=body.manifest.tool_name,
        version=body.manifest.version,
        description=body.manifest.description,
        input_schema=body.manifest.input_schema,
        timeout_ms=body.manifest.timeout_ms,
        risk_tier=body.manifest.risk_tier.value,
        entry_file=body.manifest.entry_file,
        entrypoint=body.manifest.entrypoint,
        requirements=body.manifest.requirements,
        metadata=normalized_metadata,
    )
    policy_decision = validate_tool_package_upload(
        manifest=manifest,
        package_ref=body.package_ref,
        artifact_size_bytes=body.artifact_size_bytes,
        limits=request.app.state.settings.limits,
    )
    validation = _validation_for_manifest(manifest)
    validation.errors.extend(policy_decision.errors)
    validation.warnings.extend(policy_decision.warnings)
    if validation.errors:
        validation.state = ToolValidationState.INVALID
    record = ToolVersionRecord(
        tenant_id=tenant_id,
        tool_name=manifest.tool_name,
        version=manifest.version,
        manifest=manifest,
        validation=validation,
        package_ref=body.package_ref,
        active=False,
        created_at=datetime.now(tz=timezone.utc).isoformat(),
    )
    await tool_version_store.save_tool_version(record)
    pipeline = getattr(request.app.state, "tool_audit_pipeline", None)
    if pipeline is not None:
        await pipeline.emit(
            event_type="tool_upload_saved",
            correlation_id=f"{tenant_id}:{manifest.tool_name}:{manifest.version}",
            tenant_id=tenant_id,
            payload={
                "tool_name": manifest.tool_name,
                "version": manifest.version,
                "runtime_id": "registry_api",
                "state": validation.state.value,
                "package_ref": body.package_ref,
            },
        )
    if body.activate:
        await tool_version_store.set_active_tool_version(tenant_id, manifest.tool_name, manifest.version)
        active_record = await tool_version_store.get_tool_version(tenant_id, manifest.tool_name, manifest.version)
        if active_record is not None:
            return _to_validation_response(active_record)
    return _to_validation_response(record)


@router.get("/{tenant_id}/tools/validate/{tool_name}", response_model=ToolValidationResponse)
async def validate_tool_version(
    tenant_id: str,
    tool_name: str,
    version: str | None = Query(default=None),
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_version_store: ToolVersionStore | None = Depends(get_tool_version_store),
) -> ToolValidationResponse:
    """Return stored validation status for a tenant tool version."""
    if tool_version_store is None:
        raise HTTPException(
            status_code=503,
            detail="Tool version store is not configured (memory backend).",
        )

    record: ToolVersionRecord | None
    if version:
        record = await tool_version_store.get_tool_version(tenant_id, tool_name, version)
    else:
        record = await tool_version_store.get_active_tool_version(tenant_id, tool_name)
        if record is None:
            versions = await tool_version_store.list_tool_versions(tenant_id, tool_name)
            record = versions[0] if versions else None

    if record is None:
        raise HTTPException(status_code=404, detail=f"Tool version not found: {tool_name}")
    return _to_validation_response(record)


@router.get("/{tenant_id}/tools/versions/{tool_name}", response_model=ToolVersionListResponse)
async def list_tool_versions(
    tenant_id: str,
    tool_name: str,
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_version_store: ToolVersionStore | None = Depends(get_tool_version_store),
) -> ToolVersionListResponse:
    """List all persisted versions for one tenant tool."""
    if tool_version_store is None:
        raise HTTPException(
            status_code=503,
            detail="Tool version store is not configured (memory backend).",
        )
    versions = await tool_version_store.list_tool_versions(tenant_id, tool_name)
    return ToolVersionListResponse(
        tenant_id=tenant_id,
        tool_name=tool_name,
        versions=[_to_validation_response(v) for v in versions],
        total=len(versions),
    )


@router.get("/{tenant_id}/tools/version/{tool_name}", response_model=ToolVersionListResponse)
async def list_tool_version_alias(
    tenant_id: str,
    tool_name: str,
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_version_store: ToolVersionStore | None = Depends(get_tool_version_store),
) -> ToolVersionListResponse:
    """Backward-compatible alias for clients using singular /tools/version path."""
    return await list_tool_versions(
        tenant_id=tenant_id,
        tool_name=tool_name,
        _identity=_identity,
        tool_version_store=tool_version_store,
    )


@router.post(
    "/{tenant_id}/tools/versions/{tool_name}/{version}/deactivate",
    response_model=ToolGovernanceResponse,
)
async def deactivate_tool_version(
    tenant_id: str,
    tool_name: str,
    version: str,
    request: Request,
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_version_store: ToolVersionStore | None = Depends(get_tool_version_store),
) -> ToolGovernanceResponse:
    if tool_version_store is None:
        raise HTTPException(status_code=503, detail="Tool version store is not configured (memory backend).")
    active = await tool_version_store.get_active_tool_version(tenant_id, tool_name)
    if active is None:
        raise HTTPException(status_code=404, detail=f"No active version for tool '{tool_name}'.")
    if active.version != version:
        raise HTTPException(
            status_code=409,
            detail=f"Version '{version}' is not active for tool '{tool_name}'. Active is '{active.version}'.",
        )
    await tool_version_store.clear_active_tool_version(tenant_id, tool_name)
    pipeline = getattr(request.app.state, "tool_audit_pipeline", None)
    if pipeline is not None:
        await pipeline.emit(
            event_type="tool_version_deactivated",
            correlation_id=f"{tenant_id}:{tool_name}:{version}",
            tenant_id=tenant_id,
            payload={"tool_name": tool_name, "version": version, "runtime_id": "registry_api"},
        )
    return ToolGovernanceResponse(
        tenant_id=tenant_id,
        tool_name=tool_name,
        version=version,
        action="deactivate",
        active_version="",
        revoked=False,
    )


@router.post(
    "/{tenant_id}/tools/versions/{tool_name}/rollback",
    response_model=ToolGovernanceResponse,
)
async def rollback_tool_version(
    tenant_id: str,
    tool_name: str,
    body: ToolRollbackRequest,
    request: Request,
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_version_store: ToolVersionStore | None = Depends(get_tool_version_store),
) -> ToolGovernanceResponse:
    if tool_version_store is None:
        raise HTTPException(status_code=503, detail="Tool version store is not configured (memory backend).")
    target = await tool_version_store.get_tool_version(tenant_id, tool_name, body.target_version)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Target rollback version '{body.target_version}' was not found for tool '{tool_name}'.",
        )
    await tool_version_store.set_active_tool_version(tenant_id, tool_name, body.target_version)
    pipeline = getattr(request.app.state, "tool_audit_pipeline", None)
    if pipeline is not None:
        await pipeline.emit(
            event_type="tool_version_rollback",
            correlation_id=f"{tenant_id}:{tool_name}:{body.target_version}",
            tenant_id=tenant_id,
            payload={"tool_name": tool_name, "version": body.target_version, "runtime_id": "registry_api"},
        )
    return ToolGovernanceResponse(
        tenant_id=tenant_id,
        tool_name=tool_name,
        version=body.target_version,
        action="rollback",
        active_version=body.target_version,
        revoked=False,
    )


@router.delete(
    "/{tenant_id}/tools/versions/{tool_name}/{version}",
    response_model=ToolGovernanceResponse,
)
async def revoke_tool_package_version(
    tenant_id: str,
    tool_name: str,
    version: str,
    request: Request,
    force: bool = Query(default=False),
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_version_store: ToolVersionStore | None = Depends(get_tool_version_store),
) -> ToolGovernanceResponse:
    if tool_version_store is None:
        raise HTTPException(status_code=503, detail="Tool version store is not configured (memory backend).")
    record = await tool_version_store.get_tool_version(tenant_id, tool_name, version)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Tool version not found: {tool_name}@{version}")
    if record.active and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Tool version '{version}' is active; deactivate or use force=true to revoke.",
        )
    if record.active and force:
        await tool_version_store.clear_active_tool_version(tenant_id, tool_name)
    await tool_version_store.delete_tool_version(tenant_id, tool_name, version)
    pipeline = getattr(request.app.state, "tool_audit_pipeline", None)
    if pipeline is not None:
        await pipeline.emit(
            event_type="tool_package_revoked",
            correlation_id=f"{tenant_id}:{tool_name}:{version}",
            tenant_id=tenant_id,
            payload={
                "tool_name": tool_name,
                "version": version,
                "runtime_id": "registry_api",
                "force": bool(force),
            },
        )
    active_after = await tool_version_store.get_active_tool_version(tenant_id, tool_name)
    return ToolGovernanceResponse(
        tenant_id=tenant_id,
        tool_name=tool_name,
        version=version,
        action="revoke",
        active_version=active_after.version if active_after is not None else "",
        revoked=True,
    )


@router.get("/{tenant_id}/tools", response_model=ToolListResponse)
async def list_tools(
    tenant_id: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ToolListResponse:
    """List all tools registered in the tenant's registry."""
    descriptors = ctx.tool_registry.list_descriptors()
    return ToolListResponse(
        tools=[_descriptor_to_response(d) for d in descriptors],
        total=len(descriptors),
    )


@router.get("/{tenant_id}/tools/{name}", response_model=ToolResponse)
async def get_tool(
    tenant_id: str,
    name: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
) -> ToolResponse:
    """Get the full descriptor for a single tool."""
    try:
        descriptor = ctx.tool_registry.resolve(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
    return _descriptor_to_response(descriptor)


@router.delete("/{tenant_id}/tools/{name}", status_code=204)
async def unregister_tool(
    tenant_id: str,
    name: str,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_store: ToolStore | None = Depends(get_tool_store),
) -> None:
    """Unregister a tool from the tenant's registry."""
    try:
        ctx.tool_registry.unregister(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")

    if tool_store is not None:
        await tool_store.delete_tool(tenant_id, name)
