from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import torch

from config.settings import Settings
from dashboard.commands import CommandGateway
from dashboard.schemas import CommandRequest, CommandType, RuntimeMode
from dashboard.state import RuntimeState
from dashboard.websocket import EventBus
from layer1_market.mt5_client import MT5Client
from layer2_brain.scaler import StandardScalerArtifact
from runtime.orchestrator import NeuralMT5Runtime
from runtime.worker import IsolatedWorker


FEATURES = (
    "open", "high", "low", "close", "return_1", "log_return_1", "range", "body",
    "upper_wick", "lower_wick", "tick_volume", "spread_points", "atr", "momentum",
    "realized_volatility", "tick_volume_ratio", "spread_ratio",
)


class HoldModel:
    def eval(self):
        return self

    def __call__(self, htf, mtf, ltf):
        return {
            "probabilities": torch.tensor([[0.05, 0.05, 0.90]], dtype=torch.float32),
            "quality": torch.tensor([[0.5, 0.5]], dtype=torch.float32),
            "excursion": torch.tensor([[1.0, 0.5]], dtype=torch.float32),
        }


class FakeBackend:
    TIMEFRAME_M15 = 15
    TIMEFRAME_M5 = 5
    TIMEFRAME_M1 = 1

    def __init__(self):
        self.initialized = False

    def initialize(self, **kwargs):
        self.initialized = True
        return True

    def shutdown(self):
        self.initialized = False

    def last_error(self):
        return (0, "ok")

    def terminal_info(self):
        return SimpleNamespace(connected=True)

    def account_info(self):
        return SimpleNamespace(login=1, server="test", currency="USD", balance=10000.0, equity=10000.0, margin=0.0, margin_free=10000.0)

    def symbols_get(self):
        return [SimpleNamespace(
            name="XAUUSDm", description="Gold vs US Dollar", path="Metals\\XAUUSD",
            currency_base="XAU", currency_profit="USD", currency_margin="USD",
            digits=2, point=0.01, trade_tick_size=0.01, trade_tick_value=1.0,
            trade_contract_size=100.0, volume_min=0.01, volume_max=100.0, volume_step=0.01,
            trade_stops_level=10, trade_freeze_level=0, trade_mode=4, filling_mode=1,
            trade_exemode=2, spread=20, visible=True,
        )]

    def symbol_info(self, symbol):
        return self.symbols_get()[0]

    def symbol_select(self, symbol, enable):
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=int(time.time()), bid=2350.00, ask=2350.20)

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        step = int(timeframe) * 60
        end = int(time.time()) - step * 2
        rows = []
        base = 2300.0
        for i in range(count):
            t = end - step * (count - 1 - i)
            price = base + i * 0.1
            rows.append({"time": t, "open": price, "high": price + 0.3, "low": price - 0.2, "close": price + 0.1, "tick_volume": 100 + i, "spread": 20})
        return rows

    def positions_get(self):
        return ()


class RetryBackend(FakeBackend):
    def __init__(self):
        super().__init__()
        self.attempts = 0

    def initialize(self, **kwargs):
        self.attempts += 1
        if self.attempts < 3:
            return False
        return super().initialize(**kwargs)


def settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(
        trading_mode="analysis", symbols=["XAUUSD"], htf_window=32, mtf_window=32, ltf_window=32,
        database_url=f"sqlite:///{tmp_path / 'runtime.db'}", dashboard_enabled=False,
        min_symbol_resolution_confidence=0.90, runtime_loop_seconds=0.001,
        mt5_reconnect_attempts=3, mt5_reconnect_delay_seconds=0.0,
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


def scaler() -> StandardScalerArtifact:
    return StandardScalerArtifact(FEATURES, tuple(0.0 for _ in FEATURES), tuple(1.0 for _ in FEATURES), "test-scaler")


def test_closed_loop_analysis_persists_observation_and_hold(tmp_path):
    runtime = NeuralMT5Runtime(settings(tmp_path), client=MT5Client(FakeBackend()), model=HoldModel(), scaler=scaler(), sleep_fn=lambda _: None)
    runtime.start()
    result = runtime.run_once()
    assert result.errors == 0
    assert result.processed_symbols == 1
    assert result.holds == 1
    import sqlite3
    with sqlite3.connect(tmp_path / "runtime.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0] == 1
        assert conn.execute("SELECT direction FROM opportunities").fetchone()[0] == "HOLD"
    runtime.stop()


def test_connect_retry_is_bounded(tmp_path):
    backend = RetryBackend()
    runtime = NeuralMT5Runtime(settings(tmp_path), client=MT5Client(backend), model=HoldModel(), scaler=scaler(), sleep_fn=lambda _: None)
    runtime.start()
    assert backend.attempts == 3
    runtime.stop()


def test_phase6_blocks_live_even_with_credentials(tmp_path):
    s = settings(tmp_path, trading_mode="live", mt5_login="1", mt5_password="secret", mt5_server="broker")
    import pytest
    with pytest.raises(PermissionError, match="Phase 7"):
        NeuralMT5Runtime(s, client=MT5Client(FakeBackend()), model=HoldModel(), scaler=scaler())


def test_live_dashboard_command_cannot_switch_phase6_runtime(tmp_path):
    state = RuntimeState(mode=RuntimeMode.ANALYSIS)
    gateway = CommandGateway(state)
    runtime = NeuralMT5Runtime(settings(tmp_path), client=MT5Client(FakeBackend()), model=HoldModel(), scaler=scaler(), runtime_state=state, command_gateway=gateway)
    receipt = gateway.submit(CommandRequest(command=CommandType.SET_MODE, mode=RuntimeMode.LIVE, explicit_confirmation=True))
    assert receipt.accepted
    runtime._process_commands()
    assert state.mode is RuntimeMode.ANALYSIS
    assert "Phase 7" in (state.last_error or "")


def test_event_bus_supports_threadsafe_runtime_publish():
    async def scenario():
        from contracts.events import EventType, SystemEvent
        bus = EventBus()
        queue = await bus.subscribe()
        event = SystemEvent(event_type=EventType.SYSTEM_WARNING, occurred_at_utc=datetime.now(UTC), source="test")
        bus.publish_threadsafe(event)
        received = await asyncio.wait_for(queue.get(), timeout=1)
        assert received.event_id == event.event_id
        await bus.unsubscribe(queue)
    asyncio.run(scenario())


def test_learning_worker_contains_job_failure():
    worker = IsolatedWorker()
    done = __import__("threading").Event()
    worker.start()
    worker.submit(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    worker.submit(done.set)
    assert done.wait(1.0)
    worker.stop()


class BuyModel:
    def eval(self):
        return self

    def __call__(self, htf, mtf, ltf):
        return {
            "probabilities": torch.tensor([[0.90, 0.05, 0.05]], dtype=torch.float32),
            "quality": torch.tensor([[0.9, 0.9]], dtype=torch.float32),
            "excursion": torch.tensor([[2.0, 0.5]], dtype=torch.float32),
        }


def test_paper_mode_runs_planning_risk_preflight_and_persists_fill(tmp_path):
    s = settings(
        tmp_path, trading_mode="paper", min_brainflow_score=0.10, min_confidence=0.50,
        min_direction_score=0.60, min_direction_margin=0.15, max_spread_points=100.0,
        max_slippage_points=100.0, no_new_entry_after="23:59",
    )
    runtime = NeuralMT5Runtime(s, client=MT5Client(FakeBackend()), model=BuyModel(), scaler=scaler(), sleep_fn=lambda _: None)
    runtime.start()
    result = runtime.run_once()
    assert result.errors == 0
    assert result.executed == 1
    import sqlite3
    with sqlite3.connect(tmp_path / "runtime.db") as conn:
        assert conn.execute("SELECT state FROM orders").fetchone()[0] == "PAPER_FILLED"
        assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 1
    runtime.stop()


def test_multi_cycle_soak_keeps_runtime_healthy(tmp_path):
    runtime = NeuralMT5Runtime(settings(tmp_path), client=MT5Client(FakeBackend()), model=HoldModel(), scaler=scaler(), sleep_fn=lambda _: None)
    runtime.start()
    runtime.run(max_cycles=25)
    import sqlite3
    with sqlite3.connect(tmp_path / "runtime.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM runtime_cycles").fetchone()[0] == 25
        assert conn.execute("SELECT COUNT(*) FROM runtime_cycles WHERE status='OK'").fetchone()[0] == 25
    assert runtime.state.last_error is None
    runtime.stop()


def test_paper_position_monitor_can_resolve_persisted_symbol_and_close(tmp_path):
    backend = FakeBackend()
    s = settings(
        tmp_path, trading_mode="paper", min_brainflow_score=0.10, min_confidence=0.50,
        min_direction_score=0.60, min_direction_margin=0.15, max_spread_points=100.0,
        max_slippage_points=100.0, no_new_entry_after="23:59",
    )
    runtime = NeuralMT5Runtime(s, client=MT5Client(backend), model=BuyModel(), scaler=scaler(), sleep_fn=lambda _: None)
    runtime.start()
    first = runtime.run_once()
    assert first.executed == 1
    original_tick = backend.symbol_info_tick
    backend.symbol_info_tick = lambda symbol: SimpleNamespace(time=int(time.time()), bid=9999.0, ask=9999.2)
    runtime._maintain_positions()
    import sqlite3
    with sqlite3.connect(tmp_path / "runtime.db") as conn:
        row = conn.execute("SELECT closed_at_utc,exit_reason FROM trades ORDER BY opened_at_utc LIMIT 1").fetchone()
        assert row[0] is not None
        assert row[1] == "TP"
    backend.symbol_info_tick = original_tick
    runtime.stop()
