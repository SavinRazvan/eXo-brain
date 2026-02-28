"""
File: event_router.py
Path: src/core/event_router.py
Role: Event map router for runtime events emitted by orchestrator/adapters.
Used By:
 - src/core/background_runtime.py
 - src/integration/host_adapter.py
Depends On:
 - src/schemas/events.py
 - src/core/session_context.py
Notes:
 - Event handlers are extension points; avoid embedding orchestration policy here.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from src.core.session_context import SessionContext
from src.schemas.events import RuntimeEvent, RuntimeEventType

EventHandler = Callable[[RuntimeEvent, SessionContext], Any | Awaitable[Any]]


@dataclass(slots=True)
class RoutedEvent:
    event: RuntimeEvent
    session: SessionContext
    handler_result: Any | None = None


class EventRouter:
    def __init__(self) -> None:
        self._handlers: dict[RuntimeEventType, list[EventHandler]] = {}

    def register(self, event_type: RuntimeEventType, handler: EventHandler) -> None:
        handlers = self._handlers.setdefault(event_type, [])
        handlers.append(handler)

    async def route(self, event: RuntimeEvent, session: SessionContext) -> list[RoutedEvent]:
        routed: list[RoutedEvent] = []
        for handler in self._handlers.get(event.event_type, []):
            value = handler(event, session)
            if inspect.isawaitable(value):
                value = await value
            routed.append(RoutedEvent(event=event, session=session, handler_result=value))
        return routed
