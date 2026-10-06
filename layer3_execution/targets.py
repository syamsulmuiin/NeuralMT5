from __future__ import annotations

from contracts.domain import Direction
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.pricing import round_to_tick


def deterministic_target(
    *, direction: Direction, entry: float, stop_loss: float, atr: float,
    structure_target: float | None, spec: BrokerSymbolSpec,
    atr_multiplier: float, min_rr: float,
) -> float:
    if direction is Direction.HOLD:
        raise ValueError("HOLD cannot have a target")
    risk = abs(entry - stop_loss)
    if risk <= 0 or atr <= 0:
        raise ValueError("risk and ATR must be positive")
    required = risk * min_rr
    preferred = max(required, atr * atr_multiplier)
    if direction is Direction.BUY:
        candidate = entry + preferred
        constrained = structure_target is not None and structure_target > entry and structure_target < candidate
        if constrained:
            candidate = structure_target
        # Unconstrained targets round outward so broker tick normalization cannot
        # silently reduce RR below MIN_RR. A structure-capped target rounds inward
        # and is later rejected by the RR gate if the reachable target is insufficient.
        target = round_to_tick(candidate, spec.tick_size, mode="down" if constrained else "up")
        if target <= entry:
            raise ValueError("BUY target must be above entry")
    else:
        candidate = entry - preferred
        constrained = structure_target is not None and 0 < structure_target < entry and structure_target > candidate
        if constrained:
            candidate = structure_target
        target = round_to_tick(candidate, spec.tick_size, mode="up" if constrained else "down")
        if target <= 0 or target >= entry:
            raise ValueError("SELL target must be below entry")
    return target


def reward_risk(entry: float, stop_loss: float, take_profit: float) -> float:
    risk = abs(entry - stop_loss)
    if risk <= 0:
        raise ValueError("stop distance must be positive")
    return abs(take_profit - entry) / risk
