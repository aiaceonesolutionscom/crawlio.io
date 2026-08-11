import respx
from httpx import Response

from app.core.config import settings
from app.services import ai_extraction_service, enrichment_pipeline, tavily_service


# --- Tavily: enrich_business -------------------------------------------------


async def test_enrich_business_returns_relevant_results_only(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "fake-key-for-test")

    results = [
        {"title": "Sakura Steakhouse Karachi contact", "url": "https://sakura.pk/contact",
         "content": "Call us at 021-111-222-333", "raw_content": "..."},
        {"title": "Sakura sushi recipe blog (Osaka)", "url": "https://recipeblog.example/sakura",
         "content": "A sakura blossom dessert from Osaka", "raw_content": "..."},
    ]
    with respx.mock:
        respx.post("https://api.tavily.com/search").mock(return_value=Response(200, json={"results": results}))
        found = await tavily_service.enrich_business("Sakura Steakhouse", "Karachi", "Pakistan")

    assert len(found) == 1
    assert found[0]["url"] == "https://sakura.pk/contact"


async def test_enrich_business_returns_empty_without_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "")
    assert await tavily_service.enrich_business("X", "Karachi", "Pakistan") == []


# --- Tavily: find_social_links -----------------------------------------------


async def test_find_social_links_maps_platforms(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "fake-key-for-test")

    results = [
        {"title": "Sakura Steakhouse Karachi (@sakurakarachi)", "url": "https://www.instagram.com/sakurakarachi",
         "content": ""},
        {"title": "Sakura Steakhouse Karachi - Facebook", "url": "https://www.facebook.com/sakurakarachi",
         "content": ""},
        {"title": "unrelated instagram page", "url": "https://www.instagram.com/sakura",
         "content": ""},
    ]
    with respx.mock:
        respx.post("https://api.tavily.com/search").mock(return_value=Response(200, json={"results": results}))
        socials = await tavily_service.find_social_links("Sakura Steakhouse", "Karachi", "Pakistan")

    assert socials.get("instagram") == "https://www.instagram.com/sakurakarachi"
    assert socials.get("facebook") == "https://www.facebook.com/sakurakarachi"
    assert "https://www.instagram.com/sakura" not in socials.values()


# --- AI extraction -----------------------------------------------------------


async def test_extract_contact_parses_llm_json(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "fake-key-for-test")

    llm_response = {
        "choices": [{
            "message": {
                "content": (
                    '{"email": "hello@brightsmile.pk", "phone": "+92 21 111 111 001", '
                    '"website": "https://brightsmile.pk", "address": "Clifton Karachi", '
                    '"hours": "Mon-Sat 9am-7pm", "description": "Dental clinic", '
                    '"social_links": {"instagram": "https://instagram.com/brightsmile"}, '
                    '"confidence": 0.9}'
                )
            }
        }]
    }
    with respx.mock:
        respx.post("https://api.mistral.ai/v1/chat/completions").mock(return_value=Response(200, json=llm_response))
        result = await ai_extraction_service.extract_contact(
            "Bright Smile Dental in Karachi is a family-friendly dental clinic. "
            "Call us at +92 21 111 111 001 or email hello@brightsmile.pk. "
            "We are open Mon-Sat 9am-7pm at 12 Main Clifton Road, Karachi. "
            "Visit https://brightsmile.pk for more details and to book an appointment.",
            "Bright Smile Dental", "Karachi", website="https://brightsmile.pk",
        )

    assert result["email"] == "hello@brightsmile.pk"
    assert result["phone"] == "+92 21 111 111 001"
    assert result["social_links"]["instagram"] == "https://instagram.com/brightsmile"
    assert result["confidence"] == 0.9


async def test_extract_contact_returns_empty_without_key(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "")
    assert await ai_extraction_service.extract_contact("x", "Y", "Z") == {}


# --- Enrichment pipeline -----------------------------------------------------


async def test_enrich_item_fills_from_own_website(monkeypatch):
    from app.services import website_scraper_service

    async def fake_scrape(url, country_code=None):
        return {
            "email": "hello@brightsmile.pk",
            "phone": "+92 21 111 111 001",
            "social_links": {"facebook": "https://facebook.com/brightsmile"},
        }

    monkeypatch.setattr(website_scraper_service, "extract_contact_from_website", fake_scrape)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Bright Smile Dental", "website": "https://brightsmile.pk"},
        city="Karachi", country="Pakistan", country_code="PK",
        use_browser=False, use_ai=False,
    )

    assert result["email"] == "hello@brightsmile.pk"
    assert result["phone"] == "+92 21 111 111 001"
    assert result["enrichment_status"] == "done"
    assert result["completeness"] >= 80


