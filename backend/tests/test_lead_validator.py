import pytest

from app.services.crawlers import lead_validator
from app.services.crawlers.lead_validator import (
    _has_mx,
    normalize_phone,
    validate_email,
    validate_lead,
)


class TestNormalizePhone:
    def test_pk_mobile_local_format(self):
        assert normalize_phone("0300 1234567") == "+923001234567"
        assert normalize_phone("03001234567") == "+923001234567"

    def test_pk_mobile_international_format(self):
        assert normalize_phone("+92 300 1234567") == "+923001234567"
        assert normalize_phone("00923 001234567") == "+923001234567"

    def test_pk_landline(self):
        assert normalize_phone("042-35741234") == "+924235741234"
        assert normalize_phone("04235741234") == "+924235741234"

    def test_fake_numbers_rejected(self):
        assert normalize_phone("1111111111") is None
        assert normalize_phone("1234567890") is None
        assert normalize_phone("123") is None

    def test_generic_country_keeps_long_national(self):
        # Worldwide normalization: a US national number becomes canonical E.164
        # (+1...) so the WhatsApp deep-link builder can use it directly.
        assert normalize_phone("212-555-0134", "US") == "+12125550134"

    def test_pk_garbage_rejected(self):
        assert normalize_phone("not a phone", "PK") is None


class TestEmailValidation:
    def test_blocklist_system_addresses(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: True)
        assert validate_email("noreply@example.com") is None
        assert validate_email("no-reply@acme.com") is None
        assert validate_email("postmaster@acme.com") is None

    def test_placeholder_rejected(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: True)
        assert validate_email("yourname@yourdomain.com") is None
        assert validate_email("demo@test.com") is None

    def test_disposable_rejected(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: True)
        assert validate_email("joe@mailinator.com") is None

    def test_mx_check_gates_deliverability(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: d == "good.com")
        assert validate_email("info@good.com") == "info@good.com"
        assert validate_email("info@nodomain.com") is None

    def test_malformed_rejected(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: True)
        assert validate_email("not-an-email") is None
        assert validate_email("a@b") is None

    def test_valid_email_normalized_lowercase(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: True)
        assert validate_email("Info@Acme.com") == "info@acme.com"

    def test_has_mx_caches(self, monkeypatch):
        import dns.resolver

        calls = []

        class FakeAnswers:
            def __bool__(self):
                return True

            def __len__(self):
                return 1

        def fake_resolve(self, domain, rtype):
            calls.append(domain)
            return FakeAnswers()

        monkeypatch.setattr(lead_validator, "_MX_CACHE", {})
        monkeypatch.setattr(dns.resolver.Resolver, "resolve", fake_resolve)
        assert _has_mx("crawlio.io") is True
        assert _has_mx("crawlio.io") is True
        assert calls == ["crawlio.io"]


class TestValidateLead:
    def test_drops_lead_with_no_contact_channel(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: True)
        assert validate_lead({"name": "X"}) is None
        assert validate_lead({"name": "X", "phone": "03001234567", "email": "a@bad"}) is not None

    def test_accepts_lead_with_address_and_coords(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: True)
        lead = validate_lead(
            {"name": "Advanced Dental Care", "address": "Shahnawaz Bhutto Rd, Karachi", "lat": 24.87, "lon": 67.03},
            "PK",
        )
        assert lead is not None
        assert lead["name"] == "Advanced Dental Care"

    def test_still_drops_name_without_address_or_coords(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: True)
        assert validate_lead({"name": "Bare Name", "address": "Karachi"}, "PK") is None
        assert validate_lead({"name": "Bare Name", "lat": 24.87, "lon": 67.03}, "PK") is None

    def test_cleans_phone_and_email(self, monkeypatch):
        monkeypatch.setattr(lead_validator, "_has_mx", lambda d: True)
        lead = validate_lead(
            {"name": "X", "phone": "0300-1234567", "email": "info@sakura.pk", "website": "https://sakura.pk"},
            "PK",
        )
        assert lead["phone"] == "+923001234567"
        assert lead["email"] == "info@sakura.pk"
