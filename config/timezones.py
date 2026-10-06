from __future__ import annotations

from datetime import timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_UTC_ALIASES = {"UTC", "ETC/UTC", "GMT", "ETC/GMT", "Z"}


def resolve_timezone(name: str) -> tzinfo:
    """Resolve a configured timezone without requiring tzdata for UTC.

    Windows does not ship the IANA timezone database used by zoneinfo. UTC can
    be represented directly by the stdlib, while non-UTC IANA zones are
    resolved through ZoneInfo (backed by the tzdata package on Windows).
    """
    normalized = name.strip()
    if normalized.upper() in _UTC_ALIASES:
        return timezone.utc
    try:
        return ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"invalid timezone: {name}") from exc
