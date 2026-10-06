from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from config.settings import Settings, TradingMode
from contracts.domain import Direction
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.executor import execute_plan
from layer3_execution.idempotency import DuplicateOrderError, OrderRegistry
from layer3_execution.models import MarketQuote, PlannedTrade, PreflightResult, ExecutionState
from layer3_execution.preflight import execution_preflight


def spec():
    return BrokerSymbolSpec(name="XAUUSDm", digits=2, point=0.01, tick_size=0.01,
        tick_value=1, contract_size=100, volume_min=0.01, volume_max=100,
        volume_step=0.01, stops_level=10, freeze_level=0, trade_mode=4,
        filling_mode=1, execution_mode=2, spread_points=10)


def plan():
    return PlannedTrade(client_order_key="key-1", symbol="XAUUSDm", direction=Direction.BUY,
        planned_at_utc=datetime(2026, 1, 1, 10, 0, tzinfo=UTC), entry=2000.10,
        stop_loss=1998.0, take_profit=2003.30, rr=3.2/2.1,
        sl_distance=2.1, tp_distance=3.2, lot=0.1,
        estimated_loss_at_sl=21, risk_fraction=0.0021)


def test_preflight_rejects_excess_slippage():
    q = MarketQuote(symbol="XAUUSDm", timestamp_utc=datetime.now(UTC),
                    bid=2001.0, ask=2001.1, spread_points=10)
    s = Settings(_env_file=None, max_slippage_points=20)
    r = execution_preflight(plan=plan(), refreshed_quote=q, spec=spec(), settings=s,
                            now_utc=datetime(2026,1,1,10,1,tzinfo=UTC))
    assert not r.allowed
    assert "slippage limit exceeded" in r.reasons


def test_analysis_mode_never_calls_backend(tmp_path):
    class Backend:
        called = False
        def order_send(self, request):
            self.called = True
            raise AssertionError("must not execute")
    b = Backend()
    registry = OrderRegistry(tmp_path / "orders.db")
    result = execute_plan(plan=plan(), preflight=PreflightResult(allowed=True),
                          mode=TradingMode.ANALYSIS, registry=registry, backend=b)
    assert result.state is ExecutionState.PREFLIGHT_REJECTED
    assert not b.called


def test_paper_mode_does_not_call_backend(tmp_path):
    class Backend:
        def order_send(self, request):
            raise AssertionError("paper must not call broker")
    result = execute_plan(plan=plan(), preflight=PreflightResult(allowed=True),
                          mode=TradingMode.PAPER, registry=OrderRegistry(tmp_path / "p.db"),
                          backend=Backend())
    assert result.state is ExecutionState.PAPER_FILLED


def test_duplicate_order_is_blocked_durably(tmp_path):
    registry = OrderRegistry(tmp_path / "d.db")
    execute_plan(plan=plan(), preflight=PreflightResult(allowed=True),
                 mode=TradingMode.PAPER, registry=registry)
    with pytest.raises(DuplicateOrderError):
        execute_plan(plan=plan(), preflight=PreflightResult(allowed=True),
                     mode=TradingMode.PAPER, registry=registry)


def test_live_order_has_sl_and_tp_in_same_request(tmp_path):
    class Backend:
        request = None
        def order_send(self, request):
            self.request = request
            return SimpleNamespace(order=12345, retcode=10009)
    b = Backend()
    result = execute_plan(plan=plan(), preflight=PreflightResult(allowed=True),
                          mode=TradingMode.LIVE, registry=OrderRegistry(tmp_path / "l.db"),
                          backend=b)
    assert result.state is ExecutionState.SENT
    assert b.request["sl"] == plan().stop_loss
    assert b.request["tp"] == plan().take_profit
