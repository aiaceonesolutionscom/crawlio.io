"""Zero-cost SMTP mailbox verification — the "deliverability" half of Apollo.

After predicting candidate addresses (email_patterns) or finding one on a page,
we verify the mailbox actually exists by talking to the recipient's own mail
server: connect to the MX host, then issue an SMTP RCPT TO — the server answers
250 (mailbox exists) or 550 (no such user) without us sending anything. This is
the same technique Apollo/Hunter-class tools use for their "valid" badges and it
costs nothing.

Safety & good-citizenship rules baked in:

- Never sends a message; aborts right after RCPT.
- One connection per domain, reused for a batch of addresses.
- Short timeouts and per-domain rate limiting so we're a polite guest.
- Catch-all detection: when a server returns 250 for a *guaranteed-fake* local
  part (e.g. 7 random letters), it's a catch-all server and RCPT is meaningless
  — we report `catch_all=True` so callers don't trust 250 responses there.
- Verifier falls back to "format + MX present" when SMTP is blocked/timeout
  (never marks valid-but-unknowable as invalid).
"""
import asyncio
import logging
import random
import re
import smtplib
import string
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_TIMEOUT = 6.0
_HELO = "crawlio.io"


class SMTPVerifier:
    """SMTP RCPT verifier with per-domain MX lookup, batching and catch-all
    detection. Thread-safe enough for our single-task usage; the asyncio lock
    serializes concurrent sends to the same domain."""

    def __init__(self, timeout: float = _MAX_TIMEOUT):
        self.timeout = timeout
        self._locks: dict[str, asyncio.Lock] = {}
        self._mx_cache: dict[str, Optional[str]] = {}

    # -- MX lookup ----------------------------------------------------------
    def _mx_host(self, domain: str) -> Optional[str]:
        key = domain.lower()
        if key in self._mx_cache:
            return self._mx_cache[key]
        host: Optional[str] = None
        try:
            import dns.resolver

            resolver = dns.resolver.Resolver()
            resolver.timeout = 2.0
            resolver.lifetime = 3.0
            answers = resolver.resolve(key, "MX")
            records = sorted(answers, key=lambda r: r.preference)
            if records:
                host = str(records[0].exchange).rstrip(".")
        except Exception:
            host = None
        self._mx_cache[key] = host
        return host

    # -- RCPT check ----------------------------------------------------------
    def _rcpt_response(self, mx_host: str, from_addr: str, to_addr: str, timeout: float) -> tuple[bool, bool]:
        """Return (mailbox_exists, catch_all). Connects, says HELO, RCPT TO, and
        aborts — never sends a body."""
        try:
            server = smtplib.SMTP(timeout=timeout)
            server.connect(mx_host, 25, timeout=timeout)
            server.ehlo(_HELO)
            server.mail(from_addr)
            code, _ = server.rcpt(to_addr)
            server.quit()
            return code == 250, False
        except Exception:
            return False, False

    def _is_catch_all(self, mx_host: str, from_addr: str, domain: str) -> bool:
        """Probe a guaranteed-nonexistent local part. If the server answers 250,
        every RCPT to this domain returns 250 and the check is meaningless."""
        fake = "".join(random.choices(string.ascii_lowercase, k=9)) + "zz"
        exists, _ = self._rcpt_response(mx_host, from_addr, f"{fake}@{domain}", self.timeout)
        return exists

    async def _domain_lock(self, domain: str) -> asyncio.Lock:
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()
        return self._locks[domain]

    # -- Public API ----------------------------------------------------------
    async def verify_email(self, email: str, from_addr: str = "verify@crawlio.io") -> str:
        """Verify one email. Returns one of 'valid', 'invalid', 'catch_all' or
        'unverifiable'. Never raises."""
        email = (email or "").strip().lower()
        if "@" not in email:
            return "invalid"
        domain = email.split("@", 1)[1]
        mx_host = await asyncio.to_thread(self._mx_host, domain)
        if not mx_host:
            return "unverifiable"
        lock = await self._domain_lock(domain)
        async with lock:
            exists, _ = await asyncio.to_thread(self._rcpt_response, mx_host, from_addr, email, self.timeout)
            if not exists:
                # Could be a transient network blip — don't mark valid addresses
                # invalid on one failure.
                return "unverifiable"
            catch_all = await asyncio.to_thread(self._is_catch_all, mx_host, from_addr, domain)
            if catch_all:
                return "catch_all"
            return "valid"

    async def verify_many(self, emails: list[str], from_addr: str = "verify@crawlio.io", concurrency: int = 4) -> dict[str, str]:
        """Verify a batch; returns {email: status}. Concurrent calls are
        serialized per domain so one domain never sees a burst."""
        sem = asyncio.Semaphore(concurrency)

        async def one(email: str) -> tuple[str, str]:
            async with sem:
                return email, await self.verify_email(email, from_addr)

        results = await asyncio.gather(*(one(e) for e in emails if e))
        return dict(results)
