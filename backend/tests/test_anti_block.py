"""Tests for the Sprint 2 anti-block infrastructure.

Covers the shared primitives in crawlers/base.py (proxy rotation, TLS-impersonating
fetch with block detection, robots.txt) and the Maps captcha-signature detection.
"""
import asyncio
import time

import pytest

from app.services.crawlers.base import (
    FetchOutcome,
    ProxyRotator,
    RobotsTxt,
    fetch_text,
)
from app.services.crawlers import maps_crawler


# ---------------------------------------------------------------------------
# ProxyRotator
# ---------------------------------------------------------------------------

def test_proxy_rotator_empty_pool_is_noop():
    rotator = ProxyRotator()
    assert rotator.size == 0
    assert rotator.available == 0
    assert asyncio.run(rotator.get()) is None


def test_proxy_rotator_round_robin():
    rotator = ProxyRotator(["p1", "p2", "p3"])
    assert rotator.size == 3
    first = asyncio.run(rotator.get())
    second = asyncio.run(rotator.get())
    third = asyncio.run(rotator.get())
    assert {first, second, third} == {"p1", "p2", "p3"}


def test_proxy_rotator_sticky_session():
    rotator = ProxyRotator(["p1", "p2"])
    a = asyncio.run(rotator.get("sess-1"))
    b = asyncio.run(rotator.get("sess-1"))
    c = asyncio.run(rotator.get("sess-2"))
    assert a == b
    assert c != a


def test_proxy_rotator_failure_suspends_then_recovers():
    rotator = ProxyRotator(["p1", "p2"], cooldown_seconds=0.05)
    first = asyncio.run(rotator.get())
    rotator.mark_failure(first)
    # All other proxies get used while the failed one cools down.
    others = set()
    for _ in range(5):
        others.add(asyncio.run(rotator.get()))
    assert first not in others
    # After cooldown it comes back.
    time.sleep(0.08)
    assert first == asyncio.run(rotator.get()) or first in {
        asyncio.run(rotator.get()) for _ in range(4)
    }


def test_proxy_rotator_all_suspended_returns_none():
    rotator = ProxyRotator(["p1"], cooldown_seconds=60)
    rotator.mark_failure("p1")
    assert asyncio.run(rotator.get()) is None


# ---------------------------------------------------------------------------
# fetch_text block detection
# ---------------------------------------------------------------------------

def test_fetch_text_never_raises_on_bad_url():
    outcome = asyncio.run(fetch_text("http://127.0.0.1:1/nope", timeout=1.0))
    assert isinstance(outcome, FetchOutcome)
    assert not outcome.ok


# ---------------------------------------------------------------------------
# RobotsTxt
# ---------------------------------------------------------------------------

def test_robots_parse_disallow():
    r = RobotsTxt()
    rules = r._parse("User-agent: *\nDisallow: /api/\nDisallow: /private\n")
    assert rules == ["/api/", "/private"]


def test_robots_match_prefix_and_wildcard():
    assert RobotsTxt._match("/api/", "/api/leads")
    assert RobotsTxt._match("/admin*", "/admin/users")
    assert not RobotsTxt._match("/admin*", "/user/admin")


def test_robots_fetch_failure_allows():
    r = RobotsTxt()
    assert asyncio.run(r._load(None, "nonexistent.invalid")) == []


# ---------------------------------------------------------------------------
# Maps captcha/block signature detection
# ---------------------------------------------------------------------------

def test_looks_blocked_positive():
    assert maps_crawler._looks_blocked(
        "https://www.google.com/maps/search/x",
        "<html>unusual traffic from your computer network</html>",
    )
    assert maps_crawler._looks_blocked(
        "https://www.google.com/sorry/index?continue=...",
        "",
    )


def test_looks_blocked_negative():
    assert not maps_crawler._looks_blocked(
        "https://www.google.com/maps/search/dental",
        "<div role='feed'>result one</div>",
    )


def test_user_agent_pool_is_valid():
    for ua in maps_crawler.USER_AGENTS:
        assert ua.startswith("Mozilla/5.0")
        assert "Chrome/" in ua


def test_timezone_matches_locale():
    assert maps_crawler._pick_timezone("en-PK") == "Asia/Karachi"
    assert maps_crawler._pick_timezone("en-US") == "America/New_York"
    assert maps_crawler._pick_timezone("fr-FR") == "Asia/Karachi"