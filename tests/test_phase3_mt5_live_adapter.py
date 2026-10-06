from types import SimpleNamespace

import pytest

from config.settings import Settings
from layer1_market.models import BrokerSymbolSpec
from layer3_execution.mt5_execution_adapter import MT5ExecutionAdapter


def spec():
    return BrokerSymbolSpec(name="EURUSDm", digits=5, point=0.00001, tick_size=0.00001,
        tick_value=1, contract_size=100000, volume_min=0.01, volume_max=100,
        volume_step=0.01, stops_level=10, freeze_level=0, trade_mode=4,
        filling_mode=1, execution_mode=2, spread_points=10)


class FakeMT5:
    ORDER_TYPE_BUY=0
    ORDER_TYPE_SELL=1
    TRADE_ACTION_DEAL=1
    ORDER_TIME_GTC=0
    TRADE_RETCODE_DONE=10009
    TRADE_RETCODE_DONE_PARTIAL=10010
    TRADE_RETCODE_PLACED=10008
    sent=None
    check_retcode=0
    send_retcode=10009
    def order_check(self, request):
        self.checked=request
        return SimpleNamespace(retcode=self.check_retcode, comment="check")
    def order_send(self, request):
        self.sent=request
        return SimpleNamespace(retcode=self.send_retcode, order=777, price=request["price"], comment="send")
    def last_error(self):
        return (0,"ok")


def generic(direction="BUY"):
    return dict(symbol="EURUSDm", volume=0.1, price=1.1001, sl=1.0980, tp=1.1040,
                direction=direction, client_order_key="abc")


def test_native_request_includes_sl_tp_and_broker_filling():
    mt5=FakeMT5()
    adapter=MT5ExecutionAdapter(mt5, spec(), Settings(_env_file=None))
    result=adapter.order_send(generic())
    assert result.order == 777
    assert mt5.sent["sl"] == 1.0980
    assert mt5.sent["tp"] == 1.1040
    assert mt5.sent["type_filling"] == spec().filling_mode
    assert mt5.sent["magic"] == 2601001


def test_order_check_failure_blocks_order_send():
    mt5=FakeMT5(); mt5.check_retcode=10016
    adapter=MT5ExecutionAdapter(mt5, spec(), Settings(_env_file=None))
    with pytest.raises(RuntimeError, match="order_check rejected"):
        adapter.order_send(generic())
    assert mt5.sent is None


def test_order_send_failure_is_not_false_success():
    mt5=FakeMT5(); mt5.send_retcode=10030
    adapter=MT5ExecutionAdapter(mt5, spec(), Settings(_env_file=None))
    with pytest.raises(RuntimeError, match="order_send rejected"):
        adapter.order_send(generic("SELL"))
