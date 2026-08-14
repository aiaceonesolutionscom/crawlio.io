import pytest

from app.services.enrichment import enrichment_pipeline


@pytest.mark.asyncio
async def test_enrich_scrapes_website_and_validates_email(monkeypatch):
    async def fake_scrape(website, use_browser, country_code):
        return {
            "email": "info@sakura.pk",
            "email_candidates": ["info@sakura.pk"],
            "social_links": {"instagram": "https://instagram.com/sakura"},
            "hours": "Mon-Sat 9am-7pm",
            "page_text": "x",
        }

    async def fake_geocode(address, city, country):
        return {"lat": 24.86, "lon": 67.0}

    monkeypatch.setattr(enrichment_pipeline, "_scrape_website", fake_scrape)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", fake_geocode)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Sakura Dental Studio", "website": "https://sakura.pk"},
        city="Karachi", country="Pakistan", country_code="PK",
    )

    assert result["email"] == "info@sakura.pk"
    assert result["social_links"] == {"instagram": "https://instagram.com/sakura"}
    assert result["hours"] == "Mon-Sat 9am-7pm"
    assert result["lat"] == 24.86
    assert result["lon"] == 67.0
    assert result["enrichment_status"] == "done"
    assert result["completeness"] >= 55


@pytest.mark.asyncio
async def test_enrich_without_website_does_not_fail(monkeypatch):
    async def fake_geocode(address, city, country):
        return None

    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", fake_geocode)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Sakura Dental Studio", "phone": "0300 1234567"},
        city="Karachi", country="Pakistan", country_code="PK",
    )

    assert result["enrichment_status"] == "done"
    assert result["phone"] == "0300 1234567"


@pytest.mark.asyncio
async def test_enrich_missing_name_marks_failed():
    result = await enrichment_pipeline.enrich_item(
        {"website": "https://x.pk"},
        city="Karachi", country="Pakistan",
    )
    assert result["enrichment_status"] == "failed"
    assert result["enrichment_error"] == "missing name"


@pytest.mark.asyncio
async def test_enrich_drops_invalid_email(monkeypatch):
    async def fake_scrape(website, use_browser, country_code):
        return {"email": "noreply@example.com", "email_candidates": ["noreply@example.com"]}

    async def fake_geocode(address, city, country):
        return None

    monkeypatch.setattr(enrichment_pipeline, "_scrape_website", fake_scrape)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", fake_geocode)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: None)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Sakura", "website": "https://sakura.pk"},
        city="Karachi", country="Pakistan",
    )
    assert result.get("email") is None
