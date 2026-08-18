from app.services import enrichment_pipeline


async def test_batch_free_tier_uses_plain_fetch_and_batches_fallback(monkeypatch):
    plain_calls = []
    browser_batch_calls = []

    async def fake_fetch_plain(url, country_code=None):
        plain_calls.append(url)
        if url == "https://easy.pk":
            return {"email": "info@easy.pk", "email_candidates": [], "social_links": {}}
        return None  # needs browser fallback

    async def fake_extract_contact_details(urls, country_code=None):
        browser_batch_calls.append(list(urls))
        return [{"email": f"found-{i}@x.pk", "email_candidates": [], "social_links": {}} for i in range(len(urls))]

    monkeypatch.setattr(enrichment_pipeline.website_scraper_service, "fetch_plain", fake_fetch_plain)
    monkeypatch.setattr(enrichment_pipeline.browser_scraper_service, "extract_contact_details", fake_extract_contact_details)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", lambda *a, **k: None)

    items = [
        {"name": "Easy Co", "website": "https://easy.pk", "lat": 1, "lon": 1},
        {"name": "Hard Co", "website": "https://hard.pk", "lat": 1, "lon": 1},
        {"name": "No Site Co", "lat": 1, "lon": 1},
    ]

    results = await enrichment_pipeline.enrich_items_batch(
        items, city="Karachi", country="Pakistan", country_code="PK", use_browser=False,
    )

    # Exactly ONE shared browser call for the site(s) that needed the fallback,
    # not one launch per lead.
    assert browser_batch_calls == [["https://hard.pk"]]
    assert results[0]["email"] == "info@easy.pk"
    assert results[1]["email"] == "found-0@x.pk"
    assert results[2].get("email") is None


async def test_batch_enhanced_tier_shares_one_browser_call_for_all_sites(monkeypatch):
    browser_batch_calls = []

    async def fake_extract_contact_details(urls, country_code=None):
        browser_batch_calls.append(list(urls))
        return [{"email": f"e{i}@x.pk", "email_candidates": [], "social_links": {}} for i in range(len(urls))]

    monkeypatch.setattr(enrichment_pipeline.browser_scraper_service, "extract_contact_details", fake_extract_contact_details)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", lambda *a, **k: None)

    items = [
        {"name": "A", "website": "https://a.pk", "lat": 1, "lon": 1},
        {"name": "B", "website": "https://b.pk", "lat": 1, "lon": 1},
        {"name": "C", "website": "https://c.pk", "lat": 1, "lon": 1},
    ]

    results = await enrichment_pipeline.enrich_items_batch(
        items, city="Karachi", country="Pakistan", country_code="PK", use_browser=True,
    )

    assert len(browser_batch_calls) == 1
    assert browser_batch_calls[0] == ["https://a.pk", "https://b.pk", "https://c.pk"]
    assert [r["email"] for r in results] == ["e0@x.pk", "e1@x.pk", "e2@x.pk"]


async def test_batch_drops_items_with_no_name(monkeypatch):
    async def fake_extract_contact_details(urls, country_code=None):
        return [{} for _ in urls]

    monkeypatch.setattr(enrichment_pipeline.browser_scraper_service, "extract_contact_details", fake_extract_contact_details)

    items = [{"website": "https://noname.pk"}]
    results = await enrichment_pipeline.enrich_items_batch(
        items, city="Karachi", country="Pakistan", country_code="PK", use_browser=True,
    )

    assert results[0]["enrichment_status"] == "failed"
    assert results[0]["enrichment_error"] == "missing name"


async def test_batch_survives_browser_call_failure(monkeypatch):
    async def failing_extract(urls, country_code=None):
        raise RuntimeError("chromium missing")

    monkeypatch.setattr(enrichment_pipeline.browser_scraper_service, "extract_contact_details", failing_extract)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", lambda *a, **k: None)

    items = [{"name": "A", "website": "https://a.pk", "lat": 1, "lon": 1}]
    results = await enrichment_pipeline.enrich_items_batch(
        items, city="Karachi", country="Pakistan", country_code="PK", use_browser=True,
    )

    assert results[0]["enrichment_status"] == "done"  # degraded, not crashed
    assert results[0].get("email") is None


