from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3

from .models import ObservationRecord, OutcomeLabel


class Journal:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            schema = Path(__file__).parents[1] / "storage/database/schema.sql"
            schema_sql = schema.read_text(encoding="utf-8")
            with self._connect() as conn:
                conn.executescript(schema_sql)
        except (OSError, RuntimeError) as exc:
            raise RuntimeError(f"failed to initialize journal {self.db_path}: {exc}") from exc

    @contextmanager
    def _connect(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
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
            raise RuntimeError(f"journal database operation failed ({self.db_path}): {exc}") from exc
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

    def append_observation(self, r: ObservationRecord, broker_symbol: str, htf: str, mtf: str, ltf: str) -> None:
        now = datetime.now(UTC).isoformat()
        try:
            payload = json.dumps(r.features, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"failed to serialize observation {r.observation_id}: {exc}") from exc
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO observations(
                    observation_id,symbol,broker_symbol,observed_at_utc,timeframe_htf,timeframe_mtf,timeframe_ltf,
                    feature_version,dataset_version,feature_payload_json,label_payload_json,created_at_utc
                ) VALUES(?,?,?,?,?,?,?,?,?,?,NULL,?)""",
                (r.observation_id, r.symbol, broker_symbol, r.observed_at_utc.isoformat(), htf, mtf, ltf,
                 r.feature_version, r.dataset_version, payload, now),
            )

    def attach_label_once(self, observation_id: str, label: OutcomeLabel) -> None:
        try:
            payload = json.dumps({**label.__dict__, "horizon_end_utc": label.horizon_end_utc.isoformat()}, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"failed to serialize label for {observation_id}: {exc}") from exc
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE observations SET label_payload_json=? WHERE observation_id=? AND label_payload_json IS NULL",
                (payload, observation_id),
            )
            if cur.rowcount != 1:
                raise ValueError("observation missing or already labeled")

    def has_observation(self, observation_id: str) -> bool:
        with self._connect() as conn:
            return conn.execute("SELECT 1 FROM observations WHERE observation_id=?", (observation_id,)).fetchone() is not None
