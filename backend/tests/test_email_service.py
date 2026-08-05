import json

import pytest
import respx
from httpx import Response

from app.core.config import settings
from app.services import email_service


async def test_send_email_posts_to_brevo(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "fake-key")
    monkeypatch.setattr(settings, "brevo_sender_email", "test@crawlio.io")
    monkeypatch.setattr(settings, "brevo_sender_name", "Crawlio Test")

    with respx.mock:
        route = respx.post("https://api.brevo.com/v3/smtp/email").mock(
            return_value=Response(201, json={"messageId": "msg_123"})
        )
        result = await email_service.send_email("lead@example.com", "Hi", "<p>Hi</p>")

    assert result == {"messageId": "msg_123"}
    request = route.calls[0].request
    assert request.headers["api-key"] == "fake-key"
    payload = json.loads(request.content)
    assert payload["to"] == [{"email": "lead@example.com"}]
    assert payload["sender"] == {"email": "test@crawlio.io", "name": "Crawlio Test"}


async def test_send_email_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "")
    with pytest.raises(RuntimeError):
        await email_service.send_email("lead@example.com", "Hi", "<p>Hi</p>")


def test_welcome_email_html_includes_name_and_workspace():
    html = email_service.welcome_email_html("Amara", "Acme Co")
    assert "Amara" in html
    assert "Acme Co" in html
