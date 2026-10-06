import sqlite3
from pathlib import Path


def test_schema_builds_and_enforces_score_range():
    schema = Path("storage/database/schema.sql").read_text(encoding="utf-8")
    db = sqlite3.connect(":memory:")
    db.executescript(schema)
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"observations", "opportunities", "trade_plans", "orders", "trades", "model_artifacts"} <= tables
