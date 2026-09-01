"""Safe parsing for the HTTP Retry-After response field."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def parse_retry_after(
    value: str | None,
    *,
    now: datetime | None = None,
) -> float | None:
    """Return a non-negative server delay for a valid delta or HTTP date."""
    if value is None:
        return None

    candidate = value.strip()
    if candidate.isascii() and candidate.isdigit():
        normalized_candidate = candidate.lstrip("0") or "0"
        if len(normalized_candidate) > 20:
            return None
        try:
            return float(int(normalized_candidate))
        except OverflowError, ValueError:
            return None

    try:
        retry_at = parsedate_to_datetime(candidate)
    except TypeError, ValueError, OverflowError:
        return None
    if retry_at.tzinfo is None:
        return None

    reference = now if now is not None else datetime.now(UTC)
    if reference.tzinfo is None:
        raise ValueError("Retry-After reference time must include a timezone")
    delay = (retry_at.astimezone(UTC) - reference.astimezone(UTC)).total_seconds()
    return max(0.0, delay)
