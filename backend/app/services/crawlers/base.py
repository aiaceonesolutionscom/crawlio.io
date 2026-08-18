"""Shared infrastructure for the crawlers: a circuit breaker, a token-bucket
rate limiter, a proxy rotator, and a per-source reliability tracker.

Every free source (Google Maps, directory sites, Overpass) can block or
rate-limit us. Rather than every crawler re-implementing its own backoff, they
all share these primitives so behaviour stays consistent and testable.
"""
import asyncio
import logging
import time
from typing import Optional
from urllib.parse import urlparse

try:
    from curl_cffi import requests as cffi_requests

    _HAS_CURL_CFFI = True
except ImportError:  # pragma: no cover - optional dependency
    cffi_requests = None
    _HAS_CURL_CFFI = False

import httpx

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


class ProxyRotator:
    """Round-robin proxy pool with failure-based rotation.

    Consumes a config list of proxy URLs (e.g. ``http://user:pass@host:port``
    or ``socks5://user:pass@host:port``). A proxy that fails a request is
    suspended and excluded from rotation for `cooldown_seconds`; callers
    `mark_success`/`mark_failure` after each attempt. Sticky sessions hand the
    same proxy back within one session so targets that fingerprint IP+session
    (Google Maps) don't see mid-crawl IP churn.

    With an empty pool this is a no-op: `get()` returns None (i.e. direct
    connection), so the whole crawl stack works without any proxy configured.
    """

    def __init__(
        self,
        proxies: Optional[list[str]] = None,
        name: str = "proxy-rotator",
        cooldown_seconds: float = 300.0,
    ):
        self.name = name
        self.cooldown_seconds = cooldown_seconds
        self._proxies: list[str] = [p for p in (proxies or []) if p]
        self._suspended_until: dict[str, float] = {}
        self._sticky: dict[str, str] = {}
        self._idx = 0

    @property
    def size(self) -> int:
        return len(self._proxies)

    @property
    def available(self) -> int:
        now = time.monotonic()
        return sum(1 for p in self._proxies if self._suspended_until.get(p, 0.0) <= now)

    async def get(self, sticky_key: Optional[str] = None) -> Optional[str]:
        """Return the next proxy for a request, honoring a sticky session key
        so the same proxy is reused within one session when possible. Returns
        None when the pool is empty or every proxy is suspended."""
        if not self._proxies:
            return None
        if sticky_key is not None and self._sticky.get(sticky_key):
            candidate = self._sticky[sticky_key]
            if self._suspended_until.get(candidate, 0.0) <= time.monotonic():
                return candidate
        now = time.monotonic()
        for _ in range(len(self._proxies)):
            candidate = self._proxies[self._idx % len(self._proxies)]
            self._idx += 1
            if self._suspended_until.get(candidate, 0.0) <= now:
                if sticky_key is not None:
                    self._sticky[sticky_key] = candidate
                return candidate
        return None

    def mark_success(self, proxy: Optional[str]) -> None:
        if proxy:
            self._suspended_until.pop(proxy, None)

    def mark_failure(self, proxy: Optional[str]) -> None:
        if not proxy:
            return
        self._suspended_until[proxy] = time.monotonic() + self.cooldown_seconds
        logger.warning("%s suspended proxy %s for %.0fs", self.name, proxy, self.cooldown_seconds)

    def clear(self) -> None:
        self._suspended_until.clear()


# Block/rate-limit statuses that HTTP crawlers must treat as "back off", distinct
# from a plain 404 (page genuinely missing).
class FetchOutcome:
    """Result of an HTTP fetch with enough context for the caller to decide
    whether to rotate proxies / trip circuit breakers / report zero results."""

    __slots__ = ("ok", "status", "text", "url", "blocked", "error")

    def __init__(self, ok: bool, status: int = 0, text: str = "", url: str = "", blocked: bool = False, error: str = ""):
        self.ok = ok
        self.status = status
        self.text = text
        self.url = url
        self.blocked = blocked
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"FetchOutcome(ok={self.ok}, status={self.status}, blocked={self.blocked})"


# Server responses that mean "slow down / we don't like you", regardless of the
# body content. Some anti-bot stacks return 200 with a challenge page, which
# callers catch via `body_markers`.
_BLOCK_STATUSES = {403, 429}
_CHALLENGE_MARKERS = (
    "captcha",
    "recaptcha",
    "not a robot",
    "unusual traffic",
    "access denied",
    "verify you are human",
)


async def fetch_text(
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    impersonate: str = "chrome",
    proxy: Optional[str] = None,
    timeout: float = 20.0,
    body_markers: tuple[str, ...] = _CHALLENGE_MARKERS,
    client: Optional[httpx.AsyncClient] = None,
) -> FetchOutcome:
    """Fetch a page's HTML using a TLS-impersonating client (curl_cffi when
    available, falling back to httpx). Never raises; reports blocks distinctly."""
    headers = dict(headers or {})
    headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    )
    if _HAS_CURL_CFFI:
        try:
            resp = cffi_requests.get(
                url,
                headers=headers,
                impersonate=impersonate,
                proxy=proxy,
                timeout=timeout,
            )
            if resp.status_code in _BLOCK_STATUSES:
                return FetchOutcome(False, resp.status_code, blocked=True)
            text = getattr(resp, "text", "") or ""
            if resp.status_code == 200 and text and any(m in text.lower() for m in body_markers):
                return FetchOutcome(False, 200, text=text, blocked=True)
            return FetchOutcome(resp.status_code < 400, resp.status_code, text=text, url=str(resp.url))
        except Exception as exc:  # curl_cffi can fail on odd proxies
            logger.debug("curl_cffi fetch failed for %s: %s", url, exc)
    # Fallback: plain httpx with follow_redirects.
    own = client is None
    if own:
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    try:
        resp = await client.get(url, headers=headers, proxy=proxy if client is not None else None)
    except Exception as exc:
        return FetchOutcome(False, error=str(exc))
    finally:
        if own:
            await client.aclose()
    if resp.status_code in _BLOCK_STATUSES:
        return FetchOutcome(False, resp.status_code, blocked=True)
    text = resp.text or ""
    if resp.status_code == 200 and any(m in text.lower() for m in body_markers):
        return FetchOutcome(False, 200, text=text, blocked=True)
    return FetchOutcome(resp.status_code < 400, resp.status_code, text=text, url=str(resp.url))


class RobotsTxt:
    """Tiny robots.txt checker with per-host caching so the plain-HTTP crawlers
    (directory, search pages) don't hammer robots.txt on every fetch. Treats
    any failure to fetch robots.txt as "allowed" so a flaky host never silently
    zeroes a whole crawl. Only `Disallow` rules are honored; wildcard prefixes
    are matched the same way real crawlers do (longest prefix wins)."""

    def __init__(self, user_agent: str = "CrawlioBot/1.0"):
        self.user_agent = user_agent
        self._cache: dict[str, Optional[list[str]]] = {}

    async def is_allowed(self, client: httpx.AsyncClient, url: str) -> bool:
        try:
            host = urlparse(url).netloc.lower()
        except ValueError:
            return True
        rules = self._cache.get(host)
        if rules is None:
            rules = await self._load(client, host)
            self._cache[host] = rules
        path = urlparse(url).path or "/"
        return not any(self._match(rule, path) for rule in rules)

    async def _load(self, client: httpx.AsyncClient, host: str) -> list[str]:
        robots_url = f"https://{host}/robots.txt"
        try:
            resp = await client.get(robots_url, timeout=10.0)
            if resp.status_code >= 400:
                return []
            return self._parse(resp.text or "")
        except Exception:
            return []

    def _parse(self, text: str) -> list[str]:
        rules: list[str] = []
        for line in (text or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition(":")
            if key.strip().lower() != "disallow":
                continue
            rules.append(value.strip())
        return rules

    @staticmethod
    def _match(rule: str, path: str) -> bool:
        if not rule or rule == "/":
            return False
        if "*" in rule:
            prefix, _, suffix = rule.partition("*")
            return path.startswith(prefix) and path.endswith(suffix)
        return path.startswith(rule)

    def clear(self) -> None:
        self._cache.clear()


class SourceTracker:
    """Rolling reliability stats per crawler source.

    Crawlers report `record_success(source)` / `record_failure(source)`; this
    keeps a bounded rolling window of outcomes (newest-first) so the health and
    dashboard endpoints can show which sources are healthy and which are getting
    blocked or erroring right now -- without unbounded memory growth.

    Thread-safety isn't needed: all crawler calls run inside one asyncio loop.
    """

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._outcomes: dict[str, list[bool]] = {}
        self._total: dict[str, int] = {}
        self._successes: dict[str, int] = {}
        self._first_seen: dict[str, float] = {}

    def record(self, source: str, ok: bool) -> None:
        source = source or "unknown"
        if source not in self._outcomes:
            self._outcomes[source] = []
            self._total[source] = 0
            self._successes[source] = 0
            self._first_seen[source] = time.monotonic()
        window = self._outcomes[source]
        window.append(ok)
        if len(window) > self.window_size:
            removed = window.pop(0)
            self._total[source] -= 1
            if removed:
                self._successes[source] -= 1
        self._total[source] += 1
        if ok:
            self._successes[source] += 1

    def record_success(self, source: str) -> None:
        self.record(source, True)

    def record_failure(self, source: str) -> None:
        self.record(source, False)

    def stats(self, source: str) -> dict:
        """Return {total, successes, failures, success_rate, last_ok} for a
        source, or a zeroed dict when the source hasn't been seen yet."""
        source = source or "unknown"
        total = self._total.get(source, 0)
        successes = self._successes.get(source, 0)
        window = self._outcomes.get(source, [])
        return {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": round(successes / total, 3) if total else 1.0,
            "last_ok": bool(window and window[-1]),
            "window_size": len(window),
        }

    def all_stats(self) -> dict[str, dict]:
        return {source: self.stats(source) for source in sorted(self._outcomes)}

    def unhealthy(self, min_rate: float = 0.3, min_samples: int = 5) -> list[str]:
        """Sources whose recent success rate is below `min_rate` over at least
        `min_samples` observed calls -- candidates for the degraded flag."""
        out: list[str] = []
        for source, window in self._outcomes.items():
            if len(window) < min_samples:
                continue
            rate = sum(window) / len(window)
            if rate < min_rate:
                out.append(source)
        return out


# Shared instance the crawlers and health endpoints use.
source_tracker = SourceTracker()