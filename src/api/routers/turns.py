"""
File: turns.py
Path: src/api/routers/turns.py
Role: Turn execution endpoints — SSE streaming and WebSocket for agent conversations.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/schemas/turn_schemas.py
 - src/runtime/tenant_runtime.py
 - src/integration/host_adapter.py
 - src/schemas/events.py
 - sse_starlette
Notes:
 - Both SSE and WebSocket emit the same JSON event envelope (defined in turn_schemas.py).
 - SSE: stateless, one turn per HTTP request. Best for scripts, notebooks, curl clients.
 - WebSocket: persistent, multi-turn, supports mid-session cancellation via asyncio.Task.
 - RuntimeEvent types are mapped to the shared EventEnvelope format.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse

from src.api.dependencies import get_tenant_context, require_valid_identity
from src.api.schemas.turn_schemas import TurnSubmitRequest
from src.core.session_context import SessionContext
from src.identity.contracts import IdentityContext
from src.runtime.tenant_runtime import TenantRuntimeContext
from src.schemas.events import RuntimeEvent, RuntimeEventType

router = APIRouter(tags=["turns"])


def _get_factory(request: Request):
    return request.app.state.tenant_factory


def _runtime_event_to_dict(event: RuntimeEvent) -> dict[str, Any]:
    """Map a RuntimeEvent to the shared JSON event envelope."""
    if event.event_type == RuntimeEventType.OUTPUT_DELTA:
        return {
            "event": "output_delta",
            "delta": event.payload.get("text", ""),
            "correlation_id": event.correlation_id,
        }
    elif event.event_type == RuntimeEventType.TOOL_INTENT:
        call = event.tool_call
        return {
            "event": "tool_call",
            "tool_name": call.tool_name if call else "",
            "arguments": dict(call.arguments) if call else {},
            "correlation_id": event.correlation_id,
        }
    elif event.event_type == RuntimeEventType.RUN_COMPLETE:
        return {
            "event": "run_complete",
            "run_id": event.run_id,
            "output": event.payload,
            "correlation_id": event.correlation_id,
        }
    elif event.event_type == RuntimeEventType.ERROR:
        return {
            "event": "error",
            "code": event.payload.get("code", "UNKNOWN_ERROR"),
            "message": event.payload.get("message", ""),
            "correlation_id": event.correlation_id,
        }
    # Fallback — emit as raw payload
    return {
        "event": event.event_type.value,
        "payload": event.payload,
        "correlation_id": event.correlation_id,
    }


async def _stream_turn(
    tenant_id: str,
    session_id: str,
    user_input: str,
    correlation_id: str,
    factory,
    ctx: TenantRuntimeContext,
    identity: IdentityContext,
) -> AsyncIterator[dict[str, Any]]:
    """Shared generator that yields event dicts from a single agent turn."""
    try:
        host_adapter = factory.get_session_runtime(session_id)
    except KeyError:
        yield {"event": "error", "code": "SESSION_NOT_FOUND",
               "message": f"Session '{session_id}' not found", "correlation_id": correlation_id}
        return

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    session_ctx = SessionContext(
        session_id=session_id,
        run_id=run_id,
        job_id=f"job_{uuid.uuid4().hex[:8]}",
        task_id=f"task_{uuid.uuid4().hex[:8]}",
        agent_id=session_id,
        provider_id="api",
        correlation_id=correlation_id or run_id,
        identity=identity,
    )

    try:
        async for event in host_adapter.submit_turn(session_ctx, user_input):
            yield _runtime_event_to_dict(event)
    except Exception as exc:
        yield {
            "event": "error",
            "code": "TURN_EXECUTION_ERROR",
            "message": str(exc),
            "correlation_id": correlation_id,
        }


# ---------------------------------------------------------------------------
# SSE turn endpoint
# ---------------------------------------------------------------------------


@router.post("/{tenant_id}/sessions/{session_id}/turns")
async def submit_turn_sse(
    tenant_id: str,
    session_id: str,
    body: TurnSubmitRequest,
    request: Request,
    ctx: TenantRuntimeContext = Depends(get_tenant_context),
    identity: IdentityContext = Depends(require_valid_identity),
) -> EventSourceResponse:
    """Submit a single agent turn and stream runtime events as SSE.

    Returns 404 if the session is not found.
    Events: output_delta, tool_call, run_complete, error.
    """
    factory = _get_factory(request)

    # Verify session exists before opening SSE stream
    try:
        factory.get_session_runtime(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    correlation_id = body.correlation_id or f"corr_{uuid.uuid4().hex[:8]}"

    async def event_generator():
        async for event_dict in _stream_turn(
            tenant_id=tenant_id,
            session_id=session_id,
            user_input=body.input,
            correlation_id=correlation_id,
            factory=factory,
            ctx=ctx,
            identity=identity,
        ):
            yield {"data": json.dumps(event_dict)}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# WebSocket turn endpoint
# ---------------------------------------------------------------------------


@router.websocket("/{tenant_id}/sessions/{session_id}/ws")
async def websocket_turn(
    tenant_id: str,
    session_id: str,
    websocket: WebSocket,
) -> None:
    """Persistent WebSocket connection for multi-turn agent conversations.

    Client message protocol:
      {"type": "turn", "input": "...", "run_id": "<optional>"}
      {"type": "cancel", "run_id": "..."}

    Server event protocol (same envelope as SSE):
      {"event": "output_delta", "delta": "...", "correlation_id": "..."}
      {"event": "tool_call", "tool_name": "...", "arguments": {...}, ...}
      {"event": "run_complete", "run_id": "...", "output": {...}, ...}
      {"event": "error", "code": "...", "message": "...", ...}
      {"event": "run_cancelled", "run_id": "..."}

    Cancellation: send {"type": "cancel", "run_id": "..."} to cancel a running turn.
    On disconnect: any in-flight turn task is automatically cancelled.
    """
    factory = websocket.app.state.tenant_factory
    ctx = factory.get_or_create(tenant_id)

    # Verify session exists before accepting WebSocket
    try:
        factory.get_session_runtime(session_id)
    except KeyError:
        await websocket.close(code=4404, reason=f"Session '{session_id}' not found")
        return

    await websocket.accept()

    # Map run_id → asyncio.Task for cancellation support
    active_tasks: dict[str, asyncio.Task] = {}
    # Minimal identity — WebSocket upgrades skip the X-Identity dependency for simplicity
    identity = IdentityContext(subject="ws-client", tenant_id=tenant_id)

    async def run_turn_task(run_id: str, user_input: str, correlation_id: str) -> None:
        async for event_dict in _stream_turn(
            tenant_id=tenant_id,
            session_id=session_id,
            user_input=user_input,
            correlation_id=correlation_id,
            factory=factory,
            ctx=ctx,
            identity=identity,
        ):
            try:
                await websocket.send_json(event_dict)
            except Exception:
                return
        active_tasks.pop(run_id, None)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"event": "error", "code": "INVALID_JSON", "message": "Message is not valid JSON"}
                )
                continue

            msg_type = msg.get("type", "")

            if msg_type == "turn":
                user_input = str(msg.get("input", "")).strip()
                if not user_input:
                    await websocket.send_json(
                        {"event": "error", "code": "EMPTY_INPUT", "message": "Turn input is empty"}
                    )
                    continue
                run_id = str(msg.get("run_id", "") or f"run_{uuid.uuid4().hex[:8]}")
                correlation_id = run_id
                task = asyncio.create_task(run_turn_task(run_id, user_input, correlation_id))
                active_tasks[run_id] = task

            elif msg_type == "cancel":
                run_id = str(msg.get("run_id", ""))
                task = active_tasks.pop(run_id, None)
                if task and not task.done():
                    task.cancel()
                await websocket.send_json({"event": "run_cancelled", "run_id": run_id})

            else:
                await websocket.send_json(
                    {"event": "error", "code": "UNKNOWN_MESSAGE_TYPE",
                     "message": f"Unknown message type: '{msg_type}'"}
                )

    except WebSocketDisconnect:
        pass
    finally:
        # Cancel any in-flight tasks on disconnect
        for task in active_tasks.values():
            if not task.done():
                task.cancel()
