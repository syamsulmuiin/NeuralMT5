import pytest

from contracts.domain import Direction
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.pricing import round_to_tick
from layer3_execution.sizing import calculate_position_size
from layer3_execution.stops import deterministic_stop
from layer3_execution.targets import deterministic_target, reward_risk


def spec(**overrides):
    data = dict(
        name="XAUUSDm", description="Gold", path="Metals", currency_base="XAU",
        currency_profit="USD", currency_margin="USD", digits=2, point=0.01,
        tick_size=0.01, tick_value=1.0, contract_size=100.0,
        volume_min=0.01, volume_max=100.0, volume_step=0.01,
        stops_level=20, freeze_level=0, trade_mode=4, filling_mode=1,
        execution_mode=2, spread_points=15.0,
    )
    data.update(overrides)
    return BrokerSymbolSpec(**data)


def test_tick_rounding_is_deterministic():
    assert round_to_tick(1.234, 0.01, mode="down") == 1.23
    assert round_to_tick(1.234, 0.01, mode="up") == 1.24


def test_buy_sl_tp_and_rr():
    s = spec()
    sl = deterministic_stop(direction=Direction.BUY, entry=2000.0, atr=1.0,
                            structure_level=1998.5, spec=s, atr_multiplier=1.2)
    tp = deterministic_target(direction=Direction.BUY, entry=2000.0, stop_loss=sl,
                              atr=1.0, structure_target=None, spec=s,
                              atr_multiplier=1.8, min_rr=1.5)
    assert sl < 2000 < tp
    assert reward_risk(2000.0, sl, tp) >= 1.5


def test_sell_sl_tp_and_rr():
    s = spec()
    sl = deterministic_stop(direction=Direction.SELL, entry=2000.0, atr=1.0,
                            structure_level=2001.5, spec=s, atr_multiplier=1.2)
    tp = deterministic_target(direction=Direction.SELL, entry=2000.0, stop_loss=sl,
                              atr=1.0, structure_target=None, spec=s,
                              atr_multiplier=1.8, min_rr=1.5)
    assert tp < 2000 < sl
    assert reward_risk(2000.0, sl, tp) >= 1.5


def test_position_size_uses_tick_value_and_step():
    s = spec(tick_size=0.01, tick_value=1.0, volume_step=0.01)
    result = calculate_position_size(equity=10_000, risk_fraction=0.005,
                                     entry=2000, stop_loss=1999, spec=s)
    assert result.loss_per_lot_at_sl == pytest.approx(100.0)
    assert result.normalized_lot == pytest.approx(0.5)
    assert result.estimated_loss_at_sl == pytest.approx(50.0)


def test_minimum_lot_that_breaks_budget_is_rejected():
    s = spec(volume_min=1.0, volume_step=1.0)
    with pytest.raises(ValueError, match="minimum volume"):
        calculate_position_size(equity=1000, risk_fraction=0.001,
                                entry=2000, stop_loss=1999, spec=s)
