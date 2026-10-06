from __future__ import annotations

import math
from statistics import mean, pstdev

from layer1_market.models import Candle, FeatureRow

FEATURE_VERSION = "phase1.v1"


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if abs(denominator) > 1e-12 else 0.0


def _atr(candles: tuple[Candle, ...], period: int) -> float:
    sample = candles[-period:]
    if not sample:
        return 0.0
    trs: list[float] = []
    prev_close = None
    for c in sample:
        tr = c.high - c.low
        if prev_close is not None:
            tr = max(tr, abs(c.high - prev_close), abs(c.low - prev_close))
        trs.append(tr)
        prev_close = c.close
    return mean(trs)


def build_feature_rows(
    candles: tuple[Candle, ...],
    timeframe: str,
    *,
    atr_period: int = 14,
    momentum_period: int = 10,
    volatility_period: int = 20,
) -> tuple[FeatureRow, ...]:
    warmup = max(atr_period, momentum_period, volatility_period)
    if len(candles) <= warmup:
        return ()
    rows: list[FeatureRow] = []
    for i in range(warmup, len(candles)):
        history = candles[: i + 1]
        c = history[-1]
        prev = history[-2]
        ret = _safe_ratio(c.close - prev.close, prev.close)
        log_ret = math.log(c.close / prev.close) if c.close > 0 and prev.close > 0 else 0.0
        rng = c.high - c.low
        body = abs(c.close - c.open)
        upper_wick = c.high - max(c.open, c.close)
        lower_wick = min(c.open, c.close) - c.low
        atr = _atr(history, atr_period)
        past_close = history[-1 - momentum_period].close
        momentum = _safe_ratio(c.close - past_close, past_close)
        returns = []
        vol_sample = history[-(volatility_period + 1):]
        for a, b in zip(vol_sample, vol_sample[1:]):
            returns.append(_safe_ratio(b.close - a.close, a.close))
        realized_vol = pstdev(returns) if len(returns) > 1 else 0.0
        avg_tick_volume = mean(x.tick_volume for x in history[-volatility_period:])
        tick_volume_ratio = _safe_ratio(c.tick_volume, avg_tick_volume)
        avg_spread = mean(x.spread_points for x in history[-volatility_period:])
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
