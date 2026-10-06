from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field

from contracts.domain import Direction


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExecutionState(StrEnum):
    PREFLIGHT_REJECTED = "PREFLIGHT_REJECTED"
    PAPER_FILLED = "PAPER_FILLED"
    SENT = "SENT"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    FAILED = "FAILED"


class MarketQuote(FrozenModel):
    symbol: str
    timestamp_utc: datetime
    bid: float = Field(gt=0.0)
    ask: float = Field(gt=0.0)
    spread_points: float = Field(ge=0.0)
    stale: bool = False


class RiskState(FrozenModel):
    equity: float = Field(gt=0.0)
    daily_realized_loss_fraction: float = Field(ge=0.0, le=1.0)
    daily_committed_risk_fraction: float = Field(ge=0.0, le=1.0)
    consecutive_losses: int = Field(ge=0)
    open_positions: int = Field(ge=0)
    total_exposure_fraction: float = Field(ge=0.0, le=1.0)
    correlated_exposure_fraction: float = Field(ge=0.0, le=1.0)


class PositionSizing(FrozenModel):
    requested_risk_amount: float = Field(gt=0.0)
    loss_per_lot_at_sl: float = Field(gt=0.0)
    raw_lot: float = Field(gt=0.0)
    normalized_lot: float = Field(gt=0.0)
    estimated_loss_at_sl: float = Field(gt=0.0)
    estimated_risk_fraction: float = Field(gt=0.0, le=1.0)


class PlannedTrade(FrozenModel):
    client_order_key: str
    symbol: str
    direction: Direction
    planned_at_utc: datetime
    entry: float = Field(gt=0.0)
    stop_loss: float = Field(gt=0.0)
    take_profit: float = Field(gt=0.0)
    rr: float = Field(gt=0.0)
    sl_distance: float = Field(gt=0.0)
    tp_distance: float = Field(gt=0.0)
    lot: float = Field(gt=0.0)
    estimated_loss_at_sl: float = Field(gt=0.0)
    risk_fraction: float = Field(gt=0.0, le=1.0)


class PreflightResult(FrozenModel):
    allowed: bool
    reasons: tuple[str, ...] = ()


class ExecutionResult(FrozenModel):
    state: ExecutionState
    client_order_key: str
    symbol: str
    order_ticket: int | None = None
    deal_ticket: int | None = None
    position_ticket: int | None = None
    actual_entry: float | None = None
    requested_volume: float | None = None
    filled_volume: float | None = None
    reason: str = ""


class PositionSnapshot(FrozenModel):
    ticket: int
    symbol: str
    direction: Direction
    volume: float = Field(gt=0.0)
    entry: float = Field(gt=0.0)
    stop_loss: float | None = None
    take_profit: float | None = None
    current_price: float = Field(gt=0.0)
    unrealized_pnl: float
    opened_at_utc: datetime
