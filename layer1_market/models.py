from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Score = Annotated[float, Field(ge=0.0, le=1.0)]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DataSource(StrEnum):
    REAL_MARKET_DATA = "REAL_MARKET_DATA"
    DERIVED_PROXY = "DERIVED_PROXY"


class Candle(FrozenModel):
    time_utc: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: float = Field(ge=0.0)
    spread_points: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_ohlc(self):
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open/close/low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open/close/high")
        return self


class BrokerSymbolSpec(FrozenModel):
    name: str
    description: str = ""
    path: str = ""
    currency_base: str = ""
    currency_profit: str = ""
    currency_margin: str = ""
    digits: int = Field(ge=0)
    point: float = Field(gt=0.0)
    tick_size: float = Field(gt=0.0)
    tick_value: float = Field(ge=0.0)
    contract_size: float = Field(gt=0.0)
    volume_min: float = Field(gt=0.0)
    volume_max: float = Field(gt=0.0)
    volume_step: float = Field(gt=0.0)
    stops_level: int = Field(ge=0)
    freeze_level: int = Field(ge=0)
    trade_mode: int
    filling_mode: int
    execution_mode: int
    spread_points: float = Field(ge=0.0)
    visible: bool = True
    custom: bool = False


class AccountSnapshot(FrozenModel):
    login: int
    server: str
    currency: str
    balance: float
    equity: float
    margin: float
    margin_free: float


class DataQualityReport(FrozenModel):
    valid: bool
    quality_score: Score
    reasons: tuple[str, ...] = ()
    missing_ratio: float = Field(ge=0.0, le=1.0)
    duplicate_count: int = Field(ge=0)
    malformed_count: int = Field(ge=0)


class FeatureRow(FrozenModel):
    timestamp_utc: datetime
    timeframe: str
    feature_version: str
    values: dict[str, float]


class StructureState(FrozenModel):
    timestamp_utc: datetime
    structure_score: Score
    trend_score: float = Field(ge=-1.0, le=1.0)
    last_swing_high: float | None = None
    last_swing_low: float | None = None
    bos_up: bool = False
    bos_down: bool = False
    source: DataSource = DataSource.DERIVED_PROXY


class RegimeState(FrozenModel):
    timestamp_utc: datetime
    regime: str
    regime_fitness: Score
    volatility_score: Score
    trend_strength: Score
    source: DataSource = DataSource.DERIVED_PROXY


class OrderflowProxy(FrozenModel):
    timestamp_utc: datetime
    orderflow_score: Score
    directional_pressure: float = Field(ge=-1.0, le=1.0)
    tick_activity_score: Score
    spread_quality: Score
    source: DataSource = DataSource.DERIVED_PROXY


class TimeframeSequence(FrozenModel):
    timeframe: str
    decision_time_utc: datetime
    rows: tuple[FeatureRow, ...]


class MultiTimeframeSequences(FrozenModel):
    decision_time_utc: datetime
    htf: TimeframeSequence
    mtf: TimeframeSequence
    ltf: TimeframeSequence
