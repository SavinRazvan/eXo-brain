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
    get_app_modules,
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
from src.tools.version_projection import descriptor_from_tool_version
from src.tools.version_projection import INLINE_HANDLER_SOURCE_METADATA_KEY, validate_inline_handler_source
from src.tools.version_projection import verify_artifact_bundle_integrity
from src.tools.artifact_store import (
    ARTIFACT_BUNDLE_DIR_METADATA_KEY,
    ARTIFACT_BUNDLE_HASH_METADATA_KEY,
    ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY,
    ARTIFACT_HANDLER_PATH_METADATA_KEY,
    ARTIFACT_MANIFEST_PATH_METADATA_KEY,
    ARTIFACT_SIGNATURE_VERSION_METADATA_KEY,
    DEFAULT_ARTIFACT_SIGNATURE_VERSION,
    compute_bundle_hash,
    render_tool_yaml,
    sign_bundle_hash,
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


def _to_validation_response(record: ToolVersionRecord, artifact_signing_secret: str) -> ToolValidationResponse:
    validation = record.validation or ToolValidationResult(
        tool_name=record.tool_name,
        version=record.version,
        state=ToolValidationState.PENDING,
    )
    integrity_status = "not_applicable"
    integrity_message = ""
    has_artifact = bool(str((record.manifest.metadata or {}).get(ARTIFACT_HANDLER_PATH_METADATA_KEY, "")).strip())
    if has_artifact:
        has_signature = bool(str((record.manifest.metadata or {}).get(ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY, "")).strip())
        has_hash = bool(str((record.manifest.metadata or {}).get(ARTIFACT_BUNDLE_HASH_METADATA_KEY, "")).strip())
        if not has_signature or not has_hash:
            integrity_status = "missing_metadata"
            integrity_message = "artifact hash/signature metadata is missing"
        else:
            if not artifact_signing_secret.strip():
                integrity_status = "unverifiable"
                integrity_message = "artifact signing secret is not configured"
            else:
                try:
                    verify_artifact_bundle_integrity(record, artifact_signing_secret)
                    integrity_status = "verified"
                except ValueError as exc:
                    integrity_status = "mismatch"
                    integrity_message = str(exc)
    return ToolValidationResponse(
        tenant_id=record.tenant_id,
        tool_name=record.tool_name,
        version=record.version,
        state=validation.state.value,
        errors=validation.errors,
        warnings=validation.warnings,
        normalized_schema_hash=validation.normalized_schema_hash,
        package_ref=record.package_ref,
        integrity_status=integrity_status,
        integrity_message=integrity_message,
        active=record.active,
        created_at=record.created_at,
    )


def _validation_for_manifest(
    manifest: ToolPackageManifest,
    *,
    inline_handler_source: str = "",
) -> ToolValidationResult:
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
    inline_source = inline_handler_source.strip() or str(
        (manifest.metadata or {}).get(INLINE_HANDLER_SOURCE_METADATA_KEY, "")
    ).strip()
    if inline_source:
        try:
            validate_inline_handler_source(inline_source, manifest.entrypoint)
        except ValueError as exc:
            errors.append(str(exc))
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


def _artifact_signing_secret(request: Request) -> str:
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Application modules are not configured.")
    return str(modules.tool_management.artifact_signing_secret or "")


def _limits(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Application modules are not configured.")
    return modules.platform_bootstrap.settings.limits


def _tool_upload_rate_limiter(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Application modules are not configured.")
    return modules.tenant_governance.tool_upload_rate_limiter


def _tool_audit_pipeline(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Application modules are not configured.")
    return modules.audit_observability.tool_audit_pipeline


def _tool_artifact_store(request: Request):
    modules = get_app_modules(request)
    if modules is None:
        raise HTTPException(status_code=503, detail="Application modules are not configured.")
    return modules.tool_management.tool_artifact_store


async def _sync_active_tool_descriptor(
    *,
    tenant_id: str,
    tool_name: str,
    ctx: TenantRuntimeContext,
    tool_version_store: ToolVersionStore,
    artifact_signing_secret: str,
) -> None:
    active = await tool_version_store.get_active_tool_version(tenant_id, tool_name)
    if active is None:
        try:
            ctx.tool_registry.unregister(tool_name)
        except KeyError:
            pass
        return
    descriptor = descriptor_from_tool_version(active, artifact_signing_secret=artifact_signing_secret)
    ctx.tool_registry.register(descriptor)


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
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    tool_version_store: ToolVersionStore | None = Depends(get_tool_version_store),
) -> ToolValidationResponse:
    """Register a tenant tool package version and store validation state."""
    if tool_version_store is None:
        raise HTTPException(
            status_code=503,
            detail="Tool version store is not configured (memory backend).",
        )
    rate_limiter = _tool_upload_rate_limiter(request)
    if rate_limiter is not None:
        allowed, _ = rate_limiter.allow(tenant_id)
        if not allowed:
            pipeline = _tool_audit_pipeline(request)
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
    provided_handler_source = ""
    provided_tool_yaml = ""
    if body.package_bundle is not None:
        provided_handler_source = body.package_bundle.handler_py.strip()
        provided_tool_yaml = body.package_bundle.tool_yaml.strip()
    if not provided_handler_source:
        provided_handler_source = body.inline_handler_source.strip()
    if provided_handler_source:
        artifact_store = _tool_artifact_store(request)
        if artifact_store is None:
            raise HTTPException(status_code=503, detail="Tool artifact store is not configured.")
        rendered_tool_yaml = provided_tool_yaml or render_tool_yaml(manifest)
        persisted = artifact_store.persist_bundle(
            tenant_id=tenant_id,
            tool_name=manifest.tool_name,
            version=manifest.version,
            tool_yaml=rendered_tool_yaml,
            handler_py=provided_handler_source,
        )
        manifest.metadata = dict(manifest.metadata or {})
        manifest.metadata[ARTIFACT_BUNDLE_DIR_METADATA_KEY] = persisted.bundle_dir
        manifest.metadata[ARTIFACT_MANIFEST_PATH_METADATA_KEY] = persisted.manifest_path
        manifest.metadata[ARTIFACT_HANDLER_PATH_METADATA_KEY] = persisted.handler_path
        signing_secret = _artifact_signing_secret(request).strip()
        signature_version = DEFAULT_ARTIFACT_SIGNATURE_VERSION
        bundle_hash = compute_bundle_hash(rendered_tool_yaml, provided_handler_source)
        try:
            bundle_signature = sign_bundle_hash(bundle_hash, signing_secret, signature_version)
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        manifest.metadata[ARTIFACT_BUNDLE_HASH_METADATA_KEY] = bundle_hash
        manifest.metadata[ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY] = bundle_signature
        manifest.metadata[ARTIFACT_SIGNATURE_VERSION_METADATA_KEY] = signature_version
    computed_artifact_size_bytes = body.artifact_size_bytes
    if computed_artifact_size_bytes <= 0 and provided_handler_source:
        computed_artifact_size_bytes = len(provided_handler_source.encode("utf-8"))
    policy_decision = validate_tool_package_upload(
        manifest=manifest,
        package_ref=body.package_ref,
        artifact_size_bytes=computed_artifact_size_bytes,
        limits=_limits(request),
    )
    validation = _validation_for_manifest(
        manifest,
        inline_handler_source=provided_handler_source,
    )
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
    pipeline = _tool_audit_pipeline(request)
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
        if validation.state == ToolValidationState.INVALID:
            return _to_validation_response(record, _artifact_signing_secret(request))
        try:
            descriptor_from_tool_version(
                record,
                artifact_signing_secret=_artifact_signing_secret(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        await tool_version_store.set_active_tool_version(tenant_id, manifest.tool_name, manifest.version)
        await _sync_active_tool_descriptor(
            tenant_id=tenant_id,
            tool_name=manifest.tool_name,
            ctx=ctx,
            tool_version_store=tool_version_store,
            artifact_signing_secret=_artifact_signing_secret(request),
        )
        active_record = await tool_version_store.get_tool_version(tenant_id, manifest.tool_name, manifest.version)
        if active_record is not None:
            return _to_validation_response(active_record, _artifact_signing_secret(request))
    return _to_validation_response(record, _artifact_signing_secret(request))


@router.get("/{tenant_id}/tools/validate/{tool_name}", response_model=ToolValidationResponse)
async def validate_tool_version(
    tenant_id: str,
    request: Request,
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
    return _to_validation_response(record, _artifact_signing_secret(request))


@router.get("/{tenant_id}/tools/versions/{tool_name}", response_model=ToolVersionListResponse)
async def list_tool_versions(
    tenant_id: str,
    request: Request,
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
        versions=[_to_validation_response(v, _artifact_signing_secret(request)) for v in versions],
        total=len(versions),
    )


@router.get("/{tenant_id}/tools/version/{tool_name}", response_model=ToolVersionListResponse)
async def list_tool_version_alias(
    tenant_id: str,
    request: Request,
    tool_name: str,
    _identity: IdentityContext = Depends(require_valid_identity),
    tool_version_store: ToolVersionStore | None = Depends(get_tool_version_store),
) -> ToolVersionListResponse:
    """Backward-compatible alias for clients using singular /tools/version path."""
    return await list_tool_versions(
        tenant_id=tenant_id,
        request=request,
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
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
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
    await _sync_active_tool_descriptor(
        tenant_id=tenant_id,
        tool_name=tool_name,
        ctx=ctx,
        tool_version_store=tool_version_store,
        artifact_signing_secret=_artifact_signing_secret(request),
    )
    pipeline = _tool_audit_pipeline(request)
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
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
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
    if target.validation is not None and target.validation.state == ToolValidationState.INVALID:
        raise HTTPException(
            status_code=409,
            detail=f"Target rollback version '{body.target_version}' is invalid and cannot be activated.",
        )
    try:
        descriptor_from_tool_version(
            target,
            artifact_signing_secret=_artifact_signing_secret(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await tool_version_store.set_active_tool_version(tenant_id, tool_name, body.target_version)
    await _sync_active_tool_descriptor(
        tenant_id=tenant_id,
        tool_name=tool_name,
        ctx=ctx,
        tool_version_store=tool_version_store,
        artifact_signing_secret=_artifact_signing_secret(request),
    )
    pipeline = _tool_audit_pipeline(request)
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
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
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
    await _sync_active_tool_descriptor(
        tenant_id=tenant_id,
        tool_name=tool_name,
        ctx=ctx,
        tool_version_store=tool_version_store,
        artifact_signing_secret=_artifact_signing_secret(request),
    )
    pipeline = _tool_audit_pipeline(request)
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
