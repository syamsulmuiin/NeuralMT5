from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import backtest as cli
from contracts.domain import SymbolResolution
from layer1_market.models import BrokerSymbolSpec, Candle
from layer4_learning.models import PerformanceMetrics


def _spec(name: str = "XAUUSD.vx") -> BrokerSymbolSpec:
    return BrokerSymbolSpec(
        name=name, description="Gold", path="Metals", currency_base="XAU", currency_profit="USD",
        currency_margin="USD", digits=2, point=0.01, tick_size=0.01, tick_value=1.0,
        contract_size=100.0, volume_min=0.01, volume_max=100.0, volume_step=0.01,
        stops_level=0, freeze_level=0, trade_mode=4, filling_mode=1, execution_mode=0,
        spread_points=10.0, visible=True, custom=False,
    )


def _candles(n: int = 600) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        Candle(time_utc=start + timedelta(minutes=i), open=2000.0, high=2001.0, low=1999.0, close=2000.5, tick_volume=100.0, spread_points=10.0)
        for i in range(n)
    )


class FakeBackend:
    def symbol_select(self, symbol, enable): return True
    def last_error(self): return (0, "ok")


class FakeClient:
    def __init__(self): self.backend = FakeBackend(); self.connected = False
    def connect(self, **kwargs): self.connected = True
    def shutdown(self): self.connected = False


def test_backtest_cli_writes_reports(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = SimpleNamespace(
        trading_mode="analysis", backtest_history_bars=600, backtest_initial_equity=10000.0,
        symbols=["XAUUSD"], symbol_exclude_tokens=["REPLAY"], min_symbol_resolution_confidence=0.90,
        htf="M15", mtf="M5", ltf="M1", ltf_window=200, atr_period=14, momentum_period=10,
        volatility_period=20, regime_lookback=20, orderflow_lookback=20, structure_pivot_left=2,
        structure_pivot_right=2, mt5_login=None, mt5_password=None, mt5_server=None, mt5_path=None,
        scaler_artifact_path="unused", model_artifact_path="unused", random_seed=42, hidden_size=64, dropout=0.2,
        symbol_override=lambda _: None,
    )
    spec = _spec()
    monkeypatch.setattr(cli, "_load_champion", lambda s: (object(), object(), {"network_version": "v1", "weights_hash": "abc"}))
    monkeypatch.setattr(cli, "MT5Client", FakeClient)
    monkeypatch.setattr(cli, "discover_symbols", lambda client: (spec,))
    monkeypatch.setattr(cli, "inspect_symbol_candidates", lambda *a, **k: [{"broker_symbol": spec.name, "eligible": True, "score": 0.94}])
    monkeypatch.setattr(cli, "resolve_symbol", lambda *a, **k: SymbolResolution(canonical_symbol="XAUUSD", broker_symbol=spec.name, resolution_confidence=0.94, reason="test"))
    monkeypatch.setattr(cli, "fetch_recent_candles", lambda *a, **k: _candles())

    @dataclass(frozen=True)
    class Trade:
        decision_time_utc: datetime
        entry_time_utc: datetime
        exit_time_utc: datetime
        direction: object
        entry: float
        stop_loss: float
        take_profit: float
        exit_price: float
        exit_reason: str
        realized_r: float

    trade = Trade(datetime.now(UTC), datetime.now(UTC), datetime.now(UTC), SimpleNamespace(value="BUY"), 1.0, 0.9, 1.2, 1.2, "TP", 2.0)
    result = SimpleNamespace(metrics=PerformanceMetrics(1, 2.0, float("inf"), 0.0, 2.0, 1.0), trades=(trade,))
    monkeypatch.setattr(cli, "run_historical_pipeline", lambda **kwargs: result)

    report = cli.run_backtest(settings)
    assert report["completed_symbols"] == 1
    assert report["total_trades"] == 1
    assert Path("storage/reports/backtest_report.json").exists()
    assert Path("storage/reports/backtest_trades.csv").exists()


def test_backtest_requires_champion(tmp_path):
    settings = SimpleNamespace(scaler_artifact_path=str(tmp_path / "none.json"), model_artifact_path=str(tmp_path / "none.pt"))
    try:
        cli._load_champion(settings)
    except FileNotFoundError as exc:
        assert "train.py --promote" in str(exc)
    else:
        raise AssertionError("missing Champion must fail closed")
