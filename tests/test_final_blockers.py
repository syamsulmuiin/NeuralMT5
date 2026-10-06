from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

from config.settings import Settings
from config.validation import validate_settings
from contracts.domain import Direction
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.models import MarketQuote, PlannedTrade
from layer3_execution.preflight import execution_preflight
from layer3_execution.reconciliation import execution_identity_from_mt5, closed_position_outcome_from_mt5
from layer3_execution.mt5_execution_adapter import MT5ExecutionAdapter
from live_readiness.audit import audit_clock
from runtime.store import RuntimeStore


def _spec(**kw):
    base=dict(name="EURUSDm", digits=5, point=0.00001, tick_size=0.00001, tick_value=1.0,
              contract_size=100000, volume_min=0.01, volume_max=100, volume_step=0.01,
              stops_level=0, freeze_level=0, trade_mode=4, filling_mode=1, execution_mode=2,
              spread_points=10, currency_base="EUR", currency_profit="USD")
    base.update(kw); return BrokerSymbolSpec(**base)


def test_deal_history_resolves_position_identity():
    deal=SimpleNamespace(ticket=55, order=44, position_id=33, price=1.2345, volume=0.2, time=1_700_000_000)
    class B:
        def history_deals_get(self, **kwargs): return (deal,)
    x=execution_identity_from_mt5(B(),order_ticket=None,deal_ticket=55)
    assert (x.order_ticket,x.deal_ticket,x.position_ticket)==(44,55,33)
    assert x.price==pytest.approx(1.2345)


def test_closed_position_outcome_accounts_costs():
    ds=(SimpleNamespace(ticket=1,time=100,price=1.0,profit=0,commission=-1,swap=0,fee=0,reason=0),
        SimpleNamespace(ticket=2,time=200,price=1.1,profit=20,commission=-1,swap=-.5,fee=-.2,reason=5))
    class B:
        def history_deals_get(self, **kwargs): return ds
    x=closed_position_outcome_from_mt5(B(),9)
    assert x is not None and x.exit_price==1.1
    assert x.net_pnl==pytest.approx(17.3)


def test_freeze_level_is_enforced_in_preflight():
    now=datetime(2026,1,1,12,tzinfo=UTC)
    spec=_spec(point=0.01,tick_size=0.01,freeze_level=10,digits=2)
    plan=PlannedTrade(client_order_key="x",symbol=spec.name,direction=Direction.BUY,planned_at_utc=now,
        entry=100,stop_loss=99.95,take_profit=101,rr=20,sl_distance=.05,tp_distance=1,lot=.1,
        estimated_loss_at_sl=10,risk_fraction=.001)
    q=MarketQuote(symbol=spec.name,timestamp_utc=now,bid=99.99,ask=100,spread_points=1)
    r=execution_preflight(plan=plan,refreshed_quote=q,spec=spec,settings=Settings(_env_file=None),now_utc=now)
    assert not r.allowed and any("stops level" in reason for reason in r.reasons)


def test_broker_symbol_filling_capability_maps_to_order_enum():
    class B:
        SYMBOL_FILLING_FOK=1; SYMBOL_FILLING_IOC=2; ORDER_FILLING_FOK=0; ORDER_FILLING_IOC=1; ORDER_FILLING_RETURN=2
        SYMBOL_TRADE_EXECUTION_MARKET=2
    a=MT5ExecutionAdapter(B(),_spec(filling_mode=1,execution_mode=2),Settings(_env_file=None))
    assert a._filling_type()==0


def test_clock_skew_readiness_is_real_check():
    class B:
        def symbol_info_tick(self, symbol): return SimpleNamespace(time=int((datetime.now(UTC)-timedelta(minutes=5)).timestamp()))
    checks=audit_clock(Settings(_env_file=None,live_max_clock_skew_seconds=30),B(),[_spec()])
    assert not checks[0].passed


def test_timezone_validation_rejects_unknown_zone():
    with pytest.raises(ValueError,match="TRADING_TIMEZONE"):
        validate_settings(Settings(_env_file=None,trading_timezone="Mars/Olympus"))


