from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config.settings import Settings
from contracts.domain import Direction
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.models import MarketQuote, PlannedTrade, PreflightResult


def _hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def _inside_session(now: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def execution_preflight(
    *, plan: PlannedTrade, refreshed_quote: MarketQuote, spec: BrokerSymbolSpec,
    settings: Settings, now_utc: datetime,
) -> PreflightResult:
    reasons: list[str] = []
    if plan.symbol != refreshed_quote.symbol or plan.symbol != spec.name:
        reasons.append("symbol mismatch")
    if refreshed_quote.stale:
        reasons.append("stale quote")
    if refreshed_quote.spread_points > settings.max_spread_points:
        reasons.append("spread limit exceeded")

    executable = refreshed_quote.ask if plan.direction is Direction.BUY else refreshed_quote.bid
    slippage_points = abs(executable - plan.entry) / spec.point
    if slippage_points > settings.max_slippage_points + 1e-12:
        reasons.append("slippage limit exceeded")

    try:
        session_tz = ZoneInfo(settings.trading_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"invalid TRADING_TIMEZONE: {settings.trading_timezone}") from exc
    now = now_utc.astimezone(session_tz).time().replace(tzinfo=None)
    start = _hhmm(settings.trading_session_start)
    end = _hhmm(settings.trading_session_end)
    cutoff = _hhmm(settings.no_new_entry_after)
    if not _inside_session(now, start, end):
        reasons.append("outside trading session")
    elif start <= end and now >= cutoff:
        reasons.append("new-entry cutoff reached")
    elif start > end:
        # For overnight sessions, cutoff belongs to whichever side of midnight it is configured on.
        if cutoff >= start and now >= cutoff:
            reasons.append("new-entry cutoff reached")
        elif cutoff <= end and now <= end and now >= cutoff:
            reasons.append("new-entry cutoff reached")

    # Conservative initial-order constraint: respect both stops and freeze distances.
    # Some brokers apply freeze rules around attached SL/TP even on market execution.
    min_stop_distance = max(spec.stops_level, spec.freeze_level) * spec.point
    if abs(executable - plan.stop_loss) + 1e-12 < min_stop_distance:
        reasons.append("SL violates broker stops level after revalidation")
    if abs(plan.take_profit - executable) + 1e-12 < min_stop_distance:
        reasons.append("TP violates broker stops level after revalidation")

    if plan.direction is Direction.BUY:
        if not (plan.stop_loss < executable < plan.take_profit):
            reasons.append("BUY price geometry invalid after revalidation")
    elif plan.direction is Direction.SELL:
        if not (plan.take_profit < executable < plan.stop_loss):
            reasons.append("SELL price geometry invalid after revalidation")
    return PreflightResult(allowed=not reasons, reasons=tuple(dict.fromkeys(reasons)))
