from __future__ import annotations

from datetime import time
import ipaddress
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config.settings import SUPPORTED_TIMEFRAMES, Settings, TradingMode




def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _parse_hhmm(name: str, value: str) -> time:
    try:
        hour_text, minute_text = value.split(":", maxsplit=1)
        return time(hour=int(hour_text), minute=int(minute_text))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must use HH:MM 24-hour format") from exc


def validate_settings(settings: Settings) -> Settings:
    if not settings.symbols:
        raise ValueError("SYMBOLS must contain at least one canonical symbol")

    invalid = [v for v in (settings.htf, settings.mtf, settings.ltf) if v.upper() not in SUPPORTED_TIMEFRAMES]
    if invalid:
        raise ValueError(f"Unsupported timeframe(s): {', '.join(invalid)}")

    weight_sum = sum(settings.brainflow_weights)
    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(f"Brainflow weights must sum to 1.0, got {weight_sum:.12f}")

    if settings.risk_per_trade > settings.max_daily_risk:
        raise ValueError("RISK_PER_TRADE cannot exceed MAX_DAILY_RISK")
    if settings.max_correlated_exposure > settings.max_total_exposure:
        raise ValueError("MAX_CORRELATED_EXPOSURE cannot exceed MAX_TOTAL_EXPOSURE")

    try:
        ZoneInfo(settings.trading_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"TRADING_TIMEZONE is invalid: {settings.trading_timezone}") from exc

    _parse_hhmm("TRADING_SESSION_START", settings.trading_session_start)
    _parse_hhmm("TRADING_SESSION_END", settings.trading_session_end)
    _parse_hhmm("NO_NEW_ENTRY_AFTER", settings.no_new_entry_after)
    _parse_hhmm("FORCE_FLAT_TIME", settings.force_flat_time)

    if settings.trading_mode is TradingMode.LIVE:
        missing = [name for name, value in (
            ("MT5_LOGIN", settings.mt5_login),
            ("MT5_PASSWORD", settings.mt5_password),
            ("MT5_SERVER", settings.mt5_server),
        ) if not value]
        if missing:
            raise ValueError("LIVE mode requires explicit MT5 credentials/config: " + ", ".join(missing))
        if not settings.live_execution_enabled:
            raise ValueError("LIVE mode requires LIVE_EXECUTION_ENABLED=true after Phase 7 readiness audit")
        if not settings.live_readiness_acknowledged:
            raise ValueError("LIVE mode requires LIVE_READINESS_ACKNOWLEDGED=true")
        if not settings.live_fault_injection_passed or not settings.live_soak_test_passed:
            raise ValueError("LIVE mode requires completed fault-injection and soak-test attestations")

    if settings.auto_promotion_enabled:
        raise ValueError("AUTO_PROMOTION_ENABLED=true is prohibited by the safety baseline")

    if not _is_loopback_host(settings.dashboard_host):
        if not settings.dashboard_remote_access_enabled:
            raise ValueError("non-loopback DASHBOARD_HOST requires DASHBOARD_REMOTE_ACCESS_ENABLED=true")
        if not settings.dashboard_auth_token:
            raise ValueError("remote dashboard requires DASHBOARD_AUTH_TOKEN")
        if not settings.dashboard_trust_https_proxy:
            raise ValueError("remote dashboard requires TLS/reverse proxy acknowledgement")

    return settings
