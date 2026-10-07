from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class DashboardDataError(RuntimeError):
    pass


class DashboardRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @property
    def available(self) -> bool:
        return self.db_path.exists()

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if not self.available:
            return []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(row) for row in conn.execute(sql, params).fetchall()]
        except sqlite3.Error as exc:
            raise DashboardDataError(f"dashboard database query failed: {exc}") from exc

    def recent_market(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._query("SELECT observation_id,symbol,broker_symbol,observed_at_utc,timeframe_htf,timeframe_mtf,timeframe_ltf,feature_version,dataset_version,feature_payload_json FROM observations ORDER BY observed_at_utc DESC LIMIT ?", (limit,))
        for row in rows:
            row["features"] = _json(row.pop("feature_payload_json"), {})
        return rows

    def recent_brain(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._query("SELECT opportunity_id,observation_id,decided_at_utc,direction,buy_score,sell_score,hold_score,brainflow_score,confidence,risk_decision,rejection_reason,version_payload_json FROM opportunities ORDER BY decided_at_utc DESC LIMIT ?", (limit,))
        for row in rows:
            row["versions"] = _json(row.pop("version_payload_json"), {})
        return rows

    def opportunities(self, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        rows = self._query("SELECT * FROM opportunities ORDER BY decided_at_utc DESC LIMIT ? OFFSET ?", (limit, offset))
        count = self._query("SELECT COUNT(*) AS n FROM opportunities")
        return rows, int(count[0]["n"]) if count else 0

    def positions(self) -> list[dict[str, Any]]:
        return self._query("SELECT * FROM trades WHERE closed_at_utc IS NULL ORDER BY opened_at_utc DESC")

    def trades(self, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        rows = self._query("SELECT * FROM trades ORDER BY opened_at_utc DESC LIMIT ? OFFSET ?", (limit, offset))
        count = self._query("SELECT COUNT(*) AS n FROM trades")
        return rows, int(count[0]["n"]) if count else 0

    def trade_replay(self, trade_id: str) -> dict[str, Any] | None:
        rows = self._query(
            """SELECT t.*, o.mt5_order_ticket,o.client_order_key,o.state AS order_state,o.request_payload_json,o.response_payload_json,
                      p.trade_plan_id,p.entry AS planned_entry,p.stop_loss,p.take_profit,p.rr,p.risk_fraction,p.lot,p.estimated_loss_at_sl,
                      x.opportunity_id,x.direction,x.buy_score,x.sell_score,x.hold_score,x.brainflow_score,x.confidence,x.risk_decision,x.rejection_reason,x.version_payload_json
               FROM trades t
               JOIN orders o ON o.order_id=t.order_id
               JOIN trade_plans p ON p.trade_plan_id=o.trade_plan_id
               JOIN opportunities x ON x.opportunity_id=p.opportunity_id
               WHERE t.trade_id=?""",
            (trade_id,),
        )
        if not rows:
            return None
        row = rows[0]
        for key in ("request_payload_json", "response_payload_json", "version_payload_json"):
            row[key.removesuffix("_json")] = _json(row.pop(key), None)
        return row

    def performance(self) -> dict[str, Any]:
        rows = self._query("SELECT realized_r,net_pnl,mfe,mae,closed_at_utc FROM trades WHERE closed_at_utc IS NOT NULL")
        realized = [float(r["realized_r"]) for r in rows if r["realized_r"] is not None]
        pnl = [float(r["net_pnl"]) for r in rows if r["net_pnl"] is not None]
        wins = sum(1 for x in realized if x > 0)
        losses = sum(1 for x in realized if x < 0)
        gross_win = sum(x for x in pnl if x > 0)
        gross_loss = abs(sum(x for x in pnl if x < 0))
        return {
            "closed_trades": len(rows),
            "wins": wins,
            "losses": losses,
            "win_rate": wins / len(realized) if realized else 0.0,
            "expectancy_r": sum(realized) / len(realized) if realized else 0.0,
            "total_r": sum(realized),
            "net_pnl": sum(pnl),
            "profit_factor": (gross_win / gross_loss) if gross_loss else None,
            "average_mfe": _avg([float(r["mfe"]) for r in rows if r["mfe"] is not None]),
            "average_mae": _avg([float(r["mae"]) for r in rows if r["mae"] is not None]),
        }

    def learning(self) -> dict[str, Any]:
        artifacts = self._query("SELECT artifact_id,role,network_version,feature_version,scaler_version,dataset_version,weights_hash,dataset_hash,config_hash,random_seed,metrics_json,created_at_utc,promoted_at_utc FROM model_artifacts ORDER BY created_at_utc DESC LIMIT 50")
        for row in artifacts:
            row["metrics"] = _json(row.pop("metrics_json"), {})
        audits = self._query("SELECT * FROM promotion_audit ORDER BY occurred_at_utc DESC LIMIT 50")
        return {"artifacts": artifacts, "promotion_audit": audits}

    def risk(self) -> dict[str, Any]:
        latest = self._query("SELECT risk_decision,rejection_reason,COUNT(*) AS count FROM opportunities GROUP BY risk_decision,rejection_reason ORDER BY count DESC")
        return {"decision_counts": latest}

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._query("SELECT * FROM system_events ORDER BY occurred_at_utc DESC LIMIT ?", (limit,))
        for row in rows:
            row["payload"] = _json(row.pop("payload_json"), {})
        return rows


def _json(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
