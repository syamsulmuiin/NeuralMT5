from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import train
from config.settings import Settings
from training_pipeline import _time_range


def test_time_range_reports_real_utc_period():
    class Item:
        def __init__(self, t):
            self.time_utc = t
    start = datetime(2026, 1, 1, tzinfo=UTC)
    r = _time_range([Item(start), Item(start + timedelta(minutes=5))], attr="time_utc")
    assert r["start_utc"] == start.isoformat()
    assert r["end_utc"] == (start + timedelta(minutes=5)).isoformat()
    assert r["duration_seconds"] == 300


def test_promote_runtime_error_is_friendly_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(train, "validate_settings", lambda _s: Settings(_env_file=None))
    monkeypatch.setattr(train, "promote_existing", lambda _s: (_ for _ in ()).throw(RuntimeError("promotion blocked: validation failed")))
    rc = train.main(["--promote"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "promotion blocked" in captured.err
    assert "python train.py" in captured.err
    assert "Traceback" not in captured.err
