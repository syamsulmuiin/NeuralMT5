from pathlib import Path
import json
import sqlite3
import pytest

from layer1_market.mt5_client import MT5Client
from layer2_brain.scaler import StandardScalerArtifact
from utils.error_handling import write_crash_report


class RaisingBackend:
    def initialize(self, **kwargs):
        raise OSError("terminal unavailable")
    def last_error(self):
        return (1, "x")


def test_mt5_initialize_exception_has_operation_context():
    client = MT5Client(RaisingBackend())
    with pytest.raises(ConnectionError, match="MT5 initialize raised"):
        client.connect()


def test_corrupt_scaler_has_artifact_context(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="failed to load scaler artifact"):
        StandardScalerArtifact.load(path)


def test_crash_report_is_best_effort_and_contains_context(tmp_path):
    try:
        raise ValueError("boom")
    except ValueError as exc:
        path = write_crash_report("unit-test", exc, directory=tmp_path)
    assert path is not None and path.exists()
    text = path.read_text(encoding="utf-8")
    assert "context=unit-test" in text and "ValueError: boom" in text
