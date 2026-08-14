"""Admin-facing integration registry.

Each entry maps a settings attribute (e.g. ``brevo_api_key``) to a human
label, its .env variable name, and a connectivity test. The admin panel lists
these with masked values, can set/clear a runtime override (persisted in
``system_settings`` under the ``integration.<name>`` key and hydrated into
:mod:`app.core.integration_runtime`), and can run the live test.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import httpx

from app.core import integration_runtime
from app.core.config import settings
from app.db.session import async_session_maker
from app.services.admin import system_setting_service

OVERRIDE_PREFIX = "integration."

MASK_CHARS = 8


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= MASK_CHARS:
        return "••••••••"
    return f"{value[:MASK_CHARS]}••••"


def _is_set(value: str) -> bool:
    return bool(value and value.strip())


async def _test_brevo(api_key: str) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.brevo.com/v3/account",
                headers={"api-key": api_key, "Accept": "application/json"},
            )
        if resp.status_code == 200:
            return True, "Connected to Brevo API (account reachable)."
        return False, f"Brevo API returned HTTP {resp.status_code}."
    except httpx.HTTPError as exc:
        return False, f"Request failed: {exc}"


async def _test_mistral(api_key: str) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
        if resp.status_code == 200:
            return True, "Connected to Mistral API (models list reachable)."
        return False, f"Mistral API returned HTTP {resp.status_code}."
    except httpx.HTTPError as exc:
        return False, f"Request failed: {exc}"


async def _test_tavily(api_key: str) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": "test", "search_depth": "basic", "max_results": 1},
            )
        if resp.status_code == 200:
            return True, "Connected to Tavily API (search works)."
        return False, f"Tavily API returned HTTP {resp.status_code}."
    except httpx.HTTPError as exc:
        return False, f"Request failed: {exc}"


@dataclass(frozen=True)
class Integration:
    key: str  # settings attribute name
    label: str
    description: str
    env_name: str
    secret: bool = True
    test: Optional[Callable[[str], Awaitable[tuple[bool, str]]]] = None


INTEGRATIONS: list[Integration] = [
    Integration(
        key="brevo_api_key",
        label="Brevo (email)",
        description="Transactional email sending — welcome, invite, outreach, agent.",
        env_name="BREVO_API_KEY",
        test=_test_brevo,
    ),
    Integration(
        key="mistral_api_key",
        label="Mistral AI",
        description="LLM used for lead scoring, AI email drafting and RAG agent.",
        env_name="MISTRAL_API_KEY",
        test=_test_mistral,
    ),
    Integration(
        key="tavily_api_key",
        label="Tavily (web search)",
        description="Opt-in last-resort discovery top-up source.",
        env_name="TAVILY_API_KEY",
        test=_test_tavily,
    ),
    Integration(
        key="google_client_id",
        label="Google OAuth client ID",
        description="Used to connect Gmail email accounts.",
        env_name="GOOGLE_CLIENT_ID",
        secret=True,
        test=None,
    ),
    Integration(
        key="google_client_secret",
        label="Google OAuth client secret",
        description="Used to connect Gmail email accounts.",
        env_name="GOOGLE_CLIENT_SECRET",
        secret=True,
        test=None,
    ),
    Integration(
        key="google_redirect_uri",
        label="Google OAuth redirect URI",
        description="Callback URL registered in the Google Cloud console.",
        env_name="GOOGLE_REDIRECT_URI",
        secret=False,
        test=None,
    ),
    Integration(
        key="proxy_url",
        label="Crawler proxy",
        description="Optional proxy for Google Maps / enrichment crawlers (anti-bot).",
        env_name="PROXY_URL",
        secret=True,
        test=None,
    ),
]


def get_integration(key: str) -> Optional[Integration]:
    for item in INTEGRATIONS:
        if item.key == key:
            return item
    return None


def _env_value(item: Integration) -> str:
    return getattr(settings, item.key, "") or ""


async def _override_value(session, key: str) -> str:
    setting = await system_setting_service.get_setting(session, f"{OVERRIDE_PREFIX}{key}")
    if setting is None or not setting.value:
        return ""
    return str(setting.value)


def _effective_value(env_value: str, override: str) -> str:
    return override if override else env_value


async def list_integrations(session) -> list[dict]:
    rows = []
    for item in INTEGRATIONS:
        override = await _override_value(session, item.key)
        env_value = _env_value(item)
        effective = _effective_value(env_value, override)
        source = "override" if override else ("env" if env_value else "unset")
        rows.append(
            {
                "key": item.key,
                "label": item.label,
                "description": item.description,
                "env_name": item.env_name,
                "configured": _is_set(effective),
                "source": source,
                "masked_value": mask(effective) if effective and item.secret else (effective or "—"),
            }
        )
    return rows


async def set_override(session, *, key: str, value: str, updated_by: str) -> dict:
    item = get_integration(key)
    if item is None:
        raise ValueError(f"Unknown integration: {key}")

    if not value.strip():
        raise ValueError("Value cannot be empty — use the clear action instead.")

    await system_setting_service.upsert_setting(
        session,
        key=f"{OVERRIDE_PREFIX}{key}",
        value=value.strip(),
        value_type="string",
        description=f"Admin runtime override for {item.label}",
        updated_by=updated_by,
    )
    integration_runtime.set_override(key, value.strip())

    env_value = _env_value(item)
    return {
        "key": item.key,
        "label": item.label,
        "description": item.description,
        "env_name": item.env_name,
        "configured": True,
        "source": "override",
        "masked_value": mask(value.strip()) if item.secret else (value.strip() or "—"),
    }


async def clear_override(session, *, key: str, updated_by: str) -> dict:
    item = get_integration(key)
    if item is None:
        raise ValueError(f"Unknown integration: {key}")

    setting = await system_setting_service.get_setting(session, f"{OVERRIDE_PREFIX}{key}")
    if setting is not None:
        await system_setting_service.delete_setting(session, f"{OVERRIDE_PREFIX}{key}")
    integration_runtime.clear_override(key)

    env_value = _env_value(item)
    effective = _effective_value(env_value, "")
    return {
        "key": item.key,
        "label": item.label,
        "description": item.description,
        "env_name": item.env_name,
        "configured": _is_set(effective),
        "source": "env" if env_value else "unset",
        "masked_value": mask(effective) if item.secret else (effective or "—"),
    }


async def run_test(key: str) -> dict:
    item = get_integration(key)
    if item is None:
        return {"ok": False, "message": f"Unknown integration: {key}"}

    effective = integration_runtime.api_key(key)
    if not _is_set(effective):
        return {"ok": False, "message": "Not configured — set a key or an override first."}

    if item.test is None:
        return {"ok": True, "message": "Configured (no live connectivity check available)."}

    ok, message = await item.test(effective)
    return {"ok": ok, "message": message}


async def hydrate_runtime_from_db() -> None:
    """Load all ``integration.*`` overrides from system_settings into the
    in-process runtime cache. Called at API startup and Celery worker init."""
    try:
        async with async_session_maker() as session:
            settings_rows = await system_setting_service.list_settings(session)
        overrides = {
            setting.key[len(OVERRIDE_PREFIX):]: str(setting.value)
            for setting in settings_rows
            if setting.key.startswith(OVERRIDE_PREFIX) and setting.value
        }
    except Exception as exc:  # pragma: no cover - startup should not crash
        import logging

        logging.getLogger(__name__).warning("Could not hydrate integration overrides: %s", exc)
        return
    integration_runtime.hydrate(overrides)
