from pathlib import Path
from types import SimpleNamespace
import pytest

from config.settings import Settings
from config.validation import validate_settings
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.executor import execute_plan
from layer3_execution.idempotency import OrderRegistry
from layer3_execution.models import ExecutionState, PlannedTrade, PreflightResult
from layer3_execution.mt5_execution_adapter import MT5ExecutionAdapter
from contracts.domain import Direction
from datetime import UTC, datetime
from live_readiness.audit import audit_terminal, audit_symbols


def live_settings(**kw):
    v=dict(trading_mode='live', mt5_login='1', mt5_password='x', mt5_server='broker')
    v.update(kw); return Settings(_env_file=None, **v)

def test_live_default_remains_blocked():
    with pytest.raises(ValueError, match='LIVE_EXECUTION_ENABLED'):
        validate_settings(live_settings())

def test_live_requires_host_attestations():
    with pytest.raises(ValueError, match='fault-injection'):
        validate_settings(live_settings(live_execution_enabled=True, live_readiness_acknowledged=True))

def test_live_config_can_pass_only_with_explicit_gates():
    s=live_settings(live_execution_enabled=True, live_readiness_acknowledged=True, live_fault_injection_passed=True, live_soak_test_passed=True)
    assert validate_settings(s) is s

def spec():
    return BrokerSymbolSpec(name='EURUSD', digits=5, point=1e-5, tick_size=1e-5, tick_value=1, contract_size=100000, volume_min=.01, volume_max=100, volume_step=.01, stops_level=10, freeze_level=0, trade_mode=4, filling_mode=1, execution_mode=2, spread_points=10)

class MT5:
    ORDER_TYPE_BUY=0; ORDER_TYPE_SELL=1; TRADE_ACTION_DEAL=1; ORDER_TIME_GTC=0; TRADE_RETCODE_DONE=10009; TRADE_RETCODE_DONE_PARTIAL=10010; TRADE_RETCODE_PLACED=10008
    def order_check(self,r): return SimpleNamespace(retcode=0, comment='ok')
    def order_send(self,r): return SimpleNamespace(retcode=10010, order=7, deal=8, volume=.04, price=r['price'], comment='partial')
    def last_error(self): return (0,'ok')

def test_partial_fill_is_explicit(tmp_path):
    s=Settings(_env_file=None); adapter=MT5ExecutionAdapter(MT5(), spec(), s)
    plan=PlannedTrade(client_order_key='k', symbol='EURUSD', direction=Direction.BUY, planned_at_utc=datetime.now(UTC), entry=1.1, stop_loss=1.09, take_profit=1.12, rr=2, sl_distance=.01, tp_distance=.02, lot=.1, estimated_loss_at_sl=100, risk_fraction=.01)
    result=execute_plan(plan=plan, preflight=PreflightResult(allowed=True), mode=__import__('config.settings',fromlist=['TradingMode']).TradingMode.LIVE, registry=OrderRegistry(tmp_path/'x.db'), backend=adapter)
    assert result.state is ExecutionState.PARTIALLY_FILLED
    assert result.filled_volume == .04

def test_terminal_permissions_are_a_readiness_gate():
    backend=SimpleNamespace(terminal_info=lambda:SimpleNamespace(connected=True,trade_allowed=False), account_info=lambda:SimpleNamespace(trade_allowed=True))
    checks=audit_terminal(Settings(_env_file=None), backend)
    assert not next(c for c in checks if c.name=='terminal_trade_allowed').passed

def test_symbol_execution_spec_requires_positive_tick_value():
    bad=spec().model_copy(update={'tick_value':0.0})
    assert not audit_symbols([bad])[0].passed


def test_runtime_live_gate_requires_runtime_readiness(tmp_path):
    from runtime.orchestrator import NeuralMT5Runtime
    from layer1_market.mt5_client import MT5Client
    class B:
        def terminal_info(self): return SimpleNamespace(connected=True, trade_allowed=True)
        def account_info(self): return SimpleNamespace(trade_allowed=True, login=1, server='x', currency='USD', balance=1, equity=1, margin=0, margin_free=1)
    s=live_settings(live_execution_enabled=True, live_readiness_acknowledged=True, live_fault_injection_passed=True, live_soak_test_passed=True, database_url=f"sqlite:///{tmp_path/'x.db'}")
    # Constructor is allowed only after config gates; start-time audit will additionally require real artifacts/broker state.
    class M: pass
    r=NeuralMT5Runtime(s, client=MT5Client(B()), model=M(), scaler=M())
    assert r.settings.trading_mode.value == 'live'
