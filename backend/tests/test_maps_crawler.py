import pytest

from app.services.crawlers import maps_crawler

PLACE_URL = (
    "https://www.google.com/maps/place/Sakura+Dental+Studio/"
    "data=!4m5!3m4!1s0x0:0x0!8m2!3d24.8607!4d67.0011"
)
CARD_TEXT = "Sakura Dental Studio\n4.8\n(120)\nDentist"


class TestParsers:
    def test_coords_extracted_from_place_url(self):
        lat, lon = maps_crawler._coords_from_url(PLACE_URL)
        assert lat == 24.8607
        assert lon == 67.0011

    def test_coords_none_for_non_place_url(self):
        assert maps_crawler._coords_from_url("https://google.com") == (None, None)

    def test_parse_card(self):
        card = maps_crawler._parse_card(CARD_TEXT)
        assert card["name"] == "Sakura Dental Studio"
        assert card["rating"] == 4.8
        assert card["review_count"] == 120
        assert card["category"] == "Dentist"


class FakeEl:
    def __init__(self, attrs=None, text=""):
        self.attrs = attrs or {}
        self.text = text

    async def get_attribute(self, name):
        return self.attrs.get(name)

    async def inner_text(self):
        return self.text

    async def evaluate(self, expr):
        return None


class FakePage:
    def __init__(self, feed_links, panel):
        self.feed_links = feed_links
        self.panel = panel
        self.visited = []

    async def goto(self, url, **kwargs):
        self.visited.append(url)

    async def wait_for_selector(self, sel, **kwargs):
        if 'role="feed"' in sel:
            return FakeEl({})
        raise Exception("feed not found")

    async def wait_for_timeout(self, ms):
        pass

    async def query_selector(self, sel):
        if 'role="feed"' in sel:
            return FakeEl({})
        for key, el in self.panel.items():
            if key in sel:
                return el
        return None

    async def query_selector_all(self, sel):
        if 'a[href*="/maps/place/"]' in sel:
            return self.feed_links
        return []

    async def close(self):
        pass


class FakeContext:
    def __init__(self, panel):
        self.panel = panel
        self.pages = []

    async def new_page(self):
        page = FakePage(feed_links=[], panel=self.panel)
        self.pages.append(page)
        return page


class FakeBrowser:
    def __init__(self, panel):
        self.panel = panel

    async def new_context(self, **kwargs):
        return FakeContext(self.panel)

    async def close(self):
        pass


class FakeChromium:
    def __init__(self, panel):
        self.panel = panel

    async def launch(self, **kwargs):
        return FakeBrowser(self.panel)


class FakePlaywright:
    def __init__(self, panel):
        self.chromium = FakeChromium(panel)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _panel():
    return {
        "h1": FakeEl({}, "Sakura Dental Studio"),
        "out of 5": FakeEl({"aria-label": "Rated 4.8 out of 5"}),
        "reviews": FakeEl({"aria-label": "123 reviews"}),
        "category": FakeEl({}, "Dentist"),
        "phone:": FakeEl({"aria-label": "Phone: 0300 1234567"}),
        "authority": FakeEl({"href": "https://sakura.pk"}),
        "address": FakeEl({"aria-label": "Address: 1 Main Street, Karachi"}),
        "oloc": FakeEl({"aria-label": "Plus code: 2G2G+22 Karachi"}),
        "oh": FakeEl({}, "Open · Closes 8 PM"),
    }


@pytest.mark.asyncio
async def test_search_businesses_end_to_end(monkeypatch):
    monkeypatch.setattr(maps_crawler, "_human_pause", lambda *a, **k: __import__("asyncio").sleep(0))
    panel = _panel()
    fake_pw = FakePlaywright(panel)
    monkeypatch.setattr(maps_crawler, "async_playwright", lambda: fake_pw)

    async def fake_collect(page, limit):
        return [
            {"name": "Sakura Dental Studio", "rating": 4.8, "review_count": 120,
             "category": "Dentist", "url": PLACE_URL, "lat": 24.8607, "lon": 67.0011},
            {"name": "Glow Skin Clinic", "rating": 4.5, "review_count": 80,
             "category": "Dermatologist", "url": PLACE_URL.replace("Sakura", "Glow"),
             "lat": 24.87, "lon": 67.05},
        ]

    monkeypatch.setattr(maps_crawler, "_collect_feed_links", fake_collect)

    records = await maps_crawler.search_businesses("Dental Clinic", "Karachi", "Pakistan", limit=5)

    assert len(records) == 2
    first = records[0]
    assert first["name"] == "Sakura Dental Studio"
    assert first["phone"] == "0300 1234567"
    assert first["website"] == "https://sakura.pk"
    assert first["address"] == "1 Main Street, Karachi"
    assert first["rating"] == 4.8
    assert first["review_count"] == 123
    assert first["plus_code"].startswith("2G2G+22")
    assert first["hours"] == "Open · Closes 8 PM"
    assert first["lat"] == 24.8607
    assert first["lon"] == 67.0011


@pytest.mark.asyncio
async def test_circuit_open_skips_crawl(monkeypatch):
    maps_crawler._breaker._blocked_until = 1e15
    called = False

    async def _fail(*a, **k):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(maps_crawler, "_query_url", lambda *a, **k: "http://x")
    records = await maps_crawler.search_businesses("Dental Clinic", "Karachi", "Pakistan")
    assert records == []
    maps_crawler._breaker._blocked_until = 0.0
