from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any
from uuid import uuid4

from config.settings import Settings, TradingMode
from contracts.domain import Direction, EvidenceScores, NeuralOutput
from contracts.events import EventType
from dashboard.commands import CommandGateway
from dashboard.schemas import CommandType, RuntimeMode
from dashboard.state import RuntimeState
from dashboard.websocket import EventBus
from layer1_market.broker_discovery import discover_account, discover_symbols
from layer1_market.features import FEATURE_VERSION, build_feature_rows
from layer1_market.market_data import fetch_recent_candles
from layer1_market.models import BrokerSymbolSpec
from layer1_market.mt5_client import MT5Client
from layer1_market.orderflow import build_orderflow_proxy
from layer1_market.regime import detect_regime
from layer1_market.sequences import synchronize_sequences
from layer1_market.structure import analyze_structure
from layer1_market.symbol_resolver import resolve_many
from layer1_market.timeframes import timeframe_delta
from layer1_market.validator import is_tick_stale, validate_candles
from layer2_brain.inference import infer
from layer2_brain.opportunity import evaluate_neural_opportunity
from layer3_execution.executor import execute_plan
from layer3_execution.idempotency import DuplicateOrderError, OrderRegistry
from layer3_execution.models import MarketQuote, PreflightResult, ExecutionState
from layer3_execution.mt5_execution_adapter import MT5ExecutionAdapter
from layer3_execution.preflight import execution_preflight
from layer3_execution.recovery import assess_restart_recovery
from layer3_execution.monitor import force_flat_due, mark_position, safety_issue, snapshot_from_mt5
from layer3_execution.reconciliation import execution_identity_from_mt5, closed_position_outcome_from_mt5
from layer3_execution.risk import risk_firewall
from layer3_execution.trade_planner import plan_trade
from layer4_learning.journal import Journal
from layer4_learning.models import ObservationRecord
from runtime.events import RuntimeEventPublisher
from runtime.store import RuntimeStore
from live_readiness.audit import build_report

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeCycleResult:
    cycle_id: str
    processed_symbols: int
    holds: int
    planned: int
    executed: int
    errors: int


def _sqlite_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Phase 6 runtime currently supports sqlite:/// database URLs only")
    return Path(database_url[len(prefix):])


def _config_hash(settings: Settings) -> str:
    safe = settings.model_dump(mode="json", exclude={"mt5_password", "dashboard_auth_token"})
    return hashlib.sha256(json.dumps(safe, sort_keys=True, default=str).encode()).hexdigest()


def _feature_payload(sequences: Any) -> dict[str, float]:
    # Journal the latest LTF row only as the point-in-time observation payload.
    return dict(sequences.ltf.rows[-1].values)


class NeuralMT5Runtime:
    """Closed-loop runtime with Phase 7 live-readiness gates."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: MT5Client,
        model: Any,
        scaler: Any,
        runtime_state: RuntimeState | None = None,
        event_bus: EventBus | None = None,
        command_gateway: CommandGateway | None = None,
        sleep_fn=time.sleep,
    ) -> None:
        if settings.trading_mode is TradingMode.LIVE and not (
            settings.live_execution_enabled and settings.live_readiness_acknowledged
            and settings.live_fault_injection_passed and settings.live_soak_test_passed
        ):
            raise PermissionError("LIVE mode is blocked until all Phase 7 readiness gates are explicitly satisfied")
        self.settings = settings
        self.client = client
        self.model = model
        self.scaler = scaler
        self.state = runtime_state or RuntimeState(mode=RuntimeMode(settings.trading_mode.value))
        self.bus = event_bus or EventBus()
        self.gateway = command_gateway or CommandGateway(self.state)
        self.db_path = _sqlite_path(settings.database_url)
        self.store = RuntimeStore(self.db_path)
        self.journal = Journal(self.db_path)
        self.registry = OrderRegistry(self.db_path)
        self.events = RuntimeEventPublisher(self.store, self.state, self.bus)
        self._stop = Event()
        self._sleep = sleep_fn
        self._specs: dict[str, BrokerSymbolSpec] = {}
        self._resolutions: dict[str, Any] = {}
        self._account: Any = None
        self._config_hash = _config_hash(settings)

    def start(self) -> None:
        self._connect_with_retry()
        all_specs = discover_symbols(self.client)
        overrides = {symbol: self.settings.symbol_override(symbol) for symbol in self.settings.symbols}
        self._resolutions = resolve_many(
            self.settings.symbols,
            all_specs,
            min_confidence=self.settings.min_symbol_resolution_confidence,
            overrides=overrides,
            exclude_tokens=self.settings.symbol_exclude_tokens,
        )
        by_name = {spec.name: spec for spec in all_specs}
        self._specs = {
            canonical: by_name[resolution.broker_symbol]
            for canonical, resolution in self._resolutions.items()
            if resolution.broker_symbol in by_name
        }
        self._account = discover_account(self.client)
        if self.settings.trading_mode is TradingMode.LIVE:
            report = build_report(self.settings, self.client.backend, list(self._specs.values()))
            if not report.passed:
                raise PermissionError("Phase 7 live-readiness audit failed: " + "; ".join(report.failures))
        self._recover()
        self.store.set_state("runtime_started_at_utc", datetime.now(UTC).isoformat())
        self.events.emit(EventType.RECONCILIATION_COMPLETE, source="runtime.start", payload={"clean": self.state.reconciliation_ok})

    def stop(self) -> None:
        self._stop.set()
        try:
            self.client.shutdown()
        finally:
            self.store.set_state("runtime_stopped_at_utc", datetime.now(UTC).isoformat())

    def run(self, *, max_cycles: int | None = None) -> None:
        cycles = 0
        while not self._stop.is_set() and (max_cycles is None or cycles < max_cycles):
            self.run_once()
            cycles += 1
            if not self._stop.is_set() and (max_cycles is None or cycles < max_cycles):
                self._sleep(self.settings.runtime_loop_seconds)

    def run_once(self) -> RuntimeCycleResult:
        try:
            self._process_commands()
            self._maintain_positions()
            self._account = discover_account(self.client)
        except Exception as exc:
            with self.state._lock:
                self.state.new_entries_paused = True
            self._record_error(f"cycle pre-entry safety maintenance failed: {exc}", None)
            raise RuntimeError(f"runtime safety maintenance failed; new entries paused: {exc}") from exc
        cycle_id = str(uuid4())
        started = datetime.now(UTC)
        self.store.begin_cycle(cycle_id, started)
        processed = holds = planned = executed = errors = 0
        for canonical in self.settings.symbols:
            if self._stop.is_set():
                break
            try:
                result = self._process_symbol(canonical, cycle_id)
                if result == "HOLD": holds += 1
                elif result == "PLANNED": planned += 1
                elif result == "EXECUTED": executed += 1
                processed += 1
            except Exception as exc:
                errors += 1
                self._record_error(f"{canonical}: {exc}", cycle_id)
        result = RuntimeCycleResult(cycle_id, processed, holds, planned, executed, errors)
        self.store.finish_cycle(cycle_id, "OK" if errors == 0 else "DEGRADED", result.__dict__)
        return result

    def _process_symbol(self, canonical: str, cycle_id: str) -> str:
        resolution = self._resolutions.get(canonical)
        if resolution is None or resolution.broker_symbol is None:
            self.events.emit(EventType.TRADE_REJECTED, source="runtime.symbol", correlation_id=cycle_id, payload={"canonical_symbol": canonical, "reason": getattr(resolution, "reason", "unresolved symbol")})
            return "HOLD"
        spec = self._specs[canonical]
        now = datetime.now(UTC)
        candles: dict[str, tuple[Any, ...]] = {}
        rows: dict[str, tuple[Any, ...]] = {}
        windows = {self.settings.htf: self.settings.htf_window, self.settings.mtf: self.settings.mtf_window, self.settings.ltf: self.settings.ltf_window}
        warmup = max(self.settings.atr_period, self.settings.momentum_period, self.settings.volatility_period, self.settings.regime_lookback, self.settings.orderflow_lookback) + self.settings.structure_pivot_left + self.settings.structure_pivot_right + 4
        for tf in (self.settings.htf, self.settings.mtf, self.settings.ltf):
            count = windows[tf] + warmup
            data = fetch_recent_candles(self.client, spec.name, tf, count, include_forming=False)
            report = validate_candles(data, tf, decision_time_utc=now, minimum_history=count, max_missing_ratio=self.settings.max_missing_candle_ratio)
            if not report.valid:
                self.events.emit(EventType.TRADE_REJECTED, source="runtime.data", correlation_id=cycle_id, payload={"symbol": spec.name, "timeframe": tf, "reason": "; ".join(report.reasons)})
                return "HOLD"
            candles[tf] = data
            rows[tf] = build_feature_rows(data, tf, atr_period=self.settings.atr_period, momentum_period=self.settings.momentum_period, volatility_period=self.settings.volatility_period)
        decision_time = rows[self.settings.ltf][-1].timestamp_utc + timeframe_delta(self.settings.ltf)
        sequences = synchronize_sequences(
            htf_rows=rows[self.settings.htf], mtf_rows=rows[self.settings.mtf], ltf_rows=rows[self.settings.ltf],
            htf=self.settings.htf, mtf=self.settings.mtf, ltf=self.settings.ltf,
            htf_window=self.settings.htf_window, mtf_window=self.settings.mtf_window, ltf_window=self.settings.ltf_window,
            decision_time_utc=decision_time,
        )
        htf_structure = analyze_structure(candles[self.settings.htf], pivot_left=self.settings.structure_pivot_left, pivot_right=self.settings.structure_pivot_right)
        mtf_structure = analyze_structure(candles[self.settings.mtf], pivot_left=self.settings.structure_pivot_left, pivot_right=self.settings.structure_pivot_right)
        ltf_structure = analyze_structure(candles[self.settings.ltf], pivot_left=self.settings.structure_pivot_left, pivot_right=self.settings.structure_pivot_right)
        regime = detect_regime(candles[self.settings.mtf], lookback=self.settings.regime_lookback)
        orderflow = build_orderflow_proxy(candles[self.settings.ltf], lookback=self.settings.orderflow_lookback)
        ltf_values = sequences.ltf.rows[-1].values
        momentum_score = min(1.0, abs(float(ltf_values.get("momentum", 0.0))) * 100.0)
        evidence = EvidenceScores(
            htf_strength=max(htf_structure.structure_score, abs(htf_structure.trend_score)),
            mtf_quality=mtf_structure.structure_score,
            ltf_quality=ltf_structure.structure_score,
            structure_score=(htf_structure.structure_score + mtf_structure.structure_score + ltf_structure.structure_score) / 3.0,
            orderflow_score=orderflow.orderflow_score,
            regime_fitness=regime.regime_fitness,
            momentum_score=momentum_score,
        )
        neural: NeuralOutput = infer(self.model, sequences, self.scaler)
        brainflow = evaluate_neural_opportunity(neural, evidence, self.settings)
        observation_id = hashlib.sha256(f"{canonical}|{decision_time.isoformat()}|{FEATURE_VERSION}".encode()).hexdigest()[:32]
        try:
            self.journal.append_observation(
                ObservationRecord(observation_id, canonical, decision_time, _feature_payload(sequences), FEATURE_VERSION, self.settings.dataset_version),
                spec.name, self.settings.htf, self.settings.mtf, self.settings.ltf,
            )
        except sqlite3.IntegrityError:
            if not self.journal.has_observation(observation_id):
                raise
        self.events.emit(EventType.NEURAL_INFERENCE, source="runtime.brain", correlation_id=cycle_id, payload={"symbol": spec.name, "buy": neural.buy_score, "sell": neural.sell_score, "hold": neural.hold_score, "brainflow": brainflow.brainflow_score, "direction": brainflow.direction.value})
        opportunity_id = hashlib.sha256(f"opp|{observation_id}|{brainflow.direction.value}".encode()).hexdigest()[:32]
        versions = {"feature_version": FEATURE_VERSION, "dataset_version": self.settings.dataset_version, "scaler_version": getattr(self.scaler, "version", "unknown"), "config_hash": self._config_hash}
        if brainflow.direction is Direction.HOLD or self.state.new_entries_paused or self.state.emergency_stop or not self.state.reconciliation_ok:
            reason = brainflow.reason
            if self.state.new_entries_paused: reason = "new entries paused"
            if self.state.emergency_stop: reason = "emergency stop active"
            if not self.state.reconciliation_ok: reason = "reconciliation not clean"
            self.store.record_opportunity(opportunity_id=opportunity_id, observation_id=observation_id, decided_at_utc=decision_time, neural=neural, brainflow=brainflow, risk_decision="REJECTED", rejection_reason=reason, versions=versions)
            return "HOLD"

        quote = self._current_quote(spec)
        atr = float(ltf_values["atr"])
        structure_stop = ltf_structure.last_swing_low if brainflow.direction is Direction.BUY else ltf_structure.last_swing_high
        structure_target = ltf_structure.last_swing_high if brainflow.direction is Direction.BUY else ltf_structure.last_swing_low
        plan = plan_trade(direction=brainflow.direction, quote=quote, spec=spec, equity=self._account.equity, atr=atr, structure_stop=structure_stop, structure_target=structure_target, decision_id=opportunity_id, settings=self.settings, now_utc=now)
        symbol_currencies = {x.name: {c for c in (x.currency_base, x.currency_profit) if c} for x in self._specs.values()}
        candidate_currencies = {c for c in (spec.currency_base, spec.currency_profit) if c}
        risk_state = self.store.current_risk_state(self._account.equity, candidate_currencies=candidate_currencies, symbol_currencies=symbol_currencies)
        risk = risk_firewall(plan=plan, quote=quote, state=risk_state, settings=self.settings)
        if not risk.allowed:
            self.store.record_opportunity(opportunity_id=opportunity_id, observation_id=observation_id, decided_at_utc=decision_time, neural=neural, brainflow=brainflow, risk_decision="REJECTED", rejection_reason="; ".join(risk.reasons), versions=versions)
            self.events.emit(EventType.TRADE_REJECTED, source="runtime.risk", correlation_id=cycle_id, payload={"symbol": spec.name, "reasons": list(risk.reasons)})
            return "HOLD"

        self.store.record_opportunity(opportunity_id=opportunity_id, observation_id=observation_id, decided_at_utc=decision_time, neural=neural, brainflow=brainflow, risk_decision="ALLOWED", rejection_reason=None, versions=versions)
        trade_plan_id = f"plan:{opportunity_id}"
        self.store.record_trade_plan(trade_plan_id, opportunity_id, plan)
        if self.state.mode is RuntimeMode.ANALYSIS:
            return "PLANNED"

        refreshed = self._current_quote(spec)
        preflight = execution_preflight(plan=plan, refreshed_quote=refreshed, spec=spec, settings=self.settings, now_utc=datetime.now(UTC))
        mode = TradingMode(self.state.mode.value)
        backend = MT5ExecutionAdapter(self.client.backend, spec, self.settings) if mode is TradingMode.LIVE else None
        try:
            execution = execute_plan(plan=plan, preflight=preflight, mode=mode, registry=self.registry, backend=backend)
        except DuplicateOrderError:
            self.events.emit(EventType.TRADE_REJECTED, source="runtime.idempotency", correlation_id=cycle_id, payload={"symbol": spec.name, "reason": "duplicate order key"})
            return "HOLD"
        order_id = f"order:{plan.client_order_key}"
        self.store.record_execution(order_id, trade_plan_id, plan, execution)
        if mode is TradingMode.LIVE and execution.state in {ExecutionState.FILLED, ExecutionState.PARTIALLY_FILLED, ExecutionState.SENT}:
            identity = execution_identity_from_mt5(self.client.backend, order_ticket=execution.order_ticket, deal_ticket=execution.deal_ticket)
            self.store.bind_execution_identity(
                order_id, order_ticket=identity.order_ticket, deal_ticket=identity.deal_ticket,
                position_ticket=identity.position_ticket, actual_entry=identity.price or execution.actual_entry,
                opened_at_utc=identity.time_utc,
            )
            if execution.state in {ExecutionState.FILLED, ExecutionState.PARTIALLY_FILLED} and identity.position_ticket is None:
                with self.state._lock:
                    self.state.reconciliation_ok = False
                    self.state.new_entries_paused = True
                self._record_error(f"{spec.name}: broker fill has no reconciled position identity", cycle_id)
        self.events.emit(EventType.ORDER_FILLED if execution.actual_entry is not None else EventType.TRADE_REJECTED, source="runtime.execution", correlation_id=cycle_id, payload=execution.model_dump(mode="json"))
        return "EXECUTED" if execution.actual_entry is not None else "HOLD"

    def _current_quote(self, spec: BrokerSymbolSpec) -> MarketQuote:
        try:
            tick = self.client.backend.symbol_info_tick(spec.name)
        except Exception as exc:
            raise RuntimeError(f"symbol_info_tick raised for {spec.name}: {exc}") from exc
        if tick is None:
            raise RuntimeError(f"symbol_info_tick failed for {spec.name}: {self.client.backend.last_error()}")
        raw_time = getattr(tick, "time", None)
        tick_time = datetime.fromtimestamp(int(raw_time), tz=UTC) if raw_time is not None else datetime.now(UTC)
        bid = float(getattr(tick, "bid"))
        ask = float(getattr(tick, "ask"))
        spread = max(0.0, (ask - bid) / spec.point)
        return MarketQuote(symbol=spec.name, timestamp_utc=tick_time, bid=bid, ask=ask, spread_points=spread, stale=is_tick_stale(tick_time, datetime.now(UTC), self.settings.max_stale_tick_seconds))

    def _recover(self) -> None:
        positions_get = getattr(self.client.backend, "positions_get", None)
        broker_tickets: set[int] = set()
        if callable(positions_get):
            try:
                positions = positions_get() or ()
            except Exception as exc:
                raise RuntimeError(f"MT5 positions_get failed during startup recovery: {exc}") from exc
            broker_tickets = {int(getattr(p, "ticket")) for p in positions if getattr(p, "ticket", None) is not None}
        decision = assess_restart_recovery(broker_tickets=broker_tickets, journal_tickets=self.store.open_journal_tickets())
        with self.state._lock:
            self.state.reconciliation_ok = decision.safe_to_open_new_positions
            if not decision.safe_to_open_new_positions:
                self.state.new_entries_paused = True

    def _maintain_positions(self) -> None:
        """Keep paper/live positions auditable before evaluating any new entry."""
        now = datetime.now(UTC)
        records = self.store.open_trade_records()
        if not records:
            return
        if self.state.mode is RuntimeMode.PAPER:
            for row in records:
                # Symbol is authoritative in the persisted execution request.
                try:
                    request = json.loads(row.get("request_payload_json") or "{}")
                    symbol = request.get("symbol")
                except (TypeError, ValueError, json.JSONDecodeError):
                    symbol = None
                spec = next((x for x in self._specs.values() if x.name == symbol), None)
                if spec is None:
                    continue
                quote = self._current_quote(spec)
                direction = Direction(row["direction"]); px = quote.bid if direction is Direction.BUY else quote.ask
                signed = (px - float(row["actual_entry"])) if direction is Direction.BUY else (float(row["actual_entry"]) - px)
                self.store.update_trade_mark(row["trade_id"], mfe=max(signed,0.0), mae=max(-signed,0.0))
                reason = None; exit_price = px
                if direction is Direction.BUY and px <= float(row["stop_loss"]): reason="SL"; exit_price=float(row["stop_loss"])
                elif direction is Direction.BUY and px >= float(row["take_profit"]): reason="TP"; exit_price=float(row["take_profit"])
                elif direction is Direction.SELL and px >= float(row["stop_loss"]): reason="SL"; exit_price=float(row["stop_loss"])
                elif direction is Direction.SELL and px <= float(row["take_profit"]): reason="TP"; exit_price=float(row["take_profit"])
                elif force_flat_due(now, self.settings): reason="FORCE_FLAT"
                if reason:
                    delta = (exit_price-float(row["actual_entry"])) if direction is Direction.BUY else (float(row["actual_entry"])-exit_price)
                    gross = (delta/spec.tick_size)*spec.tick_value*float(row["lot"])
                    self.store.paper_close_trade(row["trade_id"], closed_at_utc=now, exit_price=exit_price, gross_pnl=gross, exit_reason=reason)
                    self.events.emit(EventType.POSITION_CLOSED, source="runtime.paper_monitor", payload={"trade_id":row["trade_id"],"reason":reason,"exit_price":exit_price,"net_pnl":gross})
            return

        if self.state.mode is not RuntimeMode.LIVE:
            return
        positions_get = getattr(self.client.backend, "positions_get", None)
        if not callable(positions_get):
            self._record_error("MT5 positions_get unavailable during live monitoring", None); return
        positions = positions_get() or ()
        broker = {int(getattr(p,"ticket")): p for p in positions if getattr(p,"ticket",None) is not None}
        managed = {int(r["mt5_position_ticket"]): r for r in records if r.get("mt5_position_ticket") is not None}
        unmanaged = set(broker)-set(managed)
        if unmanaged:
            with self.state._lock:
                self.state.reconciliation_ok=False; self.state.new_entries_paused=True
            self._record_error(f"unmanaged broker positions detected: {sorted(unmanaged)}", None)
        for ticket,row in managed.items():
            p = broker.get(ticket)
            if p is None:
                outcome = closed_position_outcome_from_mt5(self.client.backend, ticket)
                if outcome is None:
                    with self.state._lock:
                        self.state.reconciliation_ok=False; self.state.new_entries_paused=True
                    self._record_error(f"position {ticket} disappeared without reconcilable deal history", None)
                    continue
                self.store.close_trade(ticket, closed_at_utc=outcome.closed_at_utc, exit_price=outcome.exit_price, gross_pnl=outcome.gross_pnl, commission=outcome.commission, swap=outcome.swap, net_pnl=outcome.net_pnl, exit_reason=outcome.reason)
                self.events.emit(EventType.POSITION_CLOSED, source="runtime.live_monitor", payload={"position_ticket":ticket,"net_pnl":outcome.net_pnl,"reason":outcome.reason})
                continue
            tick = self.client.backend.symbol_info_tick(str(getattr(p,"symbol")))
            if tick is None:
                self._record_error(f"position {ticket}: tick unavailable", None); continue
            snap=snapshot_from_mt5(p,tick); issue=safety_issue(snap); mark=mark_position(snap)
            self.store.update_position_mark(ticket,mfe=mark.favorable_excursion,mae=mark.adverse_excursion)
            if issue:
                with self.state._lock:
                    self.state.new_entries_paused=True
                self._record_error(f"position {ticket} safety issue: {issue}", None)
            if force_flat_due(now,self.settings):
                spec=next((x for x in self._specs.values() if x.name==snap.symbol),None)
                if spec is None:
                    self._record_error(f"position {ticket}: symbol spec unavailable for force-flat",None); continue
                adapter=MT5ExecutionAdapter(self.client.backend,spec,self.settings)
                close_price=float(getattr(tick,"bid" if snap.direction is Direction.BUY else "ask"))
                receipt=adapter.close_position(position_ticket=ticket,symbol=snap.symbol,volume=snap.volume,direction=snap.direction.value,price=close_price)
                if receipt.partial:
                    with self.state._lock:
                        self.state.new_entries_paused=True; self.state.reconciliation_ok=False
                    self._record_error(f"position {ticket}: force-flat partially filled; reconciliation required",None)
        clean = not unmanaged and all(t in broker or closed_position_outcome_from_mt5(self.client.backend,t) is not None for t in managed)
        with self.state._lock:
            self.state.reconciliation_ok = clean

    def _connect_with_retry(self) -> None:
        last: Exception | None = None
        for attempt in range(1, self.settings.mt5_reconnect_attempts + 1):
            try:
                self.client.connect(login=int(self.settings.mt5_login) if self.settings.mt5_login else None, password=self.settings.mt5_password, server=self.settings.mt5_server, path=self.settings.mt5_path)
                return
            except Exception as exc:
                last = exc
                if attempt < self.settings.mt5_reconnect_attempts:
                    self._sleep(self.settings.mt5_reconnect_delay_seconds)
        raise ConnectionError(f"MT5 connection failed after {self.settings.mt5_reconnect_attempts} attempts: {last}")

    def _process_commands(self) -> None:
        while True:
            item = self.gateway.next_command(timeout=0.0)
            if item is None:
                break
            _, request = item
            if request.command is CommandType.SET_MODE and request.mode is RuntimeMode.LIVE:
                gates = (self.settings.live_execution_enabled and self.settings.live_readiness_acknowledged
                         and self.settings.live_fault_injection_passed and self.settings.live_soak_test_passed)
                report = build_report(self.settings, self.client.backend, list(self._specs.values())) if gates and self._specs else None
                if not gates or report is None or not report.passed:
                    detail = "; ".join(report.failures) if report is not None else "Phase 7 live-readiness gates not satisfied"
                    self._record_error(f"LIVE mode command rejected: {detail}", None)
                    continue
            if request.command is CommandType.PROMOTE_MODEL:
                self._record_error("model promotion command must be handled by validated Layer 4 workflow", None)
                continue
            self.gateway.apply_runtime_control(request)
            self.store.set_state("runtime_mode", self.state.mode.value)

    def _record_error(self, message: str, correlation_id: str | None) -> None:
        with self.state._lock:
            self.state.last_error = message
        self.events.emit(EventType.SYSTEM_ERROR, source="runtime", correlation_id=correlation_id, payload={"error": message})

