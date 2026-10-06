from __future__ import annotations

from datetime import timedelta

TIMEFRAME_MINUTES: dict[str, int] = {
    "M1": 1, "M2": 2, "M3": 3, "M4": 4, "M5": 5, "M6": 6,
    "M10": 10, "M12": 12, "M15": 15, "M20": 20, "M30": 30,
    "H1": 60, "H2": 120, "H3": 180, "H4": 240, "H6": 360,
    "H8": 480, "H12": 720, "D1": 1440,
}


def timeframe_delta(timeframe: str) -> timedelta:
    try:
        return timedelta(minutes=TIMEFRAME_MINUTES[timeframe.upper()])
    except KeyError as exc:
        raise ValueError(f"Unsupported timeframe: {timeframe}") from exc


def native_timeframe(backend: object, timeframe: str) -> int:
    name = f"TIMEFRAME_{timeframe.upper()}"
    value = getattr(backend, name, None)
    if value is None:
        raise ValueError(f"MT5 backend does not expose {name}")
    return int(value)
