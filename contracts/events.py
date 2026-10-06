from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    MARKET_UPDATE = "MARKET_UPDATE"
    ANALYSIS_COMPLETE = "ANALYSIS_COMPLETE"
    NEURAL_INFERENCE = "NEURAL_INFERENCE"
    OPPORTUNITY = "OPPORTUNITY"
    TRADE_REJECTED = "TRADE_REJECTED"
    ORDER_SENT = "ORDER_SENT"
    ORDER_FILLED = "ORDER_FILLED"
    POSITION_UPDATE = "POSITION_UPDATE"
    POSITION_CLOSED = "POSITION_CLOSED"
    RECONCILIATION_COMPLETE = "RECONCILIATION_COMPLETE"
    TRAINING_STARTED = "TRAINING_STARTED"
    TRAINING_PROGRESS = "TRAINING_PROGRESS"
    TRAINING_COMPLETED = "TRAINING_COMPLETED"
    CHALLENGER_READY = "CHALLENGER_READY"
    MODEL_PROMOTED = "MODEL_PROMOTED"
    DRIFT_WARNING = "DRIFT_WARNING"
    SYSTEM_WARNING = "SYSTEM_WARNING"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class SystemEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    occurred_at_utc: datetime
    source: str
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
