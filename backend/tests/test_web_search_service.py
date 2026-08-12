import respx
from httpx import Response

from app.services.crawlers import web_search_service


def _enable(monkeypatch, max_results=10):
    monkeypatch.setattr(web_search_service.settings, "tavily_enabled", True)
    monkeypatch.setattr(web_search_service.settings, "tavily_api_key", "test-key")
    monkeypatch.setattr(web_search_service.settings, "tavily_max_results", max_results)


async def test_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(web_search_service.settings, "tavily_enabled", False)
    monkeypatch.setattr(web_search_service.settings, "tavily_api_key", "test-key")
    result = await web_search_service.find_extra_businesses("Dental Clinic", "Islamabad", "Pakistan", limit=5)
    assert result == []


async def test_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.setattr(web_search_service.settings, "tavily_enabled", True)
    monkeypatch.setattr(web_search_service.settings, "tavily_api_key", "")
    result = await web_search_service.find_extra_businesses("Dental Clinic", "Islamabad", "Pakistan", limit=5)
    assert result == []


async def test_returns_name_and_website_only_no_guessed_contact_info(monkeypatch):
    _enable(monkeypatch)
    with respx.mock:
        respx.post(web_search_service.TAVILY_URL).mock(
            return_value=Response(200, json={"results": [
                {"title": "New Dental Clinic", "url": "https://newclinic.pk", "content": "call us at 0300-1234567, email info@newclinic.pk"},
            ]})
        )
        result = await web_search_service.find_extra_businesses("Dental Clinic", "Islamabad", "Pakistan", limit=5)

    assert len(result) == 1
    record = result[0]
    assert record["name"] == "New Dental Clinic"
    assert record["website"] == "https://newclinic.pk"
    assert record["source"] == "web_search"
    assert "email" not in record
    assert "phone" not in record
    assert "address" not in record


async def test_strips_seo_stuffed_name_at_pipe(monkeypatch):
    _enable(monkeypatch)
    with respx.mock:
        respx.post(web_search_service.TAVILY_URL).mock(
            return_value=Response(200, json={"results": [
                {"title": "Acme Dental | Best Dentist in Islamabad | Top Rated", "url": "https://acmedental.pk"},
            ]})
        )
        result = await web_search_service.find_extra_businesses("Dental Clinic", "Islamabad", "Pakistan", limit=5)

    assert result[0]["name"] == "Acme Dental"


async def test_filters_out_directory_and_portal_urls(monkeypatch):
    _enable(monkeypatch)
    with respx.mock:
        respx.post(web_search_service.TAVILY_URL).mock(
            return_value=Response(200, json={"results": [
                {"title": "Best Dental Clinics in Islamabad", "url": "https://www.yellowpages.com.pk/islamabad-dentists"},
                {"title": "Real Clinic", "url": "https://realclinic.pk"},
            ]})
        )
        result = await web_search_service.find_extra_businesses("Dental Clinic", "Islamabad", "Pakistan", limit=5)

    assert len(result) == 1
    assert result[0]["website"] == "https://realclinic.pk"


async def test_respects_limit(monkeypatch):
    _enable(monkeypatch)
    with respx.mock:
        respx.post(web_search_service.TAVILY_URL).mock(
            return_value=Response(200, json={"results": [
                {"title": f"Clinic {i}", "url": f"https://clinic{i}.pk"} for i in range(5)
            ]})
        )
        result = await web_search_service.find_extra_businesses("Dental Clinic", "Islamabad", "Pakistan", limit=2)

    assert len(result) == 2


async def test_never_raises_on_http_failure(monkeypatch):
    _enable(monkeypatch)
    with respx.mock:
        respx.post(web_search_service.TAVILY_URL).mock(return_value=Response(500))
        result = await web_search_service.find_extra_businesses("Dental Clinic", "Islamabad", "Pakistan", limit=5)

    assert result == []


async def test_never_raises_on_malformed_response(monkeypatch):
    _enable(monkeypatch)
    with respx.mock:
        respx.post(web_search_service.TAVILY_URL).mock(return_value=Response(200, content=b"not json"))
        result = await web_search_service.find_extra_businesses("Dental Clinic", "Islamabad", "Pakistan", limit=5)

    assert result == []


async def test_skips_results_missing_title_or_url(monkeypatch):
    _enable(monkeypatch)
    with respx.mock:
        respx.post(web_search_service.TAVILY_URL).mock(
            return_value=Response(200, json={"results": [
                {"title": "", "url": "https://noname.pk"},
                {"title": "No URL Clinic", "url": ""},
                {"title": "Valid Clinic", "url": "https://validclinic.pk"},
            ]})
        )
        result = await web_search_service.find_extra_businesses("Dental Clinic", "Islamabad", "Pakistan", limit=5)

    assert len(result) == 1
    assert result[0]["name"] == "Valid Clinic"
