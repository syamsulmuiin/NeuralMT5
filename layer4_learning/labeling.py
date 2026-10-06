from __future__ import annotations

from datetime import datetime

from .models import OutcomeLabel


def label_forward_path(
    *,
    entry: float,
    sl: float,
    tp: float,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    horizon_end_utc: datetime,
    direction_hint: str | None = None,
) -> OutcomeLabel:
    if not highs or len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("aligned non-empty forward path required")
    risk = abs(entry - sl)
    if risk <= 0:
        raise ValueError("invalid risk distance")

    is_buy = tp > entry > sl
    is_sell = tp < entry < sl
    if not (is_buy or is_sell):
        raise ValueError("entry/SL/TP geometry is invalid")

    up = max(0.0, max(highs) - entry)
    down = max(0.0, entry - min(lows))
    direction = "HOLD"

    if is_buy:
        first = next((i for i, (h, l) in enumerate(zip(highs, lows)) if h >= tp or l <= sl), None)
        if first is not None:
            h, l = highs[first], lows[first]
            direction = "HOLD" if h >= tp and l <= sl else ("BUY" if h >= tp else "HOLD")
        favorable, adverse = up / risk, down / risk
        signed_final = (closes[-1] - entry) / risk
    else:
        first = next((i for i, (h, l) in enumerate(zip(highs, lows)) if l <= tp or h >= sl), None)
        if first is not None:
            h, l = highs[first], lows[first]
            direction = "HOLD" if l <= tp and h >= sl else ("SELL" if l <= tp else "HOLD")
        favorable, adverse = down / risk, up / risk
        signed_final = (entry - closes[-1]) / risk

    quality = max(0.0, min(1.0, favorable / (favorable + adverse + 1e-12)))
    confidence = max(0.0, min(1.0, max(0.0, signed_final))) if direction != "HOLD" else max(0.0, min(1.0, 1.0 - min(1.0, favorable)))
    return OutcomeLabel(direction, quality, confidence, favorable, adverse, horizon_end_utc)