def test_correlated_exposure_uses_currency_overlap_not_total(tmp_path: Path):
    store=RuntimeStore(tmp_path/"r.db")
    with sqlite3.connect(store.path) as c:
        c.execute("INSERT INTO trade_plans VALUES(?,?,?,?,?,?,?,?,?,?)",("p","o",1,0.9,1.2,2,.01,.1,100,datetime.now(UTC).isoformat()))
        c.execute("INSERT INTO orders(order_id,trade_plan_id,client_order_key,state,requested_at_utc,updated_at_utc,request_payload_json) VALUES(?,?,?,?,?,?,?)",("ord","p","k","FILLED",datetime.now(UTC).isoformat(),datetime.now(UTC).isoformat(),'{"symbol":"EURUSDm"}'))
        c.execute("INSERT INTO trades(trade_id,order_id,opened_at_utc,actual_entry) VALUES(?,?,?,?)",("t","ord",datetime.now(UTC).isoformat(),1.0))
    mapping={"EURUSDm":{"EUR","USD"}}
    a=store.current_risk_state(10000,candidate_currencies={"XAU","USD"},symbol_currencies=mapping)
    b=store.current_risk_state(10000,candidate_currencies={"GBP","JPY"},symbol_currencies=mapping)
    assert a.correlated_exposure_fraction==pytest.approx(.01)
    assert b.correlated_exposure_fraction==0

def test_historical_backtest_runs_production_pipeline_without_future_entry():
    import torch
    from layer1_market.models import Candle
    from layer2_brain.scaler import StandardScalerArtifact
    from layer4_learning.backtest import run_historical_pipeline
    features=("open","high","low","close","return_1","log_return_1","range","body","upper_wick","lower_wick","tick_volume","spread_points","atr","momentum","realized_volatility","tick_volume_ratio","spread_ratio")
    class Hold:
        def eval(self): return self
        def __call__(self,h,m,l):
            return {"probabilities":torch.tensor([[.05,.05,.90]]),"quality":torch.tensor([[.5,.5]]),"excursion":torch.tensor([[1.,.5]])}
    start=datetime(2026,1,1,tzinfo=UTC); candles=[]
    for i in range(100):
        p=1.10+i*.0001
        candles.append(Candle(time_utc=start+timedelta(minutes=i),open=p,high=p+.0002,low=p-.0002,close=p+.00005,tick_volume=100+i,spread_points=10))
    s=Settings(_env_file=None,htf="M1",mtf="M1",ltf="M1",htf_window=32,mtf_window=32,ltf_window=32)
    sc=StandardScalerArtifact(features,tuple(0.0 for _ in features),tuple(1.0 for _ in features),"s")
    result=run_historical_pipeline(canonical_symbol="EURUSD",spec=_spec(name="EURUSD"),candles_by_timeframe={"M1":tuple(candles)},model=Hold(),scaler=sc,settings=s)
    assert result.trades==()
    assert result.metrics.trades==0


def test_challenger_lifecycle_registers_but_never_promotes(tmp_path: Path):
    from layer4_learning.lifecycle import run_challenger_lifecycle
    from layer4_learning.models import PerformanceMetrics
    RuntimeStore(tmp_path/"m.db")
    metrics=PerformanceMetrics(20,.2,2.0,.5,4.0,.6)
    artifact=dict(network_version="n",feature_version="f",scaler_version="s",dataset_version="d",weights_hash="w",scaler_hash="sh",dataset_hash="dh",config_hash="c",random_seed=42)
    result=run_challenger_lifecycle(db_path=tmp_path/"m.db",train=lambda:object(),evaluate=lambda _:metrics,champion_metrics=None,challenger_shadow_scores=[1,1,0],champion_shadow_scores=[0,1,1],min_trades=10,max_drawdown=1,min_expectancy_r=0,artifact=artifact)
    assert result.ready_for_manual_promotion
    with sqlite3.connect(tmp_path/"m.db") as c:
        assert c.execute("SELECT role FROM model_artifacts WHERE artifact_id=?",(result.artifact_id,)).fetchone()[0]=="CHALLENGER"
        assert c.execute("SELECT COUNT(*) FROM model_artifacts WHERE role='CHAMPION'").fetchone()[0]==0
