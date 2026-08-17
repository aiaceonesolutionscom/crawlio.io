"""Tests for the Sprint 4 data-quality modules.

Pure unit tests (no real SMTP/DNS): email pattern prediction, WhatsApp/E.164
normalization, team-person extraction, and SMTP-verifier logic with a mocked
SMTP session.
"""
from app.services.crawlers import email_patterns, smtp_verify, team_contacts, whatsapp_links


# ---------------------------------------------------------------------------
# Email patterns
# ---------------------------------------------------------------------------

def test_guess_email_basic():
    assert email_patterns.guess_email("John Smith", "acme.com") == "john.smith@acme.com"


def test_guess_email_strips_www_and_titles():
    assert email_patterns.guess_email("John Smith, DDS", "www.acme.com") == "john.smith@acme.com"


def test_guess_email_requires_two_names():
    assert email_patterns.guess_email("Cher", "acme.com") is None


def test_candidates_first_last_comes_first():
    cands = email_patterns.person_email_candidates("John Smith", "acme.com")
    assert cands[0] == "john.smith@acme.com"


def test_candidates_include_common_variants():
    cands = email_patterns.person_email_candidates("John Smith", "acme.com")
    assert "j.smith@acme.com" in cands
    assert "jsmith@acme.com" in cands
    assert "johns@acme.com" in cands
    assert "john_smith@acme.com" in cands


def test_candidates_dedupe_and_cap():
    cands = email_patterns.person_email_candidates("John Smith", "acme.com", max_candidates=5)
    assert len(cands) == 5
    assert len(set(cands)) == len(cands)


def test_candidates_three_names():
    cands = email_patterns.person_email_candidates("John David Smith", "acme.com")
    assert cands[0] == "john.smith@acme.com"
    assert "johnsmith@acme.com" not in cands  # middle-initial variant is lower priority


def test_best_match_by_domain():
    cands = ["john@gmail.com", "john.smith@acme.com"]
    assert email_patterns.best_match_by_domain(cands, "https://www.acme.com") == "john.smith@acme.com"


def test_best_match_by_domain_none():
    assert email_patterns.best_match_by_domain(["john@gmail.com"], "https://acme.com") is None


# ---------------------------------------------------------------------------
# WhatsApp / E.164 worldwide
# ---------------------------------------------------------------------------

def test_normalize_e164_usa():
    assert whatsapp_links.normalize_e164("(212) 555-0100", "US") == "+12125550100"


def test_normalize_e164_pakistan_trunk_zero():
    assert whatsapp_links.normalize_e164("0300 1234567", "PK") == "+923001234567"


def test_normalize_e164_uk():
    assert whatsapp_links.normalize_e164("020 7946 0000", "GB") == "+442079460000"


def test_normalize_e164_already_international():
    assert whatsapp_links.normalize_e164("+91 98765 43210", "IN") == "+919876543210"


def test_normalize_e164_rejects_junk():
    assert whatsapp_links.normalize_e164("123", "US") is None
    assert whatsapp_links.normalize_e164("", "US") is None


def test_wa_me_link():
    assert whatsapp_links.wa_me_link("0300 1234567", "PK") == "https://wa.me/923001234567"
    assert whatsapp_links.wa_me_link("123", "US") is None


def test_telegram_handle():
    assert whatsapp_links.telegram_link("@acme_support") == "https://t.me/acme_support"
    assert whatsapp_links.telegram_link("+44 20 7946 0000", "GB") == "https://t.me/442079460000"


# ---------------------------------------------------------------------------
# SMTP verifier (mocked session)
# ---------------------------------------------------------------------------

def test_rcpt_250_is_valid():
    import smtplib

    class FakeServer:
        def __init__(self, *a, **k):
            self.mail_to = None
            self.rcpt_to = None

        def connect(self, *a, **k):
            pass

        def ehlo(self, *a, **k):
            pass

        def mail(self, addr):
            self.mail_to = addr

        def rcpt(self, addr):
            self.rcpt_to = addr
            return (250, b"2.1.5 OK")

        def quit(self):
            pass

    orig = smtplib.SMTP
    smtplib.SMTP = lambda *a, **k: FakeServer()
    try:
        v = smtp_verify.SMTPVerifier()
        exists, catch = v._rcpt_response(None, "from@x.com", "to@x.com", 1.0)
    finally:
        smtplib.SMTP = orig
    assert exists is True
    assert catch is False


def test_rcpt_550_is_invalid():
    class FakeServer:
        def connect(self, *a, **k):
            pass

        def ehlo(self, *a, **k):
            pass

        def mail(self, addr):
            pass

        def rcpt(self, addr):
            return (550, b"5.1.1 No such user")

        def quit(self):
            pass

    v = smtp_verify.SMTPVerifier()
    exists, catch = v._rcpt_response(None, "from@x.com", "to@x.com", 1.0)
    assert exists is False


def test_catch_all_detection_probes_fake_local_part():
    import smtplib

    class FakeServer:
        def __init__(self, *a, **k):
            pass

        def connect(self, *a, **k):
            pass

        def ehlo(self, *a, **k):
            pass

        def mail(self, addr):
            pass

        def rcpt(self, addr):
            return (250, b"2.1.5 OK")

        def quit(self):
            pass

    v = smtp_verify.SMTPVerifier()
    v._mx_cache["acme.com"] = "mx.acme.com"
    orig = smtplib.SMTP
    smtplib.SMTP = lambda *a, **k: FakeServer()
    try:
        assert v._is_catch_all("mx.acme.com", "from@x.com", "acme.com") is True
    finally:
        smtplib.SMTP = orig


# ---------------------------------------------------------------------------
# Team contact extraction
# ---------------------------------------------------------------------------

def test_extract_people_with_on_page_email():
    html = """
    <h2>Team</h2>
    <p>John Smith | john.smith@acme.com | Sales</p>
    <p>Jane Doe runs operations.</p>
    """
    people = team_contacts.extract_people_from_html(html, "acme.com")
    emails = [p["email"] for p in people if p["email"]]
    assert "john.smith@acme.com" in emails
    names = {p["name"] for p in people}
    assert "Jane Doe" in names


def test_extract_people_requires_domain():
    assert team_contacts.extract_people_from_html("<p>John Smith</p>", "") == []


def test_enrich_people_prediction_without_verify():
    import asyncio

    # With verify=False, a named person gets the top predicted email.
    people = asyncio.run(
        team_contacts.enrich_people(
            ["<p>John Smith runs operations.</p>"], "acme.com", verify=False, max_people=2
        )
    )
    assert people
    assert people[0]["email"] == "john.smith@acme.com"
    assert people[0]["email_verified"] == "predicted"
