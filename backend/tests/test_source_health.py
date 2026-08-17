"""Tests for Sprint 5: source reliability tracker, deep /health checks, and
admin source-health dashboard endpoints."""

import pytest

from app.services.crawlers.base import SourceTracker, source_tracker
from app.main import app


class TestSourceTracker:
    def test_starts_clean(self):
        t = SourceTracker()
        assert t.stats("google_maps") == {
            "total": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": 1.0,
            "last_ok": False,
            "window_size": 0,
        }

    def test_success_rate(self):
        t = SourceTracker()
        for _ in range(3):
            t.record_success("bing")
        t.record_failure("bing")
        stats = t.stats("bing")
        assert stats["total"] == 4
        assert stats["successes"] == 3
        assert stats["failures"] == 1
        assert stats["success_rate"] == pytest.approx(0.75)
        assert stats["last_ok"] is False

    def test_unhealthy_sources(self):
        t = SourceTracker()
        for _ in range(10):
            t.record_failure("bad")
        for _ in range(10):
            t.record_success("good")
        assert t.unhealthy() == ["bad"]
        # Not enough samples yet
        t.record_failure("tiny")
        assert "tiny" not in t.unhealthy()
        for _ in range(5):
            t.record_failure("tiny")
        assert "tiny" in t.unhealthy()

    def test_window_rolling(self):
        t = SourceTracker(window_size=5)
        for _ in range(5):
            t.record_failure("dir")
        for _ in range(5):
            t.record_success("dir")
        stats = t.stats("dir")
        assert stats["total"] == 5
        assert stats["successes"] == 5
        assert stats["failures"] == 0

    def test_all_stats_sorted(self):
        t = SourceTracker()
        t.record_success("b")
        t.record_success("a")
        assert list(t.all_stats().keys()) == ["a", "b"]

    def test_shared_instance(self):
        source_tracker.record_success("test_source")
        assert source_tracker.stats("test_source")["total"] >= 1


class TestHealthDeepChecks:
    async def test_health_reports_db_and_sources(self):
        body = await _call_health()
        assert "database" in body
        assert body["database"] == "ok"
        assert "circuit_breakers" in body
        assert set(body["circuit_breakers"]) == {"google_maps", "bing_maps", "bizdata", "directory"}
        assert isinstance(body["circuit_breakers"]["google_maps"], bool)
        assert "sources" in body
        assert "unhealthy_sources" in body


class TestAdminSourceHealth:
    async def test_sources_endpoint(self, admin_client):
        r = await admin_client.get("/api/v1/admin/dashboard/sources")
        assert r.status_code == 200
        body = r.json()
        assert "sources" in body
        assert "unhealthy_sources" in body

    async def test_recover_endpoint(self, admin_client):
        from app.services.crawlers import maps_crawler, bing_maps_crawler

        # Trip a breaker so recovery has something to clear
        for _ in range(maps_crawler._breaker.failure_threshold):
            maps_crawler._breaker.record_failure()
        assert maps_crawler._breaker.open

        r = await admin_client.post("/api/v1/admin/dashboard/sources/recover")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "recovered"
        assert not maps_crawler._breaker.open
        assert not bing_maps_crawler._breaker.open

    async def test_sources_route_registered(self):
        schema = app.openapi()
        assert "/api/v1/admin/dashboard/sources" in schema["paths"]


async def _call_health():
    import httpx
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health")
        assert r.status_code == 200
        return r.json()
