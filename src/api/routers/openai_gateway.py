"""
File: openai_gateway.py
Path: src/api/routers/openai_gateway.py
Role: Feature-flagged northbound OpenAI-compatible chat completions endpoint mapping into governed turn execution.
Used By:
 - src/api/app.py
Depends On:
 - src/api/dependencies.py
 - src/api/routers/turns.py (iter_governed_turn_dicts_for_transport)
 - src/api/schemas/openai_gateway_schemas.py
Notes:
 - Gated by EXO_ENABLE_OPENAI_COMPAT_GATEWAY; does not proxy raw upstream OpenAI — uses internal orchestration.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.api.dependencies import get_openai_gateway_runtime_context, require_valid_identity
from src.api.routers.turns import iter_governed_turn_dicts_for_transport
from src.api.schemas.openai_gateway_schemas import (
    OpenAIChatCompletionChoice,
    OpenAIChatCompletionRequest,
    OpenAIChatCompletionResponse,
    OpenAIErrorResponse,
)
from src.identity.contracts import IdentityContext
from src.runtime.tenant_runtime import TenantRuntimeContext

router = APIRouter(tags=["openai-gateway"])

SESSION_HEADER = "X-eXo-Session-Id"


def _last_user_text(messages: list[Any]) -> str:
    for msg in reversed(messages):
        role = str(getattr(msg, "role", "") or "").strip().lower()
        if role == "user":
            return str(getattr(msg, "content", "") or "")
    return ""


@router.post(
    "/chat/completions",
    response_model=None,
    responses={
        200: {"model": OpenAIChatCompletionResponse},
        400: {"model": OpenAIErrorResponse},
        401: {"model": OpenAIErrorResponse},
        403: {"model": OpenAIErrorResponse},
        404: {"model": OpenAIErrorResponse},
        502: {"model": OpenAIErrorResponse},
    },
)
async def openai_chat_completions(
    body: OpenAIChatCompletionRequest,
    request: Request,
    response: Response,
    ctx: TenantRuntimeContext = Depends(get_openai_gateway_runtime_context),
    identity: IdentityContext = Depends(require_valid_identity),
) -> OpenAIChatCompletionResponse | dict[str, Any]:
    """OpenAI-shaped non-streaming chat completion; tenant and session come from auth + header."""
    if body.stream:
        raise HTTPException(
            status_code=400,
            detail="stream=true is not supported for this gateway yet; use stream=false.",
        )
    session_id = str(request.headers.get(SESSION_HEADER, "") or "").strip()
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required header {SESSION_HEADER} (maps to an existing eXo-brain session).",
        )
    user_text = _last_user_text(body.messages)
    if not user_text.strip():
        raise HTTPException(status_code=400, detail="messages must include at least one user role with content.")

    tenant_id = str(identity.tenant_id or "").strip()
    correlation = str(body.user or "").strip() or f"oai_{uuid.uuid4().hex[:12]}"

    deltas: list[str] = []
    finish_reason = "stop"
    err_code = ""
    err_message = ""

    async for event_dict in iter_governed_turn_dicts_for_transport(
        tenant_id=tenant_id,
        session_id=session_id,
        user_input=user_text,
        body_correlation_id=correlation,
        request=request,
        identity=identity,
        ctx=ctx,
        transport="openai_compat",
    ):
        ev = event_dict.get("event")
        if ev == "output_delta":
            deltas.append(str(event_dict.get("delta", "")))
        elif ev == "error":
            finish_reason = "error"
            err_code = str(event_dict.get("code", "TURN_ERROR"))
            err_message = str(event_dict.get("message", ""))
        elif ev == "run_complete":
            break

    if finish_reason == "error":
        response.status_code = 502
        return {
            "error": {
                "message": err_message or err_code,
                "type": "api_error",
                "code": err_code,
            }
        }

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    model_name = body.model or "exo-brain"
    return OpenAIChatCompletionResponse(
        id=completion_id,
        created=int(time.time()),
        model=model_name,
        choices=[
            OpenAIChatCompletionChoice(
                index=0,
                message={"role": "assistant", "content": "".join(deltas)},
                finish_reason="stop",
            )
        ],
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
