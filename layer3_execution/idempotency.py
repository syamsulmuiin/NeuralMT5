from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class DuplicateOrderError(RuntimeError):
    pass


class OrderRegistry:
    """Durable idempotency registry. Claim must succeed before any order_send call."""
    def __init__(self, database_path: str | Path) -> None:
        self.path = str(database_path)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS execution_claims (
                client_order_key TEXT PRIMARY KEY,
                claimed_at_utc TEXT NOT NULL,
                state TEXT NOT NULL
            )""")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def claim(self, key: str, timestamp_utc: str) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO execution_claims(client_order_key,claimed_at_utc,state) VALUES(?,?,?)",
                    (key, timestamp_utc, "CLAIMED"),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateOrderError(f"duplicate client_order_key: {key}") from exc

    def update_state(self, key: str, state: str) -> None:
        with self._connect() as conn:
            cur = conn.execute("UPDATE execution_claims SET state=? WHERE client_order_key=?", (state, key))
            if cur.rowcount != 1:
                raise KeyError(key)

    def state(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT state FROM execution_claims WHERE client_order_key=?", (key,)).fetchone()
        return row[0] if row else None
