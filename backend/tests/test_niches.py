from app.data.niches import canonical_niche_key, niche_keywords, resolve_niche_tags


class TestCanonicalNicheKey:
    def test_synonyms_share_one_key(self):
        assert canonical_niche_key("Dental Clinic") == canonical_niche_key("Dentist")

    def test_lawyer_synonyms_share_one_key(self):
        assert canonical_niche_key("Lawyer") == canonical_niche_key("Attorney") == canonical_niche_key("Law Firm")

    def test_case_and_whitespace_insensitive(self):
        assert canonical_niche_key("  Dental Clinic  ") == canonical_niche_key("dental clinic")

    def test_unmapped_niche_still_gets_a_stable_key(self):
        key1 = canonical_niche_key("Underwater Basket Weaving")
        key2 = canonical_niche_key("Underwater Basket Weaving")
        assert key1 == key2
        assert key1 == "underwater basket weaving"

    def test_different_niches_get_different_keys(self):
        assert canonical_niche_key("Dental Clinic") != canonical_niche_key("Restaurant")


class TestResolveNicheTagsAndKeywordsUnaffected:
    """canonical_niche_key was added via a shared-matching refactor of
    resolve_niche_tags/niche_keywords — confirm their existing behavior held."""

    def test_resolve_niche_tags_exact_match(self):
        tags, matched = resolve_niche_tags("dentist")
        assert matched is True
        assert tags == [{"amenity": "dentist"}]

    def test_resolve_niche_tags_substring_match(self):
        tags, matched = resolve_niche_tags("Dental Clinic")
        assert matched is True
        assert tags == [{"amenity": "dentist"}]

    def test_resolve_niche_tags_unmapped(self):
        tags, matched = resolve_niche_tags("Underwater Basket Weaving")
        assert matched is False
        assert tags == []

    def test_niche_keywords_returns_synonym_group(self):
        assert set(niche_keywords("Dentist")) == {"dental", "dentist"}

    def test_niche_keywords_unmapped_returns_empty(self):
        assert niche_keywords("Underwater Basket Weaving") == []
