from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from config.settings import Settings
from contracts.domain import Direction
from layer3_execution.models import PositionSnapshot


@dataclass(frozen=True)
class PositionMark:
    ticket: int
    current_price: float
    unrealized_pnl: float
    favorable_excursion: float
    adverse_excursion: float


def safety_issue(position: PositionSnapshot) -> str | None:
    if position.stop_loss is None or position.stop_loss <= 0:
        return "position has no valid stop loss"
    if position.direction is Direction.BUY:
        if position.stop_loss >= position.entry:
            return "BUY stop is not below entry"
        if position.take_profit is not None and position.take_profit <= position.entry:
            return "BUY target is not above entry"
    elif position.direction is Direction.SELL:
        if position.stop_loss <= position.entry:
            return "SELL stop is not above entry"
        if position.take_profit is not None and position.take_profit >= position.entry:
            return "SELL target is not below entry"
    return None


def mark_position(position: PositionSnapshot) -> PositionMark:
    delta = position.current_price - position.entry
    signed = delta if position.direction is Direction.BUY else -delta
    return PositionMark(
        ticket=position.ticket,
        current_price=position.current_price,
        unrealized_pnl=position.unrealized_pnl,
        favorable_excursion=max(signed, 0.0),
        adverse_excursion=max(-signed, 0.0),
    )


def force_flat_due(now_utc: datetime, settings: Settings) -> bool:
    hour, minute = (int(v) for v in settings.force_flat_time.split(":", 1))
    return now_utc.time().replace(tzinfo=None) >= time(hour, minute)


def snapshot_from_mt5(position: Any, tick: Any) -> PositionSnapshot:
    ptype = int(getattr(position, "type", 0))
    direction = Direction.BUY if ptype == 0 else Direction.SELL
    current = float(getattr(tick, "bid" if direction is Direction.BUY else "ask"))
    raw_time = int(getattr(position, "time", 0))
    return PositionSnapshot(
        ticket=int(getattr(position, "ticket")), symbol=str(getattr(position, "symbol")), direction=direction,
        volume=float(getattr(position, "volume")), entry=float(getattr(position, "price_open")),
        stop_loss=float(getattr(position, "sl", 0.0)) or None, take_profit=float(getattr(position, "tp", 0.0)) or None,
        current_price=current, unrealized_pnl=float(getattr(position, "profit", 0.0)),
        opened_at_utc=datetime.fromtimestamp(raw_time, tz=__import__('datetime').UTC),
    )
