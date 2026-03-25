"""
File: openai_gateway_schemas.py
Path: src/api/schemas/openai_gateway_schemas.py
Role: Minimal OpenAI Chat Completions-shaped request/response models for the northbound gateway MVP.
Used By:
 - src/api/routers/openai_gateway.py
Depends On:
 - pydantic
Notes:
 - Subset of the OpenAI API; extended fields are ignored at the FastAPI layer unless added here.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OpenAIChatMessage(BaseModel):
    role: str
    content: str = ""


class OpenAIChatCompletionRequest(BaseModel):
    model: str = ""
    messages: list[OpenAIChatMessage] = Field(default_factory=list)
    stream: bool = False
    user: str | None = None


class OpenAIChatCompletionChoice(BaseModel):
    index: int = 0
    message: dict[str, str]
    finish_reason: str = "stop"


class OpenAIChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[OpenAIChatCompletionChoice] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)


class OpenAIErrorBody(BaseModel):
    message: str
    type: str = "invalid_request_error"
    param: str | None = None
    code: str | None = None


class OpenAIErrorResponse(BaseModel):
    error: OpenAIErrorBody
