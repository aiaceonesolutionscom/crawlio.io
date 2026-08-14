"""Runtime API-key / integration overrides set from the admin panel.

Secrets (Brevo, Mistral, Tavily, Google OAuth, proxy, …) normally come from
.env at boot. The admin Integrations page can set a *runtime override* that is
persisted in the ``system_settings`` table (key prefix ``integration.``) and
hydrated into this in-process cache at startup (and on every admin change).

Every service reads its key through :func:`api_key` instead of touching
``settings`` directly, so a key changed from the panel takes effect with no
code change and no restart — in both the API process and the Celery worker
(each hydrates its own cache at startup / worker init).
"""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# name -> raw value, from system_settings overrides only (env is the fallback).
_OVERRIDES: dict[str, str] = {}


def hydrate(overrides: dict[str, str]) -> None:
    """Replace the override cache wholesale (used at startup + worker init)."""
    _OVERRIDES.clear()
    _OVERRIDES.update({k: v for k, v in overrides.items() if v is not None})
    if _OVERRIDES:
        logger.info("Hydrated %d runtime integration override(s)", len(_OVERRIDES))


def set_override(name: str, value: str) -> None:
    _OVERRIDES[name] = value


def clear_override(name: str) -> None:
    _OVERRIDES.pop(name, None)


def get_override(name: str) -> Optional[str]:
    return _OVERRIDES.get(name)


def api_key(name: str) -> str:
    """Effective value for a settings attribute: override first, env fallback."""
    if name in _OVERRIDES:
        return _OVERRIDES[name]
    return getattr(settings, name, "") or ""
