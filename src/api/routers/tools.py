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
Notes:
 - handler_ref is resolved via importlib at registration time; unresolvable refs return 422.
 - Tools are stored in the tenant-scoped ToolRegistry — one per tenant, fully isolated.
"""

from __future__ import annotations

import importlib
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_tenant_context, require_valid_identity
from src.api.schemas.tool_schemas import ToolListResponse, ToolRegisterRequest, ToolResponse
from src.identity.contracts import IdentityContext
from src.runtime.tenant_runtime import TenantRuntimeContext
from src.tools.registry import ToolDescriptor

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


@router.post("/{tenant_id}/tools", status_code=201, response_model=ToolResponse)
async def register_tool(
    tenant_id: str,
    body: ToolRegisterRequest,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    _identity: IdentityContext = Depends(require_valid_identity),
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
    return _descriptor_to_response(descriptor)


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
) -> None:
    """Unregister a tool from the tenant's registry."""
    try:
        ctx.tool_registry.unregister(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
