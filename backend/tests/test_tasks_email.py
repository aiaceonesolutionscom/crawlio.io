import respx
from httpx import Response

from app.core.config import settings
from app.workers.tasks_email import _send_welcome_email_async


async def test_send_welcome_email_skips_when_no_api_key(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "")
    await _send_welcome_email_async("lead@example.com", "Amara", "Acme")


async def test_send_welcome_email_sends_via_brevo(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "fake-key")

    with respx.mock:
        route = respx.post("https://api.brevo.com/v3/smtp/email").mock(
            return_value=Response(201, json={"messageId": "x"})
        )
        await _send_welcome_email_async("lead@example.com", "Amara", "Acme")

    assert route.called


async def test_send_welcome_email_swallows_send_failures(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "fake-key")

    with respx.mock:
        respx.post("https://api.brevo.com/v3/smtp/email").mock(return_value=Response(500))
        await _send_welcome_email_async("lead@example.com", "Amara", "Acme")
