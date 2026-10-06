from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR

from layer1_market.models import BrokerSymbolSpec
from layer3_execution.models import PositionSizing


def _floor_to_step(value: float, step: float) -> float:
    v, s = Decimal(str(value)), Decimal(str(step))
    return float((v / s).to_integral_value(rounding=ROUND_FLOOR) * s)


def calculate_position_size(
    *, equity: float, risk_fraction: float, entry: float, stop_loss: float,
    spec: BrokerSymbolSpec,
) -> PositionSizing:
    if equity <= 0:
        raise ValueError("equity must be positive")
    if not 0 < risk_fraction <= 1:
        raise ValueError("risk_fraction must be in (0,1]")
    distance = abs(entry - stop_loss)
    if distance <= 0:
        raise ValueError("SL distance must be positive")
    if spec.tick_value <= 0 or spec.tick_size <= 0:
        raise ValueError("broker tick_size/tick_value must be positive for sizing")

    ticks = distance / spec.tick_size
    loss_per_lot = ticks * spec.tick_value
    risk_amount = equity * risk_fraction
    raw_lot = risk_amount / loss_per_lot
    lot = _floor_to_step(min(raw_lot, spec.volume_max), spec.volume_step)

    if lot < spec.volume_min:
        minimum_loss = loss_per_lot * spec.volume_min
        if minimum_loss > risk_amount + 1e-9:
            raise ValueError("broker minimum volume exceeds requested risk budget")
        lot = spec.volume_min
    lot = min(max(lot, spec.volume_min), spec.volume_max)
    actual_loss = loss_per_lot * lot
    actual_fraction = actual_loss / equity
    if actual_fraction > risk_fraction + 1e-9:
        raise ValueError("normalized volume exceeds requested risk budget")
    return PositionSizing(
        requested_risk_amount=risk_amount,
        loss_per_lot_at_sl=loss_per_lot,
        raw_lot=raw_lot,
        normalized_lot=lot,
        estimated_loss_at_sl=actual_loss,
        estimated_risk_fraction=actual_fraction,
    )
