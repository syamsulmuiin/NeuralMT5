from __future__ import annotations

from datetime import datetime

from layer1_market.models import Candle, DataQualityReport
from layer1_market.timeframes import timeframe_delta


def validate_candles(
    candles: tuple[Candle, ...],
    timeframe: str,
    *,
    decision_time_utc: datetime,
    minimum_history: int,
    max_missing_ratio: float,
) -> DataQualityReport:
    reasons: list[str] = []
    duplicate_count = 0
    malformed_count = 0

    if len(candles) < minimum_history:
        reasons.append(f"insufficient history: {len(candles)} < {minimum_history}")

    seen = set()
    for candle in candles:
        if candle.time_utc in seen:
            duplicate_count += 1
        seen.add(candle.time_utc)
        if candle.high < candle.low or candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
            malformed_count += 1
        if candle.time_utc > decision_time_utc:
            reasons.append("future candle detected")
            break

    if duplicate_count:
        reasons.append(f"duplicate candles: {duplicate_count}")
    if malformed_count:
        reasons.append(f"malformed candles: {malformed_count}")

    expected_step = timeframe_delta(timeframe)
    ordered = sorted({c.time_utc for c in candles})
    missing = 0
    expected_intervals = max(len(ordered) - 1, 0)
    for left, right in zip(ordered, ordered[1:]):
        gap_steps = int((right - left) / expected_step)
        if gap_steps > 1:
            missing += gap_steps - 1
    denominator = expected_intervals + missing
    missing_ratio = missing / denominator if denominator else 0.0
    if missing_ratio > max_missing_ratio:
        reasons.append(f"missing candle ratio {missing_ratio:.6f} exceeds {max_missing_ratio:.6f}")

    valid = not reasons
    penalties = min(1.0, 0.35 * bool(duplicate_count) + 0.50 * bool(malformed_count) + missing_ratio + 0.50 * (len(candles) < minimum_history))
    return DataQualityReport(
        valid=valid,
        quality_score=max(0.0, 1.0 - penalties),
        reasons=tuple(reasons),
        missing_ratio=missing_ratio,
        duplicate_count=duplicate_count,
        malformed_count=malformed_count,
    )


def is_tick_stale(tick_time_utc: datetime, now_utc: datetime, max_age_seconds: int) -> bool:
    age = (now_utc - tick_time_utc).total_seconds()
    return age < 0 or age > max_age_seconds
