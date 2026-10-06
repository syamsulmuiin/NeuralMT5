from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from config.settings import Settings
from contracts.domain import Direction, EvidenceScores
from layer1_market.features import build_feature_rows
from layer1_market.models import BrokerSymbolSpec, Candle
from layer1_market.orderflow import build_orderflow_proxy
from layer1_market.regime import detect_regime
from layer1_market.sequences import synchronize_sequences
from layer1_market.timeframes import timeframe_delta
from layer1_market.structure import analyze_structure
from layer2_brain.inference import infer
from layer2_brain.opportunity import evaluate_neural_opportunity
from layer3_execution.models import MarketQuote, RiskState
from layer3_execution.risk import risk_firewall
from layer3_execution.trade_planner import plan_trade
from .evaluator import metrics_from_r


@dataclass(frozen=True)
class BacktestTrade:
    decision_time_utc: datetime
    entry_time_utc: datetime
    exit_time_utc: datetime
    direction: Direction
    entry: float
    stop_loss: float
    take_profit: float
    exit_price: float
    exit_reason: str
    realized_r: float


@dataclass(frozen=True)
class BacktestResult:
    realized_r: tuple[float, ...]
    metrics: object
    trades: tuple[BacktestTrade, ...] = ()


def run_replay(realized_r: list[float]) -> BacktestResult:
    """Legacy metrics-only helper retained for report code; not a strategy backtest."""
    return BacktestResult(tuple(realized_r), metrics_from_r(realized_r))


def _historical_quote(candle: Candle, spec: BrokerSymbolSpec) -> MarketQuote:
    # Treat candle.open as historical bid and reconstruct ask from the recorded spread.
    bid = float(candle.open)
    ask = bid + float(candle.spread_points) * spec.point
    return MarketQuote(symbol=spec.name, timestamp_utc=candle.time_utc, bid=bid, ask=ask,
                       spread_points=float(candle.spread_points), stale=False)


def _evidence(htf: tuple[Candle, ...], mtf: tuple[Candle, ...], ltf: tuple[Candle, ...], sequences: Any, settings: Settings) -> EvidenceScores:
    hs = analyze_structure(htf, pivot_left=settings.structure_pivot_left, pivot_right=settings.structure_pivot_right)
    ms = analyze_structure(mtf, pivot_left=settings.structure_pivot_left, pivot_right=settings.structure_pivot_right)
    ls = analyze_structure(ltf, pivot_left=settings.structure_pivot_left, pivot_right=settings.structure_pivot_right)
    regime = detect_regime(mtf, lookback=settings.regime_lookback)
    orderflow = build_orderflow_proxy(ltf, lookback=settings.orderflow_lookback)
    values = sequences.ltf.rows[-1].values
    momentum = min(1.0, abs(float(values.get("momentum", 0.0))) * 100.0)
    return EvidenceScores(
        htf_strength=max(hs.structure_score, abs(hs.trend_score)), mtf_quality=ms.structure_score,
        ltf_quality=ls.structure_score, structure_score=(hs.structure_score + ms.structure_score + ls.structure_score) / 3.0,
        orderflow_score=orderflow.orderflow_score, regime_fitness=regime.regime_fitness, momentum_score=momentum,
    )


