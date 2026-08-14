import pytest
import respx
from httpx import Response

from app.core.config import settings
from app.services.lead import scoring_service


async def test_score_lead_parses_response(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "fake-key-for-test")

    mock_response = {"choices": [{"message": {"content": '{"score": 85, "status": "Qualified"}'}}]}

    with respx.mock:
        respx.post("https://api.mistral.ai/v1/chat/completions").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await scoring_service.score_lead("Amara Okafor", "Northwind", "amara@northwind.co", "Webinar")

    assert result == {"score": 85, "status": "Qualified"}


async def test_score_lead_clamps_out_of_range_score(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "fake-key-for-test")

    mock_response = {"choices": [{"message": {"content": '{"score": 140, "status": "Qualified"}'}}]}

    with respx.mock:
        respx.post("https://api.mistral.ai/v1/chat/completions").mock(
            return_value=Response(200, json=mock_response)
        )
        result = await scoring_service.score_lead("Test", None, None, None)

    assert result["score"] == 100


async def test_score_lead_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "")
    with pytest.raises(RuntimeError):
        await scoring_service.score_lead("Test", None, None, None)
