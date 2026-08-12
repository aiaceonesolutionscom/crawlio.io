from app.services.crawlers import lead_merger
from app.services.crawlers.lead_merger import merge_businesses, normalize_name


class TestNormalizeName:
    def test_strips_legal_suffixes(self):
        assert normalize_name("Sakura Dental Studio (Pvt) Ltd") == "sakuradentalstudio"
        assert normalize_name("Sakura Dental Studio") == "sakuradentalstudio"

    def test_case_and_punctuation_ignored(self):
        assert normalize_name("Acme & Co.") == "acmeco"
        assert normalize_name("acme co") == "acmeco"


class TestMergeBusinesses:
    def test_dedups_on_name(self):
        a = {"name": "Sakura Dental Studio", "phone": "+923001234567", "source": "google_maps"}
        b = {"name": "sakura dental studio", "email": "info@sakura.pk", "source": "directory"}
        merged = merge_businesses([a, b])
        assert len(merged) == 1
        assert merged[0]["phone"] == "+923001234567"
        assert merged[0]["email"] == "info@sakura.pk"

    def test_dedups_on_phone(self):
        a = {"name": "Sakura Dental Studio", "phone": "+923001234567", "source": "google_maps"}
        b = {"name": "Sakura", "phone": "03001234567", "source": "directory"}
        merged = merge_businesses([a, b])
        assert len(merged) == 1

    def test_more_trustworthy_source_wins_conflict(self):
        a = {"name": "Sakura", "phone": "+923001234567", "source": "google_maps"}
        b = {"name": "Sakura", "phone": "+923009999999", "source": "directory"}
        merged = merge_businesses([a, b])
        assert merged[0]["phone"] == "+923001234567"

    def test_coordinates_fill_gap(self):
        a = {"name": "Sakura", "phone": "+923001234567", "source": "google_maps"}
        b = {"name": "Sakura", "lat": 24.86, "lon": 67.0, "source": "openstreetmap"}
        merged = merge_businesses([a, b])
        assert merged[0]["lat"] == 24.86
        assert merged[0]["lon"] == 67.0

    def test_socials_merge_without_clobber(self):
        a = {"name": "Sakura", "source": "google_maps", "social_links": {"facebook": "https://fb.com/sakura"}}
        b = {"name": "Sakura", "source": "directory", "social_links": {"instagram": "https://ig.com/sakura"}}
        merged = merge_businesses([a, b])
        assert merged[0]["social_links"] == {
            "facebook": "https://fb.com/sakura",
            "instagram": "https://ig.com/sakura",
        }

    def test_distinct_businesses_stay_separate(self):
        a = {"name": "Sakura Dental Studio", "phone": "+923001234567", "source": "google_maps"}
        b = {"name": "Glow Skin Clinic", "phone": "+923009876543", "source": "google_maps"}
        merged = merge_businesses([a, b])
        assert len(merged) == 2

    def test_skips_nameless_records(self):
        assert merge_businesses([{"phone": "123"}, {"name": ""}]) == []