async def test_batch_result_matches_single_item_enrich(monkeypatch):
    """enrich_items_batch([item]) should behave the same as enrich_item(item)
    for the fields that matter, since it's a drop-in replacement for the
    per-item loop in _inline_enrich."""
    async def fake_fetch_plain(url, country_code=None):
        return {"email": "info@sakura.pk", "email_candidates": [], "hours": "9-5", "social_links": {}}

    monkeypatch.setattr(enrichment_pipeline.website_scraper_service, "fetch_plain", fake_fetch_plain)
    monkeypatch.setattr(enrichment_pipeline.website_scraper_service, "extract_contact_from_website", fake_fetch_plain)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", lambda *a, **k: None)

    item = {"name": "Sakura Dental Studio", "website": "https://sakura.pk", "lat": 24.8, "lon": 67.0}

    single = await enrichment_pipeline.enrich_item(
        item, city="Karachi", country="Pakistan", country_code="PK", use_browser=False,
    )
    batch = await enrichment_pipeline.enrich_items_batch(
        [item], city="Karachi", country="Pakistan", country_code="PK", use_browser=False,
    )

    assert single["email"] == batch[0]["email"] == "info@sakura.pk"
    assert single["hours"] == batch[0]["hours"] == "9-5"
    assert single["enrichment_status"] == batch[0]["enrichment_status"] == "done"


async def test_batch_maps_lookup_fills_phone_for_name_only_lead(monkeypatch):
    """A name-only OSM lead (no phone/website) gets its real GBP panel data via
    the Google Maps name-lookup when use_google_maps=True."""
    calls = []

    async def fake_lookup(name, city, country):
        calls.append(name)
        assert city == "Karachi" and country == "Pakistan"
        return {
            "name": name,
            "phone": "+92 21 32224110",
            "website": "https://alnoor.pk",
            "address": "Pardesi Heights, Shah Abdul Latif Rd, Karachi",
            "hours": "Open · Closes 8 PM",
            "rating": 4.4,
        }

    monkeypatch.setattr(enrichment_pipeline.maps_crawler, "lookup_business_by_name", fake_lookup)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", lambda *a, **k: None)

    items = [{"name": "Sabah Al-Noor Medical Centre", "lat": 24.9, "lon": 67.05}]
    results = await enrichment_pipeline.enrich_items_batch(
        items, city="Karachi", country="Pakistan", country_code="PK",
        use_browser=False, use_google_maps=True,
    )

    assert calls == ["Sabah Al-Noor Medical Centre"]
    assert results[0]["phone"] == "+92 21 32224110"
    assert results[0]["website"] == "https://alnoor.pk"
    assert "google_maps" in results[0]["enrichment_source"]
    assert results[0]["enrichment_status"] == "done"


async def test_batch_skips_maps_lookup_when_lead_has_phone(monkeypatch):
    """Leads that already carry a phone/website don't burn a Maps lookup."""
    calls = []

    async def fake_lookup(name, city, country):
        calls.append(name)
        return {"phone": "+92 21 5555555"}

    monkeypatch.setattr(enrichment_pipeline.maps_crawler, "lookup_business_by_name", fake_lookup)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", lambda *a, **k: None)

    items = [
        {"name": "Has Phone Co", "phone": "+92 300 1111111", "lat": 1, "lon": 1},
        {"name": "Needs Lookup Co", "lat": 1, "lon": 1},
    ]
    await enrichment_pipeline.enrich_items_batch(
        items, city="Karachi", country="Pakistan", country_code="PK",
        use_browser=False, use_google_maps=True,
    )

    assert calls == ["Needs Lookup Co"]


async def test_batch_maps_lookup_off_by_default(monkeypatch):
    """use_google_maps defaults to False, so no Maps crawler traffic fires
    unless the caller opts in."""
    calls = []

    async def fake_lookup(name, city, country):
        calls.append(name)
        return {"phone": "+92 21 1111111"}

    monkeypatch.setattr(enrichment_pipeline.maps_crawler, "lookup_business_by_name", fake_lookup)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", lambda *a, **k: None)

    items = [{"name": "Name Only Co", "lat": 1, "lon": 1}]
    await enrichment_pipeline.enrich_items_batch(
        items, city="Karachi", country="Pakistan", country_code="PK", use_browser=False,
    )

    assert calls == []


async def test_batch_maps_lookup_survives_lookup_failure(monkeypatch):
    """A failed Maps lookup degrades gracefully (lead stays name-only) instead
    of crashing the whole batch."""
    async def failing_lookup(name, city, country):
        raise RuntimeError("blocked")

    monkeypatch.setattr(enrichment_pipeline.maps_crawler, "lookup_business_by_name", failing_lookup)
    monkeypatch.setattr(enrichment_pipeline, "validate_email", lambda e: e)
    monkeypatch.setattr(enrichment_pipeline.geocoding_service, "geocode_business", lambda *a, **k: None)

    items = [{"name": "Name Only Co", "lat": 1, "lon": 1}]
    results = await enrichment_pipeline.enrich_items_batch(
        items, city="Karachi", country="Pakistan", country_code="PK",
        use_browser=False, use_google_maps=True,
    )

    assert results[0]["enrichment_status"] == "done"
    assert results[0].get("phone") is None
