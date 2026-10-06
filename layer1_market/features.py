from __future__ import annotations

import math
from statistics import mean, pstdev

from layer1_market.models import Candle, FeatureRow

FEATURE_VERSION = "phase1.v2"


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if abs(denominator) > 1e-12 else 0.0


def _true_range(candles: tuple[Candle, ...], i: int) -> float:
    c = candles[i]
    tr = c.high - c.low
    if i > 0:
        prev_close = candles[i - 1].close
        tr = max(tr, abs(c.high - prev_close), abs(c.low - prev_close))
    return tr


def _atr_at(candles: tuple[Candle, ...], i: int, period: int) -> float:
    start = max(0, i - period + 1)
    return mean(_true_range(candles, j) for j in range(start, i + 1))


def build_feature_rows(
    candles: tuple[Candle, ...],
    timeframe: str,
    *,
    atr_period: int = 14,
    momentum_period: int = 10,
    volatility_period: int = 20,
) -> tuple[FeatureRow, ...]:
    """Build point-in-time features using bounded rolling windows.

    The implementation is O(n * max_period), not O(n²), and every feature at index i
    only reads candles <= i.
    """
    warmup = max(atr_period, momentum_period, volatility_period)
    if len(candles) <= warmup:
        return ()
    rows: list[FeatureRow] = []
    for i in range(warmup, len(candles)):
        c = candles[i]
        prev = candles[i - 1]
        ret = _safe_ratio(c.close - prev.close, prev.close)
        log_ret = math.log(c.close / prev.close) if c.close > 0 and prev.close > 0 else 0.0
        rng = c.high - c.low
        body = abs(c.close - c.open)
        upper_wick = c.high - max(c.open, c.close)
        lower_wick = min(c.open, c.close) - c.low
        atr = _atr_at(candles, i, atr_period)
        past_close = candles[i - momentum_period].close
        momentum = _safe_ratio(c.close - past_close, past_close)

        vol_start = max(1, i - volatility_period + 1)
        returns = [
            _safe_ratio(candles[j].close - candles[j - 1].close, candles[j - 1].close)
            for j in range(vol_start, i + 1)
        ]
        realized_vol = pstdev(returns) if len(returns) > 1 else 0.0
        window = candles[max(0, i - volatility_period + 1): i + 1]
        avg_tick_volume = mean(x.tick_volume for x in window)
        tick_volume_ratio = _safe_ratio(c.tick_volume, avg_tick_volume)
        avg_spread = mean(x.spread_points for x in window)
        spread_ratio = _safe_ratio(c.spread_points, avg_spread)

        rows.append(FeatureRow(
            timestamp_utc=c.time_utc,
            timeframe=timeframe.upper(),
            feature_version=FEATURE_VERSION,
            values={
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "return_1": ret,
                "log_return_1": log_ret,
                "range": rng,
                "body": body,
                "upper_wick": upper_wick,
                "lower_wick": lower_wick,
                "tick_volume": c.tick_volume,
                "spread_points": c.spread_points,
                "atr": atr,
                "momentum": momentum,
                "realized_volatility": realized_vol,
                "tick_volume_ratio": tick_volume_ratio,
                "spread_ratio": spread_ratio,
            },
        ))
    return tuple(rows)
