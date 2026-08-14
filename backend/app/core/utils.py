from datetime import datetime, timezone


def as_utc(dt: datetime) -> datetime:
    """Return a naive datetime with UTC tzinfo attached, or a tz-aware one unchanged."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)