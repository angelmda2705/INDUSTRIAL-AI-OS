"""In-process sliding-window rate limiter.

Adequate for a single API process. A multi-instance deployment must replace
the backend with a shared store (e.g. Redis); the interface is kept small for
that purpose. See docs/KNOWN_LIMITATIONS.md.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, float]:
        """Register a hit. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False, max(0.0, window_seconds - (now - q[0]))
            q.append(now)
            if len(self._hits) > 50_000:  # bound memory under key-spraying
                for k in [k for k, v in self._hits.items() if not v][:10_000]:
                    del self._hits[k]
            return True, 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
