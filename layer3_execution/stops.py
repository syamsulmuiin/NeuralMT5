from __future__ import annotations

from contracts.domain import Direction
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.pricing import round_to_tick


def deterministic_stop(
    *, direction: Direction, entry: float, atr: float, structure_level: float | None,
    spec: BrokerSymbolSpec, atr_multiplier: float,
) -> float:
    if direction is Direction.HOLD:
        raise ValueError("HOLD cannot have a stop")
    if atr <= 0:
        raise ValueError("ATR must be positive")
    broker_min = spec.stops_level * spec.point
    noise = atr * atr_multiplier
    min_distance = max(broker_min, noise, spec.tick_size)

    if direction is Direction.BUY:
        candidate = entry - min_distance
        if structure_level is not None and 0 < structure_level < entry:
            candidate = min(candidate, structure_level - spec.tick_size)
        stop = round_to_tick(candidate, spec.tick_size, mode="down")
        if stop >= entry:
            raise ValueError("BUY stop must be below entry")
    else:
        candidate = entry + min_distance
        if structure_level is not None and structure_level > entry:
            candidate = max(candidate, structure_level + spec.tick_size)
        stop = round_to_tick(candidate, spec.tick_size, mode="up")
        if stop <= entry:
            raise ValueError("SELL stop must be above entry")
    if stop <= 0:
        raise ValueError("computed stop is invalid")
    return stop
