from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

class ModelRole(StrEnum):
    CHAMPION='CHAMPION'; CHALLENGER='CHALLENGER'; RETIRED='RETIRED'

@dataclass(frozen=True)
class ObservationRecord:
    observation_id:str; symbol:str; observed_at_utc:datetime; features:dict[str,float]; feature_version:str; dataset_version:str

@dataclass(frozen=True)
class OutcomeLabel:
    direction:str; setup_quality:float; direction_confidence:float; mfe:float; mae:float; horizon_end_utc:datetime

@dataclass(frozen=True)
class PerformanceMetrics:
    trades:int; expectancy_r:float; profit_factor:float; max_drawdown:float; total_r:float; win_rate:float

@dataclass(frozen=True)
class ValidationReport:
    passed:bool; reasons:tuple[str,...]; challenger:PerformanceMetrics; champion:PerformanceMetrics|None