def run_historical_pipeline(
    *, canonical_symbol: str, spec: BrokerSymbolSpec, candles_by_timeframe: dict[str, tuple[Candle, ...]],
    model: Any, scaler: Any, settings: Settings, initial_equity: float = 10_000.0,
) -> BacktestResult:
    """Point-in-time replay through the production Layer-1/2/3 components.

    Decisions use only candles at/before the decision timestamp. Execution occurs at
    the *next* LTF candle open, avoiding same-bar look-ahead. A bar touching SL and
    TP simultaneously is resolved to SL (conservative, never optimistic).
    """
    htf_all = candles_by_timeframe[settings.htf]
    mtf_all = candles_by_timeframe[settings.mtf]
    ltf_all = candles_by_timeframe[settings.ltf]
    warmup = max(settings.atr_period, settings.momentum_period, settings.volatility_period,
                 settings.regime_lookback, settings.orderflow_lookback) + settings.structure_pivot_left + settings.structure_pivot_right + 4
    minimum = max(settings.ltf_window + warmup, 2)
    equity = float(initial_equity)
    trades: list[BacktestTrade] = []

    for i in range(minimum - 1, len(ltf_all) - 1):
        decision_time = ltf_all[i].time_utc + timeframe_delta(settings.ltf)
        # Keep the replay serial: do not open another trade until the previous one exited.
        if trades and trades[-1].exit_time_utc >= decision_time:
            continue
        histories = {
            settings.htf: tuple(c for c in htf_all if c.time_utc + timeframe_delta(settings.htf) <= decision_time),
            settings.mtf: tuple(c for c in mtf_all if c.time_utc + timeframe_delta(settings.mtf) <= decision_time),
            settings.ltf: tuple(c for c in ltf_all[: i + 1] if c.time_utc + timeframe_delta(settings.ltf) <= decision_time),
        }
        if any(len(histories[tf]) < max(warmup, 3) for tf in (settings.htf, settings.mtf, settings.ltf)):
            continue
        rows = {tf: build_feature_rows(histories[tf], tf, atr_period=settings.atr_period,
                                       momentum_period=settings.momentum_period, volatility_period=settings.volatility_period)
                for tf in (settings.htf, settings.mtf, settings.ltf)}
        if len(rows[settings.htf]) < settings.htf_window or len(rows[settings.mtf]) < settings.mtf_window or len(rows[settings.ltf]) < settings.ltf_window:
            continue
        sequences = synchronize_sequences(
            htf_rows=rows[settings.htf], mtf_rows=rows[settings.mtf], ltf_rows=rows[settings.ltf],
            htf=settings.htf, mtf=settings.mtf, ltf=settings.ltf,
            htf_window=settings.htf_window, mtf_window=settings.mtf_window, ltf_window=settings.ltf_window,
            decision_time_utc=decision_time,
        )
        neural = infer(model, sequences, scaler)
        evidence = _evidence(histories[settings.htf], histories[settings.mtf], histories[settings.ltf], sequences, settings)
        opportunity = evaluate_neural_opportunity(neural, evidence, settings)
        if opportunity.direction is Direction.HOLD:
            continue

        entry_bar = ltf_all[i + 1]
        quote = _historical_quote(entry_bar, spec)
        structure = analyze_structure(histories[settings.ltf], pivot_left=settings.structure_pivot_left, pivot_right=settings.structure_pivot_right)
        values = sequences.ltf.rows[-1].values
        structure_stop = structure.last_swing_low if opportunity.direction is Direction.BUY else structure.last_swing_high
        structure_target = structure.last_swing_high if opportunity.direction is Direction.BUY else structure.last_swing_low
        try:
            plan = plan_trade(direction=opportunity.direction, quote=quote, spec=spec, equity=equity,
                              atr=float(values["atr"]), structure_stop=structure_stop, structure_target=structure_target,
                              decision_id=f"bt:{canonical_symbol}:{decision_time.isoformat()}", settings=settings,
                              now_utc=entry_bar.time_utc)
        except ValueError:
            continue
        risk = risk_firewall(plan=plan, quote=quote, state=RiskState(
            equity=equity, daily_realized_loss_fraction=0.0, daily_committed_risk_fraction=0.0,
            consecutive_losses=0, open_positions=0, total_exposure_fraction=0.0, correlated_exposure_fraction=0.0,
        ), settings=settings)
        if not risk.allowed:
            continue

        exit_price = None; exit_time = None; reason = None
        for j, bar in enumerate(ltf_all[i + 1:], start=i + 1):
            if bar.time_utc.date() != entry_bar.time_utc.date():
                # Intraday contract: close at previous available close before carrying overnight.
                prev = ltf_all[max(i + 1, j - 1)]
                exit_price, exit_time, reason = float(prev.close), prev.time_utc, "SESSION_FLAT"
                break
            if opportunity.direction is Direction.BUY:
                sl_hit, tp_hit = bar.low <= plan.stop_loss, bar.high >= plan.take_profit
            else:
                sl_hit, tp_hit = bar.high >= plan.stop_loss, bar.low <= plan.take_profit
            if sl_hit and tp_hit:
                exit_price, exit_time, reason = plan.stop_loss, bar.time_utc, "AMBIGUOUS_BAR_WORST_CASE_SL"
                break
            if sl_hit:
                exit_price, exit_time, reason = plan.stop_loss, bar.time_utc, "SL"
                break
            if tp_hit:
                exit_price, exit_time, reason = plan.take_profit, bar.time_utc, "TP"
                break
        if exit_price is None:
            last = ltf_all[-1]; exit_price, exit_time, reason = float(last.close), last.time_utc, "DATA_END"
        signed = (exit_price - plan.entry) if opportunity.direction is Direction.BUY else (plan.entry - exit_price)
        pnl = (signed / spec.tick_size) * spec.tick_value * plan.lot
        realized_r = pnl / plan.estimated_loss_at_sl if plan.estimated_loss_at_sl > 0 else 0.0
        equity += pnl
        trades.append(BacktestTrade(decision_time, entry_bar.time_utc, exit_time, opportunity.direction,
                                    plan.entry, plan.stop_loss, plan.take_profit, float(exit_price), str(reason), realized_r))

    rs = [t.realized_r for t in trades]
    return BacktestResult(tuple(rs), metrics_from_r(rs), tuple(trades))
