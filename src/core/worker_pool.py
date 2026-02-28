"""
File: worker_pool.py
Path: src/core/worker_pool.py
Role: Bounded concurrency worker pool for task graph execution.
Used By:
 - src/core/scheduler.py
Depends On:
 - asyncio
Notes:
 - Concurrency bounds are a safety gate for background runtime saturation control.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class WorkerPool:
    def __init__(self, max_concurrency: int) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    async def run(self, fn: Callable[[], Awaitable[T]]) -> T:
        async with self._semaphore:
            return await fn()
