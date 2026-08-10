import re

import respx
from httpx import Response

from app.services import duckduckgo_service


SAMPLE_HTML = """
<html><body>
<div class="result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fsakura.pk%2F">Sakura Dental Studio</a>
  </h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fsakura.pk%2F">
    Dental clinic in Karachi, book an appointment online.</a>
</div>
<div class="result">
  <h2 class="result__title">
    <a rel="nofollow" class="result__a"
       href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.instagram.com%2Fsakura">Sakura on Instagram</a>
  </h2>
</div>
</body></html>
"""


def test_real_url_unwraps_duckduckgo_redirect():
    assert duckduckgo_service._real_url(
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fsakura.pk%2Fcontact"
    ) == "https://sakura.pk/contact"
    assert duckduckgo_service._real_url("https://sakura.pk") == "https://sakura.pk"
    assert duckduckgo_service._real_url("//duckduckgo.com/l/?uddg=") == ""


def test_result_parser_extracts_entries():
    parser = duckduckgo_service._ResultParser()
    parser.feed(SAMPLE_HTML)
    parser.close()
    results = parser.results

    assert len(results) == 2
    first = results[0]
    assert first["url"] == "https://sakura.pk/"
    assert "Sakura Dental Studio" in first["title"]
    assert "book an appointment" in first["content"]
    assert results[1]["url"] == "https://www.instagram.com/sakura"
    assert results[1]["content"] == ""


async def test_search_returns_parsed_results():
    with respx.mock:
        respx.get(url=re.compile(r"https://html\.duckduckgo\.com/html/\?q=.+")).mock(
            return_value=Response(200, text=SAMPLE_HTML)
        )
        results = await duckduckgo_service.search("dental clinic in Karachi")

    assert len(results) == 2
    assert results[0]["title"] == "Sakura Dental Studio"


async def test_search_returns_empty_on_failure():
    with respx.mock:
        respx.get(url=re.compile(r"https://html\.duckduckgo\.com/html/\?q=.+")).mock(
            return_value=Response(403, text="bot detected")
        )
        assert await duckduckgo_service.search("anything") == []


async def test_find_website_url_accepts_own_domain_only(monkeypatch):
    async def fake_search(query, max_results=8):
        return [
            {"title": "Sakura Dental Studio Karachi", "url": "https://sakura.pk", "content": "x"},
            {"title": "Sakura Dental Studio on Yelp", "url": "https://www.yelp.com/biz/sakura", "content": "x"},
        ]

    monkeypatch.setattr(duckduckgo_service, "search", fake_search)
    assert await duckduckgo_service.find_website_url("Sakura Dental Studio", "Karachi", "Pakistan") == "https://sakura.pk"


async def test_find_social_links_maps_platforms(monkeypatch):
    async def fake_search(query, max_results=8):
        return [
            {"title": "Sakura Dental Studio (@sakurakarachi)", "url": "https://www.instagram.com/sakurakarachi", "content": ""},
            {"title": "Sakura Dental Studio - Facebook", "url": "https://www.facebook.com/sakurakarachi", "content": ""},
            {"title": "Unrelated", "url": "https://www.instagram.com/sakura", "content": ""},
        ]

    monkeypatch.setattr(duckduckgo_service, "search", fake_search)
    socials = await duckduckgo_service.find_social_links("Sakura Dental Studio", "Karachi")

    assert socials.get("instagram") == "https://www.instagram.com/sakurakarachi"
    assert socials.get("facebook") == "https://www.facebook.com/sakurakarachi"
    assert "https://www.instagram.com/sakura" not in socials.values()