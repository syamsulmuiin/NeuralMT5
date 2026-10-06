from types import SimpleNamespace

import pytest

from layer1_market.broker_discovery import discover_symbols
from layer1_market.mt5_client import MT5Client


class FakeBackend:
    TIMEFRAME_M1 = 1
    def __init__(self, ok=True): self.ok = ok; self.closed = False
    def initialize(self, **kwargs): self.kwargs = kwargs; return self.ok
    def shutdown(self): self.closed = True
    def last_error(self): return (1, "fake")
    def terminal_info(self): return SimpleNamespace(name="fake") if self.ok else None
    def account_info(self): return None
    def symbol_info(self, symbol): return None
    def symbol_select(self, symbol, enable): return True
    def symbol_info_tick(self, symbol): return None
    def copy_rates_from_pos(self, *args): return []
    def symbols_get(self):
        return [SimpleNamespace(
            name="EURUSDm", description="Euro vs US Dollar", path="Forex", currency_base="EUR",
            currency_profit="USD", currency_margin="EUR", digits=5, point=0.00001,
            trade_tick_size=0.00001, trade_tick_value=1.0, trade_contract_size=100000,
            volume_min=0.01, volume_max=100, volume_step=0.01, trade_stops_level=10,
            trade_freeze_level=0, trade_mode=4, filling_mode=1, trade_exemode=2,
            spread=15, visible=True)]


def test_client_connection_failure_is_explicit():
    with pytest.raises(ConnectionError):
        MT5Client(FakeBackend(ok=False)).connect()


def test_discovery_reads_actual_broker_metadata():
    client = MT5Client(FakeBackend())
    client.connect(login=1, password="x", server="demo")
    specs = discover_symbols(client)
    assert specs[0].name == "EURUSDm"
    assert specs[0].contract_size == 100000
    client.shutdown()
    assert client.backend.closed
