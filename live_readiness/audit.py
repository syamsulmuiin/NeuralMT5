from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import UTC, datetime
from typing import Any

from config.settings import Settings
from layer1_market.models import BrokerSymbolSpec


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ReadinessReport:
    checks: tuple[ReadinessCheck, ...]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(c.detail for c in self.checks if not c.passed)


def audit_artifacts(settings: Settings) -> tuple[ReadinessCheck, ...]:
    return (
        ReadinessCheck("model_artifact", Path(settings.model_artifact_path).is_file(), f"model artifact: {settings.model_artifact_path}"),
        ReadinessCheck("scaler_artifact", Path(settings.scaler_artifact_path).is_file(), f"scaler artifact: {settings.scaler_artifact_path}"),
        ReadinessCheck("auto_promotion_off", not settings.auto_promotion_enabled, "AUTO_PROMOTION_ENABLED must remain false"),
    )

def audit_terminal(settings: Settings, backend: Any) -> tuple[ReadinessCheck, ...]:
    terminal = backend.terminal_info()
    account = backend.account_info()
    checks = [ReadinessCheck("terminal_available", terminal is not None, "terminal_info must be available"),
              ReadinessCheck("account_available", account is not None, "account_info must be available")]
    if terminal is not None:
        checks.append(ReadinessCheck("terminal_connected", bool(getattr(terminal, "connected", False)), "terminal must be connected"))
        if settings.live_require_terminal_trade_allowed:
            checks.append(ReadinessCheck("terminal_trade_allowed", bool(getattr(terminal, "trade_allowed", False)), "terminal trade_allowed must be true"))
    if account is not None and settings.live_require_account_trade_allowed:
        checks.append(ReadinessCheck("account_trade_allowed", bool(getattr(account, "trade_allowed", False)), "account trade_allowed must be true"))
    return tuple(checks)

def audit_symbols(specs: list[BrokerSymbolSpec]) -> tuple[ReadinessCheck, ...]:
    out=[]
    for spec in specs:
        sane = spec.tick_size > 0 and spec.tick_value > 0 and spec.volume_min > 0 and spec.volume_step > 0 and spec.volume_max >= spec.volume_min
        out.append(ReadinessCheck(f"symbol:{spec.name}", sane, f"{spec.name} broker execution specification must be sane"))
    return tuple(out)

def audit_clock(settings: Settings, backend: Any, specs: list[BrokerSymbolSpec]) -> tuple[ReadinessCheck, ...]:
    if not specs:
        return (ReadinessCheck("clock_skew", False, "clock skew cannot be measured without resolved symbols"),)
    tick = backend.symbol_info_tick(specs[0].name)
    raw = getattr(tick, "time", None) if tick is not None else None
    if raw is None:
        return (ReadinessCheck("clock_skew", False, "broker tick timestamp unavailable for clock-skew check"),)
    broker_time = datetime.fromtimestamp(int(raw), tz=UTC)
    skew = abs((datetime.now(UTC) - broker_time).total_seconds())
    return (ReadinessCheck("clock_skew", skew <= settings.live_max_clock_skew_seconds, f"broker/local UTC clock skew={skew:.1f}s (max {settings.live_max_clock_skew_seconds}s)"),)

def build_report(settings: Settings, backend: Any, specs: list[BrokerSymbolSpec]) -> ReadinessReport:
    return ReadinessReport(audit_artifacts(settings) + audit_terminal(settings, backend) + audit_symbols(specs) + audit_clock(settings, backend, specs))
