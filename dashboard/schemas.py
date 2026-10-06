from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DashboardModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RuntimeMode(StrEnum):
    ANALYSIS = "analysis"
    PAPER = "paper"
    LIVE = "live"


class CommandType(StrEnum):
    PAUSE_NEW_ENTRY = "PAUSE_NEW_ENTRY"
    RESUME_NEW_ENTRY = "RESUME_NEW_ENTRY"
    EMERGENCY_STOP_NEW_ENTRY = "EMERGENCY_STOP_NEW_ENTRY"
    SET_MODE = "SET_MODE"
    PROMOTE_MODEL = "PROMOTE_MODEL"


class RuntimeStatus(DashboardModel):
    mode: RuntimeMode
    new_entries_paused: bool
    emergency_stop: bool
    reconciliation_ok: bool
    last_event_at_utc: datetime | None = None
    last_error: str | None = None


class CommandRequest(DashboardModel):
    command: CommandType
    mode: RuntimeMode | None = None
    artifact_id: str | None = None
    explicit_confirmation: bool = False
    actor: str = Field(default="dashboard", min_length=1, max_length=128)


class CommandReceipt(DashboardModel):
    command_id: str
    accepted: bool
    reason: str
    created_at_utc: datetime


class PaginatedResult(DashboardModel):
    items: list[dict[str, Any]]
    limit: int
    offset: int
    total: int


class SystemInfo(DashboardModel):
    dashboard_version: str
    api_version: str
    database_available: bool
    config: dict[str, Any]
    warnings: list[str]
