"""Async token-bucket rate limiter.

Caps the *rate* of outbound connections (politeness, IDS-friendliness, not
melting the target), independently of the *concurrency* cap. Concurrency is
handled by a semaphore in the scanner; this paces packets-per-second.
"""
from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Token bucket. ``acquire()`` blocks until a token is available.

    Refills continuously at ``rate_per_sec`` tokens/second up to ``burst``.
    A non-positive rate disables limiting (acquire is a no-op).
    """

    def __init__(self, rate_per_sec: float, *, burst: float | None = None) -> None:
        self._rate = float(rate_per_sec)
        self._capacity = float(burst if burst is not None else rate_per_sec)
        self._tokens = self._capacity
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        if self._rate <= 0:
            return
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # Sleep just long enough to accrue the deficit, holding the
                # lock so pacing is strict and ordered.
                deficit = tokens - self._tokens
                await asyncio.sleep(deficit / self._rate)