async def test_enrich_item_uses_web_search_for_no_website(monkeypatch):
    from app.services import tavily_service, website_scraper_service

    async def no_scrape(url, country_code=None):
        return {}

    async def no_website(*args, **kwargs):
        return None

    async def web_results(*args, **kwargs):
        return [{"title": "Test Cafe Karachi contact", "url": "https://testcafe.pk", "content": "x"}]

    async def ai_extract(name, city, results):
        return {
            "email": "hello@testcafe.pk",
            "phone": "+92 300 1234567",
            "website": "https://testcafe.pk",
            "social_links": {"instagram": "https://instagram.com/testcafe"},
        }

    async def no_socials(*args, **kwargs):
        return {}

    monkeypatch.setattr(website_scraper_service, "extract_contact_from_website", no_scrape)
    monkeypatch.setattr(tavily_service, "find_website_url", no_website)
    monkeypatch.setattr(tavily_service, "enrich_business", web_results)
    monkeypatch.setattr(tavily_service, "find_social_links", no_socials)
    monkeypatch.setattr(ai_extraction_service, "extract_from_tavily_results", ai_extract)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Test Cafe", "address": "Karachi"},
        city="Karachi", country="Pakistan", country_code="PK",
        use_browser=False, use_ai=True,
    )

    assert result["email"] == "hello@testcafe.pk"
    assert result["website"] == "https://testcafe.pk"
    assert result["social_links"]["instagram"] == "https://instagram.com/testcafe"
    assert result["enrichment_status"] == "done"


async def test_enrich_item_rejects_invalid_ai_email(monkeypatch):
    from app.services import tavily_service, website_scraper_service

    async def no_scrape(url, country_code=None):
        return {}

    async def no_website(*args, **kwargs):
        return None

    async def web_results(*args, **kwargs):
        return [{"title": "Test Cafe Karachi", "url": "https://testcafe.pk", "content": "x"}]

    async def ai_bad_email(name, city, results):
        return {"email": "notanemail", "phone": "+92 300 1234567"}

    async def no_socials(*args, **kwargs):
        return {}

    monkeypatch.setattr(website_scraper_service, "extract_contact_from_website", no_scrape)
    monkeypatch.setattr(tavily_service, "find_website_url", no_website)
    monkeypatch.setattr(tavily_service, "enrich_business", web_results)
    monkeypatch.setattr(tavily_service, "find_social_links", no_socials)
    monkeypatch.setattr(ai_extraction_service, "extract_from_tavily_results", ai_bad_email)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Test Cafe", "address": "Karachi"},
        city="Karachi", country="Pakistan", use_browser=False, use_ai=True,
    )

    assert result.get("email") is None
    assert result["phone"] == "+92 300 1234567"


async def test_enrich_item_finds_socials_for_website_less_business_regardless_of_tier(monkeypatch):
    """The no-website social-discovery step used to be gated behind use_ai
    (effectively Pro-only) — a website-less free-tier business should still
    get checked, since social media is often its only contact channel."""
    from app.services import duckduckgo_service, tavily_service, website_scraper_service

    async def no_website_lookup(*args, **kwargs):
        return None

    async def no_web_results(*args, **kwargs):
        return []

    async def tavily_socials(*args, **kwargs):
        return {"facebook": "https://facebook.com/testcafe"}

    async def ddg_socials(*args, **kwargs):
        return {"instagram": "https://instagram.com/testcafe"}

    monkeypatch.setattr(tavily_service, "find_website_url", no_website_lookup)
    monkeypatch.setattr(duckduckgo_service, "find_website_url", no_website_lookup)
    monkeypatch.setattr(tavily_service, "enrich_business", no_web_results)
    monkeypatch.setattr(duckduckgo_service, "enrich_business", no_web_results)
    monkeypatch.setattr(tavily_service, "find_social_links", tavily_socials)
    monkeypatch.setattr(duckduckgo_service, "find_social_links", ddg_socials)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Test Cafe", "address": "Karachi"},
        city="Karachi", country="Pakistan", use_browser=False, use_ai=False,
    )

    # Both engines' results should be merged, not "stop after the first hit."
    assert result["social_links"]["facebook"] == "https://facebook.com/testcafe"
    assert result["social_links"]["instagram"] == "https://instagram.com/testcafe"


async def test_enrich_item_social_search_not_skipped_when_partially_filled(monkeypatch):
    """A single social link found upstream used to skip the whole social
    lookup step entirely — it should instead keep looking for other
    platforms, on top of what's already there."""
    from app.services import duckduckgo_service, tavily_service

    async def no_website_lookup(*args, **kwargs):
        return None

    async def tavily_socials(*args, **kwargs):
        return {"instagram": "https://instagram.com/testcafe"}

    async def ddg_socials(*args, **kwargs):
        return {}

    monkeypatch.setattr(tavily_service, "find_website_url", no_website_lookup)
    monkeypatch.setattr(duckduckgo_service, "find_website_url", no_website_lookup)
    monkeypatch.setattr(tavily_service, "find_social_links", tavily_socials)
    monkeypatch.setattr(duckduckgo_service, "find_social_links", ddg_socials)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Test Cafe", "address": "Karachi", "social_links": {"facebook": "https://facebook.com/testcafe"}},
        city="Karachi", country="Pakistan", use_browser=False, use_ai=False,
    )

    assert result["social_links"]["facebook"] == "https://facebook.com/testcafe"
    assert result["social_links"]["instagram"] == "https://instagram.com/testcafe"


async def test_enrich_item_sets_lat_lon_from_geocoding(monkeypatch):
    from app.services import geocoding_service, website_scraper_service

    async def fake_scrape(url, country_code=None):
        return {"email": "hello@brightsmile.pk"}

    async def fake_geocode_business(address, city, country):
        return {"lat": 24.86, "lon": 67.01, "display_name": "Karachi, Sindh, Pakistan"}

    monkeypatch.setattr(website_scraper_service, "extract_contact_from_website", fake_scrape)
    monkeypatch.setattr(geocoding_service, "geocode_business", fake_geocode_business)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Bright Smile Dental", "website": "https://brightsmile.pk", "address": "Karachi"},
        city="Karachi", country="Pakistan", use_browser=False, use_ai=False,
    )

    assert result["lat"] == 24.86
    assert result["lon"] == 67.01
    # The original address text is left alone — a geocoded display_name is
    # often just a vague administrative-area name, not a more useful address.
    assert result["address"] == "Karachi"


async def test_enrich_item_geocoding_failure_does_not_break_enrichment(monkeypatch):
    from app.services import geocoding_service, website_scraper_service

    async def fake_scrape(url, country_code=None):
        return {"email": "hello@brightsmile.pk"}

    async def failing_geocode(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(website_scraper_service, "extract_contact_from_website", fake_scrape)
    monkeypatch.setattr(geocoding_service, "geocode_business", failing_geocode)

    result = await enrichment_pipeline.enrich_item(
        {"name": "Bright Smile Dental", "website": "https://brightsmile.pk", "address": "Karachi"},
        city="Karachi", country="Pakistan", use_browser=False, use_ai=False,
    )

    assert result["enrichment_status"] == "done"
    assert result.get("lat") is None


# --- AI-filter enrich endpoint ------------------------------------------------


async def test_ai_filter_enrich_dispatches_background_tasks(client_factory, monkeypatch):
    from app.api.v1 import leads as leads_api
    from app.workers.tasks_scoring import score_lead_task

    monkeypatch.setattr(score_lead_task, "delay", lambda lead_id: None)
    dispatched = []
    monkeypatch.setattr(leads_api.enrich_lead, "delay", lambda lead_id: dispatched.append(lead_id))

    async with client_factory("user_ai_enrich") as client:
        await client.post("/api/v1/workspaces", json={"name": "Acme"})
        ws = (await client.get("/api/v1/workspaces/me")).json()
        await client.patch(f"/api/v1/workspaces/{ws['id']}/plan", json={"plan": "pro"})

        created = await client.post("/api/v1/leads", json={"name": "Lead A"})
        lead_id = created.json()["id"]
        resp = await client.post("/api/v1/leads/ai-filter/enrich", json={"lead_ids": [lead_id]})

    assert resp.status_code == 200
    assert resp.json() == {"dispatched": 1}
    assert dispatched == [lead_id]
