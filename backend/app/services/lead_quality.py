"""Completeness/quality scoring for discovered or stored leads.

Lets the UI rank "how complete is this lead's data" instead of silently showing
a bare name. Kept plan-agnostic so both partial and full leads render with an
honest quality number.
"""


def data_quality(fields: dict) -> int:
    """0-100 completeness score. `fields` may carry name/address/phone/email/
    website and a social_links value (dict or list)."""
    score = 0

    def _has(key: str) -> bool:
        value = fields.get(key)
        if value is None:
            return False
        if isinstance(value, (dict, list)):
            return bool(value)
        return bool(str(value).strip())

    if _has("name"):
        score += 10
    if _has("address"):
        score += 15
    if _has("phone"):
        score += 20
    if _has("email"):
        score += 25
    if _has("website"):
        score += 20
    if _has("social_links"):
        score += 10
    return score
