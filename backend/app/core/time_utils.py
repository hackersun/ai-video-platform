"""Time helpers used by persistence and API code."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return a UTC timestamp compatible with existing naive DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)
