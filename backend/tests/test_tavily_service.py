import respx
from httpx import Response

from app.core.config import settings
from app.services import tavily_service


async def test_find_website_url_accepts_matching_domain(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "fake-key-for-test")

    mock_response = {
        "results": [
            {"title": "Sakura Steakhouse Karachi", "url": "https://sakurasteakhouse.com", "content": ""},
        ]
    }

    with respx.mock:
        respx.post("https://api.tavily.com/search").mock(return_value=Response(200, json=mock_response))
        url = await tavily_service.find_website_url("Sakura", "Karachi", "Pakistan")

    assert url == "https://sakurasteakhouse.com"


async def test_find_website_url_rejects_third_party_aggregator_domain(monkeypatch):
    """A business name can appear in a review/directory site's URL *path*
    while the *domain* belongs to someone else entirely — scraping that
    domain would attribute an aggregator's contact info to the business, so
    it must be rejected rather than returned as if it were the real site."""
    monkeypatch.setattr(settings, "tavily_api_key", "fake-key-for-test")

    mock_response = {
        "results": [
            {
                "title": "Kolachi Restaurant Karachi Menu With Prices",
                "url": "https://foodiespakistan.pk/karachi/kolachi-restaurant-do-darya-menu-with-prices-deals",
                "content": "",
            },
        ]
    }

    with respx.mock:
        respx.post("https://api.tavily.com/search").mock(return_value=Response(200, json=mock_response))
        url = await tavily_service.find_website_url("Kolachi Restaurant", "Karachi", "Pakistan")

    assert url is None


async def test_find_website_url_skips_social_media_links(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "fake-key-for-test")

    mock_response = {
        "results": [
            {"title": "Sakura Karachi", "url": "https://www.facebook.com/sakurakarachi", "content": ""},
        ]
    }

    with respx.mock:
        respx.post("https://api.tavily.com/search").mock(return_value=Response(200, json=mock_response))
        url = await tavily_service.find_website_url("Sakura", "Karachi", "Pakistan")

    assert url is None


async def test_find_website_url_skips_irrelevant_results(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "fake-key-for-test")

    mock_response = {
        "results": [
            {"title": "Officers Mess dining etiquette report", "url": "https://gov.example/officers-mess.pdf", "content": ""},
        ]
    }

    with respx.mock:
        respx.post("https://api.tavily.com/search").mock(return_value=Response(200, json=mock_response))
        url = await tavily_service.find_website_url("Officers Mess", "Karachi", "Pakistan")

    assert url is None


async def test_find_website_url_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "")
    url = await tavily_service.find_website_url("Sakura", "Karachi", "Pakistan")
    assert url is None
