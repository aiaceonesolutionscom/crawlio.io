import respx
from httpx import Response

from app.core.config import settings
from app.services import listing_extraction_service


async def test_extract_businesses_parses_response(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "fake-key-for-test")

    mock_content = {
        "businesses": [
            {"name": "Kolachi Restaurant", "phone": "+92 21 111 111 001", "email": None,
             "website": None, "address": "DHA Phase 8, Karachi"},
            {"name": "Sakura", "phone": None, "email": None, "website": "https://sakura.pk", "address": None},
        ]
    }
    mock_response = {"choices": [{"message": {"content": __import__("json").dumps(mock_content)}}]}

    with respx.mock:
        respx.post("https://api.mistral.ai/v1/chat/completions").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await listing_extraction_service.extract_businesses(
            "restaurants", "Karachi", "some directory page content " * 50
        )

    assert len(result) == 2
    assert result[0]["name"] == "Kolachi Restaurant"
    assert result[0]["phone"] == "+92 21 111 111 001"
    assert result[1]["website"] == "https://sakura.pk"


async def test_extract_businesses_drops_entries_without_a_name(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "fake-key-for-test")

    mock_content = {"businesses": [{"name": "", "phone": "123"}, {"name": "Real Place"}]}
    mock_response = {"choices": [{"message": {"content": __import__("json").dumps(mock_content)}}]}

    with respx.mock:
        respx.post("https://api.mistral.ai/v1/chat/completions").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await listing_extraction_service.extract_businesses(
            "restaurants", "Karachi", "some directory page content " * 50
        )

    assert len(result) == 1
    assert result[0]["name"] == "Real Place"


async def test_extract_businesses_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "")
    result = await listing_extraction_service.extract_businesses(
        "restaurants", "Karachi", "some directory page content " * 50
    )
    assert result == []


async def test_extract_businesses_skips_too_short_content(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "fake-key-for-test")
    result = await listing_extraction_service.extract_businesses("restaurants", "Karachi", "too short")
    assert result == []


async def test_extract_businesses_handles_malformed_json_gracefully(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "fake-key-for-test")

    mock_response = {"choices": [{"message": {"content": "not valid json"}}]}

    with respx.mock:
        respx.post("https://api.mistral.ai/v1/chat/completions").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await listing_extraction_service.extract_businesses(
            "restaurants", "Karachi", "some directory page content " * 50
        )

    assert result == []
