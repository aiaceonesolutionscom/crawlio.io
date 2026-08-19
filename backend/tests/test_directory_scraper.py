import pytest

from app.services.discovery.crawlers import directory_scraper

YELLOWPAGE_HTML = """
<html><body>
  <div class="card listing-card">
    <h2 class="h5 font-weight-bold text-dark mb-2">
      <a href="javascript:void(0);">Sakura Dental Studio</a>
    </h2>
    <div class="listing-meta-row">
      <div class="meta-item mr-3"><i class="fas fa-map-marker-alt text-danger mr-1"></i><span>Gulshan-e-Iqbal, Karachi</span></div>
      <div class="meta-item mr-3"><i class="fas fa-phone-alt text-success mr-1"></i><a href="tel:0300 1234567" class="text-secondary">0300 1234567</a></div>
    </div>
  </div>
  <div class="card listing-card">
    <h2><a href="javascript:void(0);">Glow Skin Clinic</a></h2>
    <a href="tel:021-35870000">021-35870000</a>
  </div>
</body></html>
"""

HOTFROG_HTML = r"""
<html><body>
<script>
window.mapBubbles=[{"lat":1,"lng":2,"html":"<small><span><a href=\"/company/1/restaurant/london\"><strong>Sakura Restaurant</strong></a><br />\n<br />  10 High St, London<br />\n<a href=\"tel:+44-20-1234-5678\">020 1234 5678</a><br /></span></small>"},{"lat":3,"lng":4,"html":"<small><span><a href=\"/company/2/x\"><strong>Glow Cafe</strong></a><br />\n<a href=\"tel:+44-20-9999-0000\">020 9999 0000</a><br /></span></small>"}];
</script>
</body></html>
"""


class TestParseYellowpageCards:
    def test_extracts_name_phone_address(self):
        records = directory_scraper._parse_yellowpage_cards(YELLOWPAGE_HTML)
        phones = {r["phone"] for r in records}
        assert "0300 1234567" in phones
        sakura = next(r for r in records if r["phone"] == "0300 1234567")
        assert sakura["name"] == "Sakura Dental Studio"
        assert sakura["address"] == "Gulshan-e-Iqbal, Karachi"

    def test_keeps_record_with_phone_only(self):
        records = directory_scraper._parse_yellowpage_cards(YELLOWPAGE_HTML)
        assert any(r["phone"] == "021-35870000" for r in records)

    def test_unescapes_html_entities(self):
        html = '<div class="card listing-card"><h2><a>ARMAN\'S HOTEL &amp; BANQUET</a></h2><a href="tel:0302-8936767">0302-8936767</a></div>'
        records = directory_scraper._parse_yellowpage_cards(html)
        assert records[0]["name"] == "ARMAN'S HOTEL & BANQUET"

    def test_empty_html(self):
        assert directory_scraper._parse_yellowpage_cards("") == []

    def test_short_phone_ignored(self):
        html = '<div class="card listing-card"><h2><a>Acme</a></h2><a href="tel:1234">x</a></div>'
        assert directory_scraper._parse_yellowpage_cards(html) == []


class TestParseHotfrog:
    def test_extracts_from_map_bubbles(self):
        records = directory_scraper._parse_hotfrog(HOTFROG_HTML)
        phones = {r["phone"] for r in records}
        assert "+44-20-1234-5678" in phones
        sakura = next(r for r in records if r["phone"] == "+44-20-1234-5678")
        assert sakura["name"] == "Sakura Restaurant"

    def test_dedups(self):
        records = directory_scraper._parse_hotfrog(HOTFROG_HTML + HOTFROG_HTML)
        assert len(records) == 2

    def test_empty_html(self):
        assert directory_scraper._parse_hotfrog("") == []


@pytest.mark.asyncio
async def test_search_businesses_merges_and_dedups(monkeypatch):
    monkeypatch.setattr(directory_scraper.settings, "directory_enabled", True)

    calls = []

    async def fake_fetch(url):
        calls.append(url)
        if "yellowpage.pk/search" in url:
            return '<div class="card listing-card"><h2><a>Acme</a></h2><a href="tel:03001234567">03001234567</a></div>'
        if "hotfrog.com" in url:
            return 'window.mapBubbles=[{"html":"<strong>Acme</strong><a href=\\"tel:03001234567\\">03001234567</a>"}];'
        return None

    monkeypatch.setattr(directory_scraper, "_fetch", fake_fetch)

    records = await directory_scraper.search_businesses("Dental Clinic", "Karachi", "Pakistan", limit=10)
    assert len(records) == 1
    assert records[0]["name"] == "Acme"
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
