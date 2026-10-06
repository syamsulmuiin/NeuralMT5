from __future__ import annotations

from statistics import mean

from layer1_market.models import Candle, OrderflowProxy


def build_orderflow_proxy(candles: tuple[Candle, ...], *, lookback: int = 20) -> OrderflowProxy:
    """Derived proxy only. It never claims centralized exchange orderflow."""
    if len(candles) < lookback:
        raise ValueError("insufficient candles for orderflow proxy")
    sample = candles[-lookback:]
    avg_volume = max(mean(c.tick_volume for c in sample[:-1]), 1e-12)
    avg_spread = max(mean(c.spread_points for c in sample[:-1]), 1e-12)
    last = sample[-1]

    tick_activity = min(1.0, last.tick_volume / avg_volume / 2.0)
    spread_quality = max(0.0, min(1.0, 1.0 - (last.spread_points / avg_spread - 1.0) / 2.0))

    signed_moves = []
    weights = []
    for c in sample:
        rng = max(c.high - c.low, 1e-12)
        signed = (c.close - c.open) / rng
        signed_moves.append(max(-1.0, min(1.0, signed)))
        weights.append(max(c.tick_volume, 1.0))
    pressure = sum(v * w for v, w in zip(signed_moves, weights)) / sum(weights)
    pressure = max(-1.0, min(1.0, pressure))
    score = 0.40 * abs(pressure) + 0.35 * tick_activity + 0.25 * spread_quality

    return OrderflowProxy(
        timestamp_utc=last.time_utc,
        orderflow_score=max(0.0, min(1.0, score)),
        directional_pressure=pressure,
        tick_activity_score=tick_activity,
        spread_quality=spread_quality,
    )
