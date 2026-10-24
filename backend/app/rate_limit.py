"""Small in-process sliding-window limiter for the optional AI endpoint.

This is not a security boundary. It is a simple guard against a demo button being
held down and burning provider credits. Behind a reverse proxy, all callers may
share a key depending on how the server sees the connection.
"""

from __future__ import annotations

import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1.0, window_seconds)
        self._events: dict[str, deque[float]] = {}

    def allow(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        events = self._events.setdefault(key, deque())
        cutoff = current - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) >= self.limit:
            retry_after = max(1, int(events[0] + self.window_seconds - current) + 1)
            return False, retry_after

        events.append(current)
        if len(self._events) > 2_000:
            # Avoid unbounded growth from many one-off client keys.
            stale = [name for name, queue in self._events.items() if not queue]
            for name in stale:
                self._events.pop(name, None)
        return True, 0
