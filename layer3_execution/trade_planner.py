from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from config.settings import Settings
from contracts.domain import Direction
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.models import MarketQuote, PlannedTrade
from layer3_execution.sizing import calculate_position_size
from layer3_execution.stops import deterministic_stop
from layer3_execution.targets import deterministic_target, reward_risk


def _order_key(symbol: str, direction: Direction, decision_id: str) -> str:
    payload = f"{symbol}|{direction.value}|{decision_id}".encode()
    return hashlib.sha256(payload).hexdigest()[:32]


def plan_trade(
    *, direction: Direction, quote: MarketQuote, spec: BrokerSymbolSpec, equity: float,
    atr: float, structure_stop: float | None, structure_target: float | None,
    decision_id: str, settings: Settings, now_utc: datetime | None = None,
) -> PlannedTrade:
    if direction is Direction.HOLD:
        raise ValueError("HOLD cannot be planned for execution")
    if quote.symbol != spec.name:
        raise ValueError("quote/spec symbol mismatch")
    if quote.stale:
        raise ValueError("cannot plan from stale quote")
    entry = quote.ask if direction is Direction.BUY else quote.bid
    stop = deterministic_stop(
        direction=direction, entry=entry, atr=atr, structure_level=structure_stop,
        spec=spec, atr_multiplier=settings.atr_sl_multiplier,
    )
    target = deterministic_target(
        direction=direction, entry=entry, stop_loss=stop, atr=atr,
        structure_target=structure_target, spec=spec,
        atr_multiplier=settings.atr_tp_multiplier, min_rr=settings.min_rr,
    )
    rr = reward_risk(entry, stop, target)
    if rr + 1e-12 < settings.min_rr:
        raise ValueError(f"RR {rr:.4f} below MIN_RR {settings.min_rr:.4f}")
    sizing = calculate_position_size(
        equity=equity, risk_fraction=settings.risk_per_trade,
        entry=entry, stop_loss=stop, spec=spec,
    )
    return PlannedTrade(
        client_order_key=_order_key(spec.name, direction, decision_id),
        symbol=spec.name,
        direction=direction,
        planned_at_utc=now_utc or datetime.now(timezone.utc),
        entry=entry,
        stop_loss=stop,
        take_profit=target,
        rr=rr,
        sl_distance=abs(entry-stop),
        tp_distance=abs(target-entry),
        lot=sizing.normalized_lot,
        estimated_loss_at_sl=sizing.estimated_loss_at_sl,
        risk_fraction=sizing.estimated_risk_fraction,
    )
