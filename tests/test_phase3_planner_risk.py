from datetime import UTC, datetime

import pytest

from config.settings import Settings
from contracts.domain import Direction
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.models import MarketQuote, RiskState
from layer3_execution.risk import risk_firewall
from layer3_execution.trade_planner import plan_trade


def spec():
    return BrokerSymbolSpec(
        name="EURUSD.vx", description="Euro vs Dollar", path="Forex", currency_base="EUR",
        currency_profit="USD", currency_margin="EUR", digits=5, point=0.00001,
        tick_size=0.00001, tick_value=1.0, contract_size=100000,
        volume_min=0.01, volume_max=50, volume_step=0.01, stops_level=20,
        freeze_level=10, trade_mode=4, filling_mode=1, execution_mode=2,
        spread_points=10,
    )


def settings(**kwargs):
    return Settings(_env_file=None, **kwargs)


def test_plan_uses_buy_ask_and_has_sl_before_execution():
    q = MarketQuote(symbol="EURUSD.vx", timestamp_utc=datetime.now(UTC),
                    bid=1.10000, ask=1.10010, spread_points=10)
    p = plan_trade(direction=Direction.BUY, quote=q, spec=spec(), equity=10_000,
                   atr=0.001, structure_stop=1.0980, structure_target=None,
                   decision_id="abc", settings=settings())
    assert p.entry == q.ask
    assert p.stop_loss < p.entry < p.take_profit
    assert p.rr >= 1.5
    assert p.client_order_key


def test_same_decision_has_same_idempotency_key():
    q = MarketQuote(symbol="EURUSD.vx", timestamp_utc=datetime.now(UTC),
                    bid=1.10000, ask=1.10010, spread_points=10)
    args = dict(direction=Direction.BUY, quote=q, spec=spec(), equity=10_000,
                atr=0.001, structure_stop=None, structure_target=None,
                decision_id="same", settings=settings())
    assert plan_trade(**args).client_order_key == plan_trade(**args).client_order_key


def test_risk_firewall_vetoes_daily_loss_even_for_valid_plan():
    q = MarketQuote(symbol="EURUSD.vx", timestamp_utc=datetime.now(UTC),
                    bid=1.1, ask=1.1001, spread_points=10)
    p = plan_trade(direction=Direction.BUY, quote=q, spec=spec(), equity=10_000,
                   atr=0.001, structure_stop=None, structure_target=None,
                   decision_id="risk", settings=settings())
    state = RiskState(equity=10_000, daily_realized_loss_fraction=0.02,
                      daily_committed_risk_fraction=0, consecutive_losses=0,
                      open_positions=0, total_exposure_fraction=0,
                      correlated_exposure_fraction=0)
    r = risk_firewall(plan=p, quote=q, state=state, settings=settings())
    assert not r.allowed
    assert "daily loss limit reached" in r.reasons


def test_risk_firewall_allows_clean_state():
    q = MarketQuote(symbol="EURUSD.vx", timestamp_utc=datetime.now(UTC),
                    bid=1.1, ask=1.1001, spread_points=10)
    p = plan_trade(direction=Direction.SELL, quote=q, spec=spec(), equity=10_000,
                   atr=0.001, structure_stop=None, structure_target=None,
                   decision_id="ok", settings=settings())
    state = RiskState(equity=10_000, daily_realized_loss_fraction=0,
                      daily_committed_risk_fraction=0, consecutive_losses=0,
                      open_positions=0, total_exposure_fraction=0,
                      correlated_exposure_fraction=0)
    assert risk_firewall(plan=p, quote=q, state=state, settings=settings()).allowed
