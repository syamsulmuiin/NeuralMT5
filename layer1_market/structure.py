from __future__ import annotations

from layer1_market.models import Candle, StructureState


def analyze_structure(candles: tuple[Candle, ...], *, pivot_left: int = 2, pivot_right: int = 2) -> StructureState:
    if len(candles) < pivot_left + pivot_right + 3:
        raise ValueError("insufficient candles for confirmed structure")

    confirmed_highs: list[tuple[int, float]] = []
    confirmed_lows: list[tuple[int, float]] = []
    # A pivot at i is only visible once pivot_right future bars relative to i have CLOSED.
    # The latest decision candle is never used to confirm a pivot that requires future bars.
    for i in range(pivot_left, len(candles) - pivot_right):
        left = candles[i - pivot_left:i]
        right = candles[i + 1:i + 1 + pivot_right]
        c = candles[i]
        if all(c.high > x.high for x in (*left, *right)):
            confirmed_highs.append((i, c.high))
        if all(c.low < x.low for x in (*left, *right)):
            confirmed_lows.append((i, c.low))

    last_high = confirmed_highs[-1][1] if confirmed_highs else None
    last_low = confirmed_lows[-1][1] if confirmed_lows else None
    current = candles[-1]
    bos_up = last_high is not None and current.close > last_high
    bos_down = last_low is not None and current.close < last_low

    trend = 0.0
    if len(confirmed_highs) >= 2 and len(confirmed_lows) >= 2:
        higher_high = confirmed_highs[-1][1] > confirmed_highs[-2][1]
        higher_low = confirmed_lows[-1][1] > confirmed_lows[-2][1]
        lower_high = confirmed_highs[-1][1] < confirmed_highs[-2][1]
        lower_low = confirmed_lows[-1][1] < confirmed_lows[-2][1]
        if higher_high and higher_low:
            trend = 1.0
        elif lower_high and lower_low:
            trend = -1.0

    evidence = int(last_high is not None) + int(last_low is not None) + int(trend != 0.0) + int(bos_up or bos_down)
    score = evidence / 4.0
    return StructureState(
        timestamp_utc=current.time_utc,
        structure_score=score,
        trend_score=trend,
        last_swing_high=last_high,
        last_swing_low=last_low,
        bos_up=bos_up,
        bos_down=bos_down,
    )
