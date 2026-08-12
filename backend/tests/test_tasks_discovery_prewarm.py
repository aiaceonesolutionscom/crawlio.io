from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models.discovery_cache import DiscoveryCache
from app.services import discovery_service
from app.workers import tasks_discovery_prewarm


async def _seed_row(session_maker, niche_key, city_key, country_code, item_count, expires_in_minutes):
    async with session_maker() as session:
        session.add(DiscoveryCache(
            niche_key=niche_key, city_key=city_key, country_code=country_code,
            niche=niche_key.title(), city=city_key.title(), country="Pakistan",
            items=[{"name": "placeholder"}] * item_count, item_count=item_count,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        ))
        await session.commit()


async def test_prewarm_refreshes_soonest_to_expire_batch(db_engine, monkeypatch):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(tasks_discovery_prewarm, "async_session_maker", session_maker)
    monkeypatch.setattr(tasks_discovery_prewarm.settings, "discovery_prewarm_batch_size", 2)

    await _seed_row(session_maker, "dental", "karachi", "PK", item_count=5, expires_in_minutes=5)
    await _seed_row(session_maker, "restaurant", "lahore", "PK", item_count=3, expires_in_minutes=10)
    await _seed_row(session_maker, "gym", "islamabad", "PK", item_count=2, expires_in_minutes=999)  # not soonest

    refreshed = []

    async def fake_discover(niche, city, country, country_code="PK", limit=50):
        refreshed.append((niche, city, limit))
        return [{"name": "Fresh", "phone": "+923001234567", "source": "google_maps"}]

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    await tasks_discovery_prewarm._prewarm_async()

    # Only the batch_size=2 soonest-to-expire rows were refreshed, not the third.
    assert len(refreshed) == 2
    refreshed_keys = {(niche, city) for niche, city, _ in refreshed}
    assert refreshed_keys == {("Dental", "Karachi"), ("Restaurant", "Lahore")}


async def test_prewarm_uses_item_count_as_refresh_target_with_floor(db_engine, monkeypatch):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(tasks_discovery_prewarm, "async_session_maker", session_maker)
    monkeypatch.setattr(tasks_discovery_prewarm.settings, "discovery_prewarm_batch_size", 1)

    await _seed_row(session_maker, "dental", "karachi", "PK", item_count=2, expires_in_minutes=5)

    captured_limit = {}

    async def fake_discover(niche, city, country, country_code="PK", limit=50):
        captured_limit["limit"] = limit
        return []

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    await tasks_discovery_prewarm._prewarm_async()

    assert captured_limit["limit"] == tasks_discovery_prewarm.MIN_REFRESH_LIMIT


async def test_prewarm_writes_fresh_results_back_to_cache(db_engine, monkeypatch):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(tasks_discovery_prewarm, "async_session_maker", session_maker)
    monkeypatch.setattr(tasks_discovery_prewarm.settings, "discovery_prewarm_batch_size", 1)

    await _seed_row(session_maker, "dental", "karachi", "PK", item_count=10, expires_in_minutes=5)

    async def fake_discover(niche, city, country, country_code="PK", limit=50):
        return [{"name": "Refreshed Clinic", "phone": "+923001234567", "source": "google_maps"}]

    monkeypatch.setattr(discovery_service, "discover_businesses", fake_discover)

    await tasks_discovery_prewarm._prewarm_async()

    from app.services import discovery_cache_service
    async with session_maker() as session:
        result = await discovery_cache_service.get_cached(session, "dental", "karachi", "PK")

    assert result is not None
    items, _ = result
    assert items == [{"name": "Refreshed Clinic", "phone": "+923001234567", "source": "google_maps"}]


async def test_prewarm_survives_one_row_failing(db_engine, monkeypatch):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(tasks_discovery_prewarm, "async_session_maker", session_maker)
    monkeypatch.setattr(tasks_discovery_prewarm.settings, "discovery_prewarm_batch_size", 2)

    await _seed_row(session_maker, "dental", "karachi", "PK", item_count=2, expires_in_minutes=5)
    await _seed_row(session_maker, "restaurant", "lahore", "PK", item_count=2, expires_in_minutes=6)

    async def flaky_discover(niche, city, country, country_code="PK", limit=50):
        if niche == "dental":
            raise RuntimeError("boom")
        return [{"name": "Still Works", "phone": "+923001234567", "source": "google_maps"}]

    monkeypatch.setattr(discovery_service, "discover_businesses", flaky_discover)

    await tasks_discovery_prewarm._prewarm_async()  # must not raise

    from app.services import discovery_cache_service
    async with session_maker() as session:
        result = await discovery_cache_service.get_cached(session, "restaurant", "lahore", "PK")
    assert result is not None


def test_task_is_a_noop_when_prewarm_disabled(monkeypatch):
    monkeypatch.setattr(tasks_discovery_prewarm.settings, "discovery_prewarm_enabled", False)
    called = False

    async def fake_prewarm_async():
        nonlocal called
        called = True

    monkeypatch.setattr(tasks_discovery_prewarm, "_prewarm_async", fake_prewarm_async)

    tasks_discovery_prewarm.prewarm_discovery_cache.run()

    assert called is False
