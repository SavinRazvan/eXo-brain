"""
File: rate_limiter.py
Path: src/tenancy/rate_limiter.py
Role: Process-local per-tenant fixed-window rate limiting.
Used By:
 - src/api/bootstrap.py
 - src/api/routers/tools.py
 - src/api/routers/turns.py
Depends On:
 - threading
 - time
Notes:
 - This limiter is intentionally simple and deterministic for local/runtime control paths.
"""

from __future__ import annotations

import threading
import time


class TenantRateLimiter:
    def __init__(self, *, max_requests: int, window_seconds: int = 60) -> None:
        self._max_requests = max(int(max_requests), 0)
        self._window_seconds = max(int(window_seconds), 1)
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}

    def allow(self, tenant_id: str) -> tuple[bool, int]:
        if self._max_requests <= 0:
            return True, 0
        tenant_key = str(tenant_id or "default").strip() or "default"
        now = int(time.time())
        current_window = now // self._window_seconds
        with self._lock:
            window, count = self._windows.get(tenant_key, (current_window, 0))
            if window != current_window:
                window = current_window
                count = 0
            if count >= self._max_requests:
                return False, self._window_seconds
            self._windows[tenant_key] = (window, count + 1)
            return True, max(self._max_requests - (count + 1), 0)
