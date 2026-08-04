import json
from typing import Optional

import httpx

from app.core.config import settings

SCORING_PROMPT = (
    "You are a B2B lead qualification assistant. Given a lead's name, company, email, and "
    "source, return a JSON object with exactly two fields: \"score\" (integer 0-100, how "
    "likely this lead is to convert) and \"status\" (one of \"New\", \"Qualified\", "
    "\"Contacted\", \"Nurturing\", \"Won\", \"Lost\" -- pick \"Qualified\" if score >= 70, "
    "otherwise \"New\"). Respond with ONLY the JSON object, no other text."
)


async def score_lead(name: str, company: Optional[str], email: Optional[str], source: Optional[str]) -> dict:
    if not settings.mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured")

    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": SCORING_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Name: {name}\nCompany: {company or 'unknown'}\n"
                    f"Email: {email or 'unknown'}\nSource: {source or 'unknown'}"
                )
            }],

        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.mistral_api_key}", "Content-Type": "application/json"},
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    result = json.loads(content)
    score = max(0, min(100, int(result["score"])))
    status_label = result.get("status") or ("Qualified" if score >= 70 else "New")
    return {"score": score, "status": status_label}
