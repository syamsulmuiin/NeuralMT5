from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Score = Annotated[float, Field(ge=0.0, le=1.0)]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Direction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class RiskDecision(StrEnum):
    ALLOWED = "ALLOWED"
    REJECTED = "REJECTED"


class SymbolResolution(FrozenModel):
    canonical_symbol: str
    broker_symbol: str | None
    resolution_confidence: Score
    reason: str
    ambiguous: bool = False

    @model_validator(mode="after")
    def ambiguous_has_no_broker_symbol(self):
        if self.ambiguous and self.broker_symbol is not None:
            raise ValueError("ambiguous resolution must not select a broker symbol")
        return self


class VersionStamp(FrozenModel):
    strategy_version: str
    feature_version: str
    network_version: str
    dataset_version: str
    scaler_version: str
    config_hash: str
    weights_hash: str
    dataset_hash: str
    random_seed: int


class MarketSnapshot(FrozenModel):
    canonical_symbol: str
    broker_symbol: str
    timestamp_utc: datetime
    htf: str
    mtf: str
    ltf: str
    bid: float
    ask: float
    spread_points: float
    data_quality_score: Score
    is_stale: bool
    is_complete: bool


class EvidenceScores(FrozenModel):
    htf_strength: Score
    mtf_quality: Score
    ltf_quality: Score
    structure_score: Score
    orderflow_score: Score
    regime_fitness: Score
    momentum_score: Score


class NeuralOutput(FrozenModel):
    buy_score: Score
    sell_score: Score
    hold_score: Score
    setup_quality: Score
    direction_confidence: Score
    expected_favorable_excursion: float
    expected_adverse_excursion: float

    @model_validator(mode="after")
    def probabilities_sum_to_one(self):
        total = self.buy_score + self.sell_score + self.hold_score
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"BUY/SELL/HOLD probabilities must sum to 1.0, got {total}")
        return self


class BrainflowResult(FrozenModel):
    direction: Direction
    brainflow_score: Score
    confidence: Score
    reason: str


class TradePlan(FrozenModel):
    symbol: str
    direction: Direction
    entry: float
    stop_loss: float
    take_profit: float
    rr: float = Field(gt=0.0)
    risk_fraction: float = Field(gt=0.0, le=1.0)
    lot: float = Field(gt=0.0)
    estimated_loss_at_sl: float = Field(ge=0.0)
    risk_quality: Score


class RiskResult(FrozenModel):
    decision: RiskDecision
    reason: str


class Opportunity(FrozenModel):
    timestamp_utc: datetime
    market: MarketSnapshot
    evidence: EvidenceScores
    neural: NeuralOutput
    brainflow: BrainflowResult
    trade_plan: TradePlan | None
    risk: RiskResult
    versions: VersionStamp
