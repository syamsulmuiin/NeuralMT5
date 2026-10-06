from __future__ import annotations

from enum import StrEnum
import os
from typing import Annotated

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


SUPPORTED_TIMEFRAMES = frozenset(
    {"M1", "M2", "M3", "M4", "M5", "M6", "M10", "M12", "M15", "M20", "M30",
     "H1", "H2", "H3", "H4", "H6", "H8", "H12", "D1"}
)


class TradingMode(StrEnum):
    ANALYSIS = "analysis"
    PAPER = "paper"
    LIVE = "live"


def _csv_symbols(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip().upper() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip().upper() for item in value if str(item).strip()]
    raise TypeError("SYMBOLS must be a comma-separated string or a list")


SymbolList = Annotated[list[str], BeforeValidator(_csv_symbols)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    trading_mode: TradingMode = TradingMode.ANALYSIS
    mt5_login: str | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_path: str | None = None
    mt5_magic_number: int = Field(2601001, ge=1)
    mt5_order_comment: str = "NeuralMT5"

    symbols: SymbolList = ["XAUUSD", "EURUSD"]
    min_symbol_resolution_confidence: float = Field(0.90, ge=0.0, le=1.0)

    htf: str = "M15"
    mtf: str = "M5"
    ltf: str = "M1"
    htf_window: int = Field(200, ge=32)
    mtf_window: int = Field(200, ge=32)
    ltf_window: int = Field(200, ge=32)
    max_stale_tick_seconds: int = Field(5, ge=1)
    max_missing_candle_ratio: float = Field(0.01, ge=0.0, le=1.0)
    atr_period: int = Field(14, ge=2)
    momentum_period: int = Field(10, ge=1)
    volatility_period: int = Field(20, ge=2)
    structure_pivot_left: int = Field(2, ge=1)
    structure_pivot_right: int = Field(2, ge=1)
    regime_lookback: int = Field(20, ge=5)
    orderflow_lookback: int = Field(20, ge=5)

    network_type: str = "cnn_gru"
    hidden_size: int = Field(64, ge=4)
    dropout: float = Field(0.20, ge=0.0, lt=1.0)
    learning_rate: float = Field(0.001, gt=0.0)
    batch_size: int = Field(64, ge=1)
    epochs: int = Field(30, ge=1)
    random_seed: int = 42
    dataset_version: str = "dataset-v1"
    model_artifact_path: str = "storage/models/champion.pt"
    scaler_artifact_path: str = "storage/scalers/champion.json"

    runtime_loop_seconds: float = Field(1.0, gt=0.0)
    mt5_reconnect_attempts: int = Field(3, ge=1, le=100)
    mt5_reconnect_delay_seconds: float = Field(2.0, ge=0.0)
    live_execution_enabled: bool = False
    live_readiness_acknowledged: bool = False
    live_require_terminal_trade_allowed: bool = True
    live_require_account_trade_allowed: bool = True
    live_max_clock_skew_seconds: int = Field(30, ge=0)
    live_fault_injection_passed: bool = False
    live_soak_test_passed: bool = False

    w_htf: float = Field(0.14, ge=0.0, le=1.0)
    w_mtf: float = Field(0.14, ge=0.0, le=1.0)
    w_ltf: float = Field(0.14, ge=0.0, le=1.0)
    w_structure: float = Field(0.14, ge=0.0, le=1.0)
    w_orderflow: float = Field(0.10, ge=0.0, le=1.0)
    w_regime: float = Field(0.10, ge=0.0, le=1.0)
    w_momentum: float = Field(0.10, ge=0.0, le=1.0)
    w_neural: float = Field(0.14, ge=0.0, le=1.0)

    min_direction_score: float = Field(0.60, ge=0.0, le=1.0)
    min_direction_margin: float = Field(0.15, ge=0.0, le=1.0)
    min_brainflow_score: float = Field(0.65, ge=0.0, le=1.0)
    min_confidence: float = Field(0.60, ge=0.0, le=1.0)

    min_rr: float = Field(1.50, gt=0.0)
    atr_sl_multiplier: float = Field(1.20, gt=0.0)
    atr_tp_multiplier: float = Field(1.80, gt=0.0)

    risk_per_trade: float = Field(0.005, gt=0.0, le=1.0)
    max_daily_risk: float = Field(0.020, gt=0.0, le=1.0)
    max_daily_loss: float = Field(0.020, gt=0.0, le=1.0)
    max_consecutive_losses: int = Field(4, ge=1)
    max_open_positions: int = Field(3, ge=1)
    max_total_exposure: float = Field(0.030, gt=0.0, le=1.0)
    max_correlated_exposure: float = Field(0.015, gt=0.0, le=1.0)

    max_spread_points: float = Field(50.0, gt=0.0)
    max_slippage_points: float = Field(20.0, ge=0.0)

    trading_timezone: str = "UTC"
    trading_session_start: str = "00:00"
    trading_session_end: str = "23:59"
    no_new_entry_after: str = "23:30"
    force_flat_time: str = "23:55"

    retrain_enabled: bool = True
    shadow_mode_enabled: bool = True
    auto_promotion_enabled: bool = False
    purge_bars: int = Field(20, ge=0)
    embargo_bars: int = Field(20, ge=0)
    min_challenger_trades: int = Field(100, ge=1)
    max_allowed_drawdown: float = Field(0.15, ge=0.0, le=1.0)
    min_expectancy_r: float = 0.0

    database_url: str = "sqlite:///storage/database/neuralmt5.db"
    log_level: str = "INFO"
    dashboard_enabled: bool = True
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = Field(8000, ge=1, le=65535)
    dashboard_auth_token: str | None = None
    dashboard_remote_access_enabled: bool = False
    dashboard_trust_https_proxy: bool = False
    dashboard_rate_limit_per_minute: int = Field(120, ge=10, le=10000)
    dashboard_docs_enabled: bool = False


    def symbol_override(self, canonical_symbol: str) -> str | None:
        value = os.getenv(f"SYMBOL_{canonical_symbol.upper()}", "").strip()
        return value or None

    @property
    def brainflow_weights(self) -> tuple[float, ...]:
        return (
            self.w_htf, self.w_mtf, self.w_ltf, self.w_structure,
            self.w_orderflow, self.w_regime, self.w_momentum, self.w_neural,
        )
