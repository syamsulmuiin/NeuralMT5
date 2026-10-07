from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contracts.domain import BrainflowResult, EvidenceScores, NeuralOutput
from layer3_execution.models import ExecutionResult, PlannedTrade, RiskState


class RuntimeStore:
    """Persistence bridge used by the integrated runtime.

    The store writes only auditable runtime facts. It does not make trading decisions.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        schema = Path(__file__).parents[1] / "storage/database/schema.sql"
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            schema_sql = schema.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"failed to prepare runtime database {self.path}: {exc}") from exc
        with self._connect() as conn:
            conn.executescript(schema_sql)
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runtime_cycles (
                    cycle_id TEXT PRIMARY KEY,
                    started_at_utc TEXT NOT NULL,
                    completed_at_utc TEXT,
                    status TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(orders)").fetchall()}
            if "mt5_deal_ticket" not in columns:
                conn.execute("ALTER TABLE orders ADD COLUMN mt5_deal_ticket INTEGER")

    @contextmanager
    def _connect(self):
        conn = None
        try:
            conn = sqlite3.connect(self.path, timeout=10.0)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 10000")
            yield conn
            conn.commit()
        except sqlite3.IntegrityError:
            if conn is not None:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            raise
        except sqlite3.Error as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            raise RuntimeError(f"runtime database operation failed ({self.path}): {exc}") from exc
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            raise
        finally:
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass

    def set_state(self, key: str, value: Any) -> None:
        now = datetime.now(UTC).isoformat()
        payload = json.dumps(value, sort_keys=True, default=str)
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO runtime_state(key,value_json,updated_at_utc) VALUES(?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at_utc=excluded.updated_at_utc""",
                (key, payload, now),
            )

    def get_state(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value_json FROM runtime_state WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        return json.loads(row[0])

    def begin_cycle(self, cycle_id: str, started_at_utc: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runtime_cycles(cycle_id,started_at_utc,status,details_json) VALUES(?,?,?,?)",
                (cycle_id, started_at_utc.isoformat(), "RUNNING", "{}"),
            )

    def finish_cycle(self, cycle_id: str, status: str, details: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runtime_cycles SET completed_at_utc=?,status=?,details_json=? WHERE cycle_id=?",
                (datetime.now(UTC).isoformat(), status, json.dumps(details, sort_keys=True, default=str), cycle_id),
            )

    def record_event(self, event_id: str, event_type: str, occurred_at_utc: datetime, source: str, correlation_id: str | None, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO system_events(event_id,event_type,occurred_at_utc,source,correlation_id,payload_json) VALUES(?,?,?,?,?,?)",
                (event_id, event_type, occurred_at_utc.isoformat(), source, correlation_id, json.dumps(payload, sort_keys=True, default=str)),
            )

    def record_opportunity(
        self,
        *,
        opportunity_id: str,
        observation_id: str,
        decided_at_utc: datetime,
        neural: NeuralOutput,
        brainflow: BrainflowResult,
        risk_decision: str,
        rejection_reason: str | None,
        versions: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO opportunities(
                    opportunity_id,observation_id,decided_at_utc,direction,buy_score,sell_score,hold_score,
                    brainflow_score,confidence,risk_decision,rejection_reason,version_payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    opportunity_id, observation_id, decided_at_utc.isoformat(), brainflow.direction.value,
                    neural.buy_score, neural.sell_score, neural.hold_score, brainflow.brainflow_score,
                    brainflow.confidence, risk_decision, rejection_reason, json.dumps(versions, sort_keys=True),
                ),
            )

    def record_trade_plan(self, trade_plan_id: str, opportunity_id: str, plan: PlannedTrade) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO trade_plans(
                    trade_plan_id,opportunity_id,entry,stop_loss,take_profit,rr,risk_fraction,lot,
                    estimated_loss_at_sl,created_at_utc
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    trade_plan_id, opportunity_id, plan.entry, plan.stop_loss, plan.take_profit, plan.rr,
                    plan.risk_fraction, plan.lot, plan.estimated_loss_at_sl, plan.planned_at_utc.isoformat(),
                ),
            )

    def record_execution(self, order_id: str, trade_plan_id: str, plan: PlannedTrade, result: ExecutionResult) -> None:
        now = datetime.now(UTC).isoformat()
        request = {
            "symbol": plan.symbol,
            "direction": plan.direction.value,
            "volume": plan.lot,
            "price": plan.entry,
            "sl": plan.stop_loss,
            "tp": plan.take_profit,
        }
        response = result.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO orders(
                    order_id,trade_plan_id,mt5_order_ticket,mt5_deal_ticket,client_order_key,state,requested_at_utc,updated_at_utc,
                    request_payload_json,response_payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    order_id, trade_plan_id, result.order_ticket, result.deal_ticket, plan.client_order_key, result.state.value,
                    now, now, json.dumps(request, sort_keys=True), json.dumps(response, sort_keys=True),
                ),
            )
            if result.actual_entry is not None:
                trade_id = f"trade:{order_id}"
                conn.execute(
                    """INSERT OR IGNORE INTO trades(trade_id,order_id,mt5_position_ticket,opened_at_utc,actual_entry)
                       VALUES(?,?,?,?,?)""",
                    (trade_id, order_id, result.position_ticket, now, result.actual_entry),
                )

    def open_journal_tickets(self) -> set[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT mt5_position_ticket FROM trades WHERE closed_at_utc IS NULL AND mt5_position_ticket IS NOT NULL").fetchall()
        return {int(row[0]) for row in rows}

    def current_risk_state(self, equity: float, *, candidate_currencies: set[str] | None = None, symbol_currencies: dict[str, set[str]] | None = None) -> RiskState:
        today = datetime.now(UTC).date().isoformat()
        with self._connect() as conn:
            open_rows = conn.execute(
                """SELECT p.risk_fraction,o.request_payload_json FROM trades t JOIN orders o ON o.order_id=t.order_id
                   JOIN trade_plans p ON p.trade_plan_id=o.trade_plan_id WHERE t.closed_at_utc IS NULL"""
            ).fetchall()
            closed_rows = conn.execute(
                "SELECT net_pnl,realized_r FROM trades WHERE closed_at_utc IS NOT NULL AND substr(closed_at_utc,1,10)=? ORDER BY closed_at_utc",
                (today,),
            ).fetchall()
        committed = sum(float(r[0]) for r in open_rows)
        correlated = 0.0
        if candidate_currencies and symbol_currencies:
            for risk_fraction, payload in open_rows:
                try:
                    symbol = json.loads(payload).get("symbol")
                except (TypeError, ValueError, json.JSONDecodeError):
                    symbol = None
                currencies = symbol_currencies.get(symbol or "", set())
                if currencies & candidate_currencies:
                    correlated += float(risk_fraction)
        realized_loss_amount = abs(sum(min(float(r[0] or 0.0), 0.0) for r in closed_rows))
        consecutive_losses = 0
        for _, realized_r in reversed(closed_rows):
            if realized_r is not None and float(realized_r) < 0:
                consecutive_losses += 1
            else:
                break
        loss_fraction = realized_loss_amount / equity if equity > 0 else 1.0
        return RiskState(
            equity=equity,
            daily_realized_loss_fraction=min(max(loss_fraction, 0.0), 1.0),
            daily_committed_risk_fraction=min(max(committed, 0.0), 1.0),
            consecutive_losses=consecutive_losses,
            open_positions=len(open_rows),
            total_exposure_fraction=min(max(committed, 0.0), 1.0),
            correlated_exposure_fraction=min(max(correlated, 0.0), 1.0),
        )


    def bind_execution_identity(self, order_id: str, *, order_ticket: int | None = None, deal_ticket: int | None = None, position_ticket: int | None = None, actual_entry: float | None = None, opened_at_utc: datetime | None = None) -> None:
        """Bind durable MT5 ids discovered after order_send without replacing audit history."""
        with self._connect() as conn:
            if order_ticket is not None or deal_ticket is not None:
                conn.execute(
                    "UPDATE orders SET mt5_order_ticket=COALESCE(?,mt5_order_ticket),mt5_deal_ticket=COALESCE(?,mt5_deal_ticket),updated_at_utc=? WHERE order_id=?",
                    (order_ticket, deal_ticket, datetime.now(UTC).isoformat(), order_id),
                )
            trade_id = f"trade:{order_id}"
            row = conn.execute("SELECT trade_id FROM trades WHERE order_id=?", (order_id,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE trades SET mt5_position_ticket=COALESCE(?,mt5_position_ticket),actual_entry=COALESCE(?,actual_entry) WHERE order_id=?",
                    (position_ticket, actual_entry, order_id),
                )
            elif actual_entry is not None:
                conn.execute(
                    "INSERT INTO trades(trade_id,order_id,mt5_position_ticket,opened_at_utc,actual_entry) VALUES(?,?,?,?,?)",
                    (trade_id, order_id, position_ticket, (opened_at_utc or datetime.now(UTC)).isoformat(), actual_entry),
                )

    def open_trade_records(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT t.*,o.mt5_order_ticket,o.mt5_deal_ticket,o.state,o.request_payload_json,o.response_payload_json,
                          p.entry AS planned_entry,p.stop_loss,p.take_profit,p.lot,p.risk_fraction,p.estimated_loss_at_sl,
                          opp.direction
                   FROM trades t JOIN orders o ON o.order_id=t.order_id
                   JOIN trade_plans p ON p.trade_plan_id=o.trade_plan_id
                   JOIN opportunities opp ON opp.opportunity_id=p.opportunity_id
                   WHERE t.closed_at_utc IS NULL ORDER BY t.opened_at_utc"""
            ).fetchall()
        return [dict(r) for r in rows]

    def update_position_mark(self, position_ticket: int, *, mfe: float, mae: float) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT mfe,mae FROM trades WHERE mt5_position_ticket=? AND closed_at_utc IS NULL", (position_ticket,)).fetchone()
            if not row:
                return
            old_mfe = float(row[0] or 0.0); old_mae = float(row[1] or 0.0)
            conn.execute("UPDATE trades SET mfe=?,mae=? WHERE mt5_position_ticket=? AND closed_at_utc IS NULL", (max(old_mfe,mfe), max(old_mae,mae), position_ticket))

    def close_trade(self, position_ticket: int, *, closed_at_utc: datetime, exit_price: float, gross_pnl: float, commission: float, swap: float, net_pnl: float, exit_reason: str, slippage_points: float | None = None) -> None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT t.trade_id,t.actual_entry,p.estimated_loss_at_sl FROM trades t
                   JOIN orders o ON o.order_id=t.order_id JOIN trade_plans p ON p.trade_plan_id=o.trade_plan_id
                   WHERE t.mt5_position_ticket=? AND t.closed_at_utc IS NULL""", (position_ticket,)
            ).fetchone()
            if not row:
                return
            risk_amount = float(row[2] or 0.0)
            realized_r = net_pnl / risk_amount if risk_amount > 0 else None
            conn.execute(
                """UPDATE trades SET closed_at_utc=?,exit_price=?,gross_pnl=?,commission=?,swap=?,net_pnl=?,realized_r=?,slippage_points=?,exit_reason=? WHERE trade_id=?""",
                (closed_at_utc.isoformat(), exit_price, gross_pnl, commission, swap, net_pnl, realized_r, slippage_points, exit_reason, row[0]),
            )

    def paper_close_trade(self, trade_id: str, *, closed_at_utc: datetime, exit_price: float, gross_pnl: float, exit_reason: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT p.estimated_loss_at_sl FROM trades t JOIN orders o ON o.order_id=t.order_id JOIN trade_plans p ON p.trade_plan_id=o.trade_plan_id WHERE t.trade_id=? AND t.closed_at_utc IS NULL""", (trade_id,)
            ).fetchone()
            if not row:
                return
            risk_amount=float(row[0] or 0.0); realized_r=gross_pnl/risk_amount if risk_amount>0 else None
            conn.execute("UPDATE trades SET closed_at_utc=?,exit_price=?,gross_pnl=?,commission=0.0,swap=0.0,net_pnl=?,realized_r=?,exit_reason=? WHERE trade_id=?", (closed_at_utc.isoformat(),exit_price,gross_pnl,gross_pnl,realized_r,exit_reason,trade_id))

    def update_trade_mark(self, trade_id: str, *, mfe: float, mae: float) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT mfe,mae FROM trades WHERE trade_id=? AND closed_at_utc IS NULL", (trade_id,)).fetchone()
            if not row:
                return
            conn.execute("UPDATE trades SET mfe=?,mae=? WHERE trade_id=?", (max(float(row[0] or 0.0),mfe), max(float(row[1] or 0.0),mae), trade_id))
