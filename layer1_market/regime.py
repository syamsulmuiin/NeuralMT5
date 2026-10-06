from __future__ import annotations

from statistics import mean

from layer1_market.models import Candle, RegimeState


def detect_regime(candles: tuple[Candle, ...], *, lookback: int = 20) -> RegimeState:
    if len(candles) < lookback + 1:
        raise ValueError("insufficient candles for regime detection")
    sample = candles[-lookback:]
    ranges = [c.high - c.low for c in sample]
    avg_range = mean(ranges)
    price_scale = max(mean(c.close for c in sample), 1e-12)
    normalized_vol = min(1.0, avg_range / price_scale * 100.0)
    net_move = sample[-1].close - sample[0].open
    path = sum(abs(b.close - a.close) for a, b in zip(sample, sample[1:]))
    efficiency = min(1.0, abs(net_move) / path) if path > 0 else 0.0

    if normalized_vol >= 0.70 and efficiency < 0.25:
        regime = "CHAOTIC"
        fitness = 1.0 - efficiency
    elif normalized_vol >= 0.70:
        regime = "HIGH_VOLATILITY"
        fitness = normalized_vol
    elif efficiency >= 0.55 and net_move > 0:
        regime = "TREND_UP"
        fitness = efficiency
    elif efficiency >= 0.55 and net_move < 0:
        regime = "TREND_DOWN"
        fitness = efficiency
    elif normalized_vol <= 0.15:
        regime = "COMPRESSION"
        fitness = 1.0 - normalized_vol
    else:
        regime = "RANGE"
        fitness = max(0.0, 1.0 - efficiency)

    return RegimeState(
        timestamp_utc=sample[-1].time_utc,
        regime=regime,
        regime_fitness=min(max(fitness, 0.0), 1.0),
        volatility_score=normalized_vol,
        trend_strength=efficiency,
    )
