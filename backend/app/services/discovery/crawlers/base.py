"""Shared infrastructure for the crawlers: a circuit breaker and a token-bucket
rate limiter.

Every free source (Google Maps, directory sites, Overpass) can block or
rate-limit us. Rather than every crawler re-implementing its own backoff, they
all share these primitives so behaviour stays consistent and testable.
"""
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Fail-fast cooldown after a provider signals a block/rate-limit.

    Once tripped, every `call` fails fast for `cooldown_seconds` instead of a
    whole batch hammering an already-blocked source (a single block usually
    means every near-simultaneous call is blocked too, so retrying is waste).
    """

    def __init__(self, name: str, failure_threshold: int = 2, cooldown_seconds: float = 300.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._blocked_until = 0.0

    @property
    def open(self) -> bool:
        return time.monotonic() < self._blocked_until

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._blocked_until = time.monotonic() + self.cooldown_seconds
            logger.warning(
                "%s failed %d times in a row, circuit-breaking for %.0fs",
                self.name, self._consecutive_failures, self.cooldown_seconds,
            )

    def record_success(self) -> None:
        self._consecutive_failures = 0


class RateLimiter:
    """Simple token-bucket limiter so crawlers stay good citizens of free
    endpoints. `interval` is the minimum seconds between two `wait()` calls."""

    def __init__(self, name: str, interval: float = 1.0):
        self.name = name
        self.interval = interval
        self._next_ready = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._next_ready - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_ready = max(now, self._next_ready) + self.interval
