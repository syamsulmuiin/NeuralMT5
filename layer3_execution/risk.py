from __future__ import annotations

from config.settings import Settings
from layer3_execution.models import MarketQuote, PlannedTrade, PreflightResult, RiskState


def risk_firewall(*, plan: PlannedTrade, quote: MarketQuote, state: RiskState, settings: Settings) -> PreflightResult:
    reasons: list[str] = []
    if quote.stale:
        reasons.append("stale quote")
    if quote.spread_points > settings.max_spread_points:
        reasons.append("spread limit exceeded")
    if state.daily_realized_loss_fraction >= settings.max_daily_loss:
        reasons.append("daily loss limit reached")
    if state.daily_committed_risk_fraction + plan.risk_fraction > settings.max_daily_risk + 1e-12:
        reasons.append("daily risk limit exceeded")
    if state.consecutive_losses >= settings.max_consecutive_losses:
        reasons.append("consecutive loss limit reached")
    if state.open_positions >= settings.max_open_positions:
        reasons.append("maximum open positions reached")
    if state.total_exposure_fraction + plan.risk_fraction > settings.max_total_exposure + 1e-12:
        reasons.append("total exposure limit exceeded")
    if state.correlated_exposure_fraction + plan.risk_fraction > settings.max_correlated_exposure + 1e-12:
        reasons.append("correlated exposure limit exceeded")
    return PreflightResult(allowed=not reasons, reasons=tuple(reasons))
