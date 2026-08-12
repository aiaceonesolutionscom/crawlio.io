from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.services import discovery_cache_service
from app.db.models.discovery_cache import DiscoveryCache


async def test_miss_when_nothing_cached(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        result = await discovery_cache_service.get_cached(session, "Dental Clinic", "Karachi", "PK")
        assert result is None


async def test_upsert_then_get_round_trip(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    items = [{"name": "Acme Dental", "phone": "+923001234567", "source": "google_maps"}]

    async with session_maker() as session:
        await discovery_cache_service.upsert_cache(
            session, "Dental Clinic", "Karachi", "pk",
            niche_display="Dental Clinic", city_display="Karachi", country_display="Pakistan",
            items=items,
        )

    async with session_maker() as session:
        result = await discovery_cache_service.get_cached(session, "Dental Clinic", "Karachi", "PK")

    assert result is not None
    cached_items, cached_at = result
    assert cached_items == items
    assert cached_at is not None


async def test_get_is_case_and_whitespace_insensitive(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        await discovery_cache_service.upsert_cache(
            session, "Dental Clinic", " Karachi ", "pk",
            niche_display="Dental Clinic", city_display="Karachi", country_display="Pakistan",
            items=[{"name": "X"}],
        )

    async with session_maker() as session:
        result = await discovery_cache_service.get_cached(session, "dental clinic", "karachi", "PK")

    assert result is not None


async def test_synonym_niches_share_one_cache_entry(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        await discovery_cache_service.upsert_cache(
            session, "Dental Clinic", "Karachi", "PK",
            niche_display="Dental Clinic", city_display="Karachi", country_display="Pakistan",
            items=[{"name": "Acme Dental"}],
        )

    async with session_maker() as session:
        result = await discovery_cache_service.get_cached(session, "Dentist", "Karachi", "PK")

    assert result is not None
    cached_items, _ = result
    assert cached_items == [{"name": "Acme Dental"}]


async def test_expired_entry_is_a_miss(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        row = DiscoveryCache(
            niche_key="dental", city_key="karachi", country_code="PK",
            niche="Dental Clinic", city="Karachi", country="Pakistan",
            items=[{"name": "Stale"}], item_count=1,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        session.add(row)
        await session.commit()

    async with session_maker() as session:
        result = await discovery_cache_service.get_cached(session, "Dental Clinic", "Karachi", "PK")

    assert result is None


async def test_upsert_overwrites_existing_row_not_duplicates(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        await discovery_cache_service.upsert_cache(
            session, "Dental Clinic", "Karachi", "PK",
            niche_display="Dental Clinic", city_display="Karachi", country_display="Pakistan",
            items=[{"name": "First"}],
        )
    async with session_maker() as session:
        await discovery_cache_service.upsert_cache(
            session, "Dental Clinic", "Karachi", "PK",
            niche_display="Dental Clinic", city_display="Karachi", country_display="Pakistan",
            items=[{"name": "Second"}, {"name": "Third"}],
        )

    async with session_maker() as session:
        result = await discovery_cache_service.get_cached(session, "Dental Clinic", "Karachi", "PK")

    assert result is not None
    cached_items, _ = result
    assert len(cached_items) == 2
    assert cached_items[0]["name"] == "Second"
