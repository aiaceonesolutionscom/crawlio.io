import pytest
import respx
from httpx import Response

from app.services.discovery import website_lookup_service
from app.services.discovery.website_lookup_service import BING_URL, DDG_URL, GOOGLE_URL


@pytest.fixture(autouse=True)
def _disable_tavily(monkeypatch):
    """These tests exercise the free HTML engine chain (DDG -> Bing -> Google).
    Tavily runs first in the real service, but it needs an API key and an HTTP
    call — disable it so the tests stay hermetic and deterministic."""
    monkeypatch.setattr(website_lookup_service.settings, "tavily_enabled", False)


def _ddg_html(*results: str) -> str:
    """Build a fake DuckDuckGo HTML results page from raw hrefs."""
    items = []
    for href in results:
        items.append(
            f'<div class="result"><a rel="nofollow" class="result__a" href="{href}">Some Business</a></div>'
        )
    return "<html><body>" + "".join(items) + "</body></html>"


async def test_find_business_website_returns_own_site(respx_mock):
    respx_mock.get(DDG_URL).mock(
        return_value=Response(200, text=_ddg_html(
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.altamashclinic.com%2F&amp;rut=abc"
        ))
    )
    site = await website_lookup_service.find_business_website("Altamash Dental Clinic", "Karachi", "Pakistan")
    assert site == "https://www.altamashclinic.com/"


async def test_find_business_website_skips_directories_and_social(respx_mock):
    """Facebook/social and directory/portal pages are never treated as the
    business's own website — the first own-domain result wins."""
    respx_mock.get(DDG_URL).mock(
        return_value=Response(200, text=_ddg_html(
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.facebook.com%2Fcosmodentclinicss%2F&amp;rut=1",
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.marham.pk%2Fhospitals%2Fkarachi%2Fcosmodent-clinics&amp;rut=2",
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.dentists10.com%2FPK%2FKarachi%2Fcosmodent&amp;rut=3",
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fcosmodent.pk%2Fcontact%2F&amp;rut=4",
        ))
    )
    site = await website_lookup_service.find_business_website("CosmoDent Clinics", "Karachi", "Pakistan")
    assert site == "https://cosmodent.pk/contact/"


async def test_find_business_website_returns_none_when_only_directories(respx_mock, monkeypatch):
    monkeypatch.setattr(website_lookup_service, "ENGINES", [website_lookup_service.DDG_ENGINE])
    respx_mock.get(DDG_URL).mock(
        return_value=Response(200, text=_ddg_html(
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.cybo.com%2FPK-biz%2Ffoo&amp;rut=1",
            "//duckduckgo.com/l/?uddg=https%3A%2F%2Fekatlang.com%2Flisting%2Ffoo%2F&amp;rut=2",
        ))
    )
    site = await website_lookup_service.find_business_website("Some Clinic", "Karachi", "Pakistan")
    assert site is None


async def test_find_business_website_returns_none_on_http_error(respx_mock, monkeypatch):
    monkeypatch.setattr(website_lookup_service, "ENGINES", [website_lookup_service.DDG_ENGINE])
    respx_mock.get(DDG_URL).mock(return_value=Response(503))
    site = await website_lookup_service.find_business_website("Foo", "Karachi", "Pakistan")
    assert site is None


async def test_find_business_website_returns_none_on_empty_page(respx_mock, monkeypatch):
    monkeypatch.setattr(website_lookup_service, "ENGINES", [website_lookup_service.DDG_ENGINE])
    respx_mock.get(DDG_URL).mock(return_value=Response(200, text="<html><body></body></html>"))
    site = await website_lookup_service.find_business_website("Foo", "Karachi", "Pakistan")
    assert site is None


def _bing_html(*hrefs: str) -> str:
    items = []
    for href in hrefs:
        items.append(
            f'<li class="b_algo"><h2><a href="{href}">Some Business</a></h2></li>'
        )
    return "<html><body><ol>" + "".join(items) + "</ol></body></html>"


async def test_find_business_website_falls_back_to_bing_when_ddg_down(respx_mock):
    """When the first engine fails (blocked/HTTP error) the next engine answers."""
    respx_mock.get(DDG_URL).mock(return_value=Response(503))
    respx_mock.get(BING_URL).mock(
        return_value=Response(200, text=_bing_html(
            "https://www.facebook.com/someclinic/",
            "https://www.altamashclinic.com/",
        ))
    )
    site = await website_lookup_service.find_business_website("Altamash Dental Clinic", "Karachi", "Pakistan")
    assert site == "https://www.altamashclinic.com/"


def _google_html(*targets: str) -> str:
    items = []
    for target in targets:
        items.append(
            f'<div class="g"><a href="/url?q={target}&amp;sa=U&amp;ved=0">Some Business</a></div>'
        )
    return "<html><body>" + "".join(items) + "</body></html>"


async def test_find_business_website_falls_back_to_google_when_ddg_and_bing_empty(respx_mock):
    respx_mock.get(DDG_URL).mock(return_value=Response(200, text="<html><body></body></html>"))
    respx_mock.get(BING_URL).mock(return_value=Response(200, text="<html><body></body></html>"))
    respx_mock.get(GOOGLE_URL).mock(
        return_value=Response(200, text=_google_html(
            "https%3A%2F%2Fcosmodent.pk%2Fcontact%2F",
        ))
    )
    site = await website_lookup_service.find_business_website("CosmoDent", "Karachi", "Pakistan")
    assert site == "https://cosmodent.pk/contact/"
