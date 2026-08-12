import pytest

from app.services.crawlers import directory_scraper

LISTING_HTML = """
<html><body>
  <li class="listing">
    <h2>Sakura Dental Studio</h2>
    <p class="address">Gulshan-e-Iqbal, Karachi</p>
    <a href="tel:0300 1234567">0300 1234567</a>
    <a href="mailto:info@sakura.pk">info@sakura.pk</a>
    <a href="https://sakura.pk">Website</a>
  </li>
  <li class="listing">
    <h3>Glow Skin Clinic</h3>
    <a href="tel:021-35870000">021-35870000</a>
  </li>
</body></html>
"""


class TestParseListings:
    def test_extracts_phone_email_website(self):
        records = directory_scraper._parse_listings(LISTING_HTML, "https://www.cybo.com/search/?q=x")
        phones = {r["phone"] for r in records}
        assert "0300 1234567" in phones
        sakura = next(r for r in records if r["phone"] == "0300 1234567")
        assert sakura["name"] == "Sakura Dental Studio"
        assert sakura["email"] == "info@sakura.pk"
        assert sakura["website"] == "https://sakura.pk"

    def test_keeps_record_with_phone_only(self):
        records = directory_scraper._parse_listings(LISTING_HTML, "https://x.com")
        assert any(r["phone"] == "021-35870000" for r in records)

    def test_ignores_directory_own_links(self):
        html = '<a href="https://www.cybo.com/about">About</a><h2>Acme</h2><a href="tel:03001234567">call</a>'
        records = directory_scraper._parse_listings(html, "https://www.cybo.com/search")
        assert records[0]["website"] is None

    def test_empty_html(self):
        assert directory_scraper._parse_listings("", "https://x.com") == []

    def test_short_phone_ignored(self):
        records = directory_scraper._parse_listings("<h2>Acme</h2><a href='tel:1234'>x</a>", "https://x.com")
        assert records == []


@pytest.mark.asyncio
async def test_search_businesses_merges_and_dedups(monkeypatch):
    monkeypatch.setattr(directory_scraper.settings, "directory_enabled", True)

    async def fake_fetch(url):
        if "yellowpages" in url:
            return "<h2>Acme</h2><a href='tel:03001234567'>03001234567</a>"
        if "cybo.com/search" in url:
            return "<h2>Acme</h2><a href='tel:03001234567'>03001234567</a><a href='mailto:hello@acme.pk'>hello@acme.pk</a>"
        return None

    monkeypatch.setattr(directory_scraper, "_fetch", fake_fetch)

    records = await directory_scraper.search_businesses("Dental Clinic", "Karachi", "Pakistan", limit=10)
    assert len(records) == 1
    assert records[0]["name"] == "Acme"
    assert records[0]["email"] == "hello@acme.pk"
    assert records[0]["source"] == "directory"


@pytest.mark.asyncio
async def test_search_businesses_disabled(monkeypatch):
    monkeypatch.setattr(directory_scraper.settings, "directory_enabled", False)
    assert await directory_scraper.search_businesses("Dental Clinic", "Karachi", "Pakistan") == []


@pytest.mark.asyncio
async def test_search_businesses_all_fail_returns_empty(monkeypatch):
    monkeypatch.setattr(directory_scraper.settings, "directory_enabled", True)
    monkeypatch.setattr(directory_scraper, "_fetch", lambda url: None)
    assert await directory_scraper.search_businesses("Dental Clinic", "Karachi", "Pakistan") == []
