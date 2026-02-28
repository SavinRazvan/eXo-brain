"""
File: compensation_hooks.py
Path: src/resilience/compensation_hooks.py
Role: Compensation hook registry for post-failure side-effect handling.
Used By:
 - future tool and workflow recovery integrations
Depends On:
 - none
Notes:
 - Hooks are optional and run best-effort.
"""

from __future__ import annotations

from typing import Callable


class CompensationHooks:
    def __init__(self) -> None:
        self._hooks: dict[str, Callable[[dict], None]] = {}

    def register(self, reason_code: str, hook: Callable[[dict], None]) -> None:
        self._hooks[reason_code] = hook

    def run(self, reason_code: str, payload: dict) -> None:
        hook = self._hooks.get(reason_code)
        if hook is not None:
            hook(dict(payload))

