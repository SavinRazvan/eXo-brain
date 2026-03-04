"""
File: turn_schemas.py
Path: src/api/schemas/turn_schemas.py
Role: Pydantic request schemas and shared event envelope for SSE + WebSocket turn endpoints.
Used By:
 - src/api/routers/turns.py
Depends On:
 - pydantic
Notes:
 - EventEnvelope is the canonical JSON shape emitted by both SSE and WebSocket transports.
   Client parsers only need to handle one format regardless of transport.
 - SSE format: "data: <json>\n\n"
 - WebSocket format: raw JSON string per message.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TurnSubmitRequest(BaseModel):
    input: str = Field(..., description="User message to submit to the agent")
    correlation_id: str = Field(default="", description="Optional caller-supplied correlation ID")


# ---------------------------------------------------------------------------
# Shared event envelope — emitted by both SSE and WebSocket
# ---------------------------------------------------------------------------


class OutputDeltaEvent(BaseModel):
    event: Literal["output_delta"] = "output_delta"
    delta: str
    correlation_id: str = ""


class ToolCallEvent(BaseModel):
    event: Literal["tool_call"] = "tool_call"
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = ""


class ToolResultEvent(BaseModel):
    event: Literal["tool_result"] = "tool_result"
    tool_name: str
    result: Any = None
    policy: str = ""
    mode: str = ""
    correlation_id: str = ""


class ToolProgressEvent(BaseModel):
    event: Literal["tool_progress"] = "tool_progress"
    call_id: str = ""
    tool_name: str = ""
    state: str = ""
    tool_status: str = ""
    error_code: str = ""
    job_id: str = ""
    lease_token: str = ""
    lease_expires_at_epoch: str = ""
    claim_attempt: str = ""
    correlation_id: str = ""


class RunCompleteEvent(BaseModel):
    event: Literal["run_complete"] = "run_complete"
    run_id: str = ""
    output: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = ""


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    code: str
    message: str
    correlation_id: str = ""


class RunCancelledEvent(BaseModel):
    event: Literal["run_cancelled"] = "run_cancelled"
    run_id: str = ""
    correlation_id: str = ""


# ---------------------------------------------------------------------------
# WebSocket message protocol
# ---------------------------------------------------------------------------


class WSTurnMessage(BaseModel):
    type: Literal["turn"] = "turn"
    input: str
    run_id: str = Field(default="", description="Optional; server generates one if absent")


class WSCancelMessage(BaseModel):
    type: Literal["cancel"] = "cancel"
    run_id: str
