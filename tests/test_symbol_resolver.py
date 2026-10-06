from layer1_market.models import BrokerSymbolSpec
from layer1_market.symbol_resolver import normalize_symbol, resolve_symbol


def spec(name: str, base: str = "XAU", profit: str = "USD", **kw) -> BrokerSymbolSpec:
    values = dict(
        name=name, description="Gold vs US Dollar", path="Metals", currency_base=base,
        currency_profit=profit, currency_margin="USD", digits=2, point=0.01,
        tick_size=0.01, tick_value=1.0, contract_size=100.0,
        volume_min=0.01, volume_max=100.0, volume_step=0.01, stops_level=10,
        freeze_level=0, trade_mode=4, filling_mode=1, execution_mode=2,
        spread_points=20.0, visible=True,
    )
    values.update(kw)
    return BrokerSymbolSpec(**values)


def test_normalize_symbol_removes_broker_punctuation():
    assert normalize_symbol(" xau.usd ") == "XAUUSD"


def test_exact_symbol_wins():
    r = resolve_symbol("XAUUSD", [spec("XAUUSD")])
    assert r.broker_symbol == "XAUUSD"
    assert r.resolution_confidence >= 0.90


def test_suffix_symbol_resolves_using_metadata_too():
    r = resolve_symbol("XAUUSD", [spec("XAUUSD.vx")])
    assert r.broker_symbol == "XAUUSD.vx"
    assert r.resolution_confidence >= 0.90


def test_gold_alias_resolves():
    r = resolve_symbol("XAUUSD", [spec("GOLD")])
    assert r.broker_symbol == "GOLD"


def test_low_confidence_is_no_trade_resolution():
    bad = spec("BTCUSD", base="BTC", profit="USD", description="Bitcoin", path="Crypto")
    r = resolve_symbol("XAUUSD", [bad])
    assert r.broker_symbol is None
    assert not r.ambiguous


def test_ambiguous_candidates_rejected():
    a = spec("XAUUSD.a")
    b = spec("XAUUSD.b")
    r = resolve_symbol("XAUUSD", [a, b])
    assert r.broker_symbol is None
    assert r.ambiguous


def test_manual_override_requires_exact_broker_name():
    s = spec("XAUUSD.vx")
    ok = resolve_symbol("XAUUSD", [s], override="XAUUSD.vx")
    assert ok.broker_symbol == "XAUUSD.vx"
    missing = resolve_symbol("XAUUSD", [s], override="XAUUSD.bad")
    assert missing.broker_symbol is None


def test_exact_symbol_resolves_even_when_optional_currency_metadata_is_blank():
    s = spec("XAUUSD", base="", profit="", description="", path="")
    r = resolve_symbol("XAUUSD", [s])
    assert r.broker_symbol == "XAUUSD"
    assert r.resolution_confidence >= 0.90


def test_replay_symbol_is_hard_rejected_and_real_suffix_wins():
    real = spec("XAUUSD.vx")
    replay = spec("XAUUSDreplay")
    r = resolve_symbol("XAUUSD", [replay, real])
    assert r.broker_symbol == "XAUUSD.vx"
    assert r.resolution_confidence >= 0.90


def test_custom_symbol_is_hard_rejected_even_with_matching_metadata():
    custom = spec("XAUUSD.synthetic", custom=True)
    r = resolve_symbol("XAUUSD", [custom])
    assert r.broker_symbol is None
    assert "custom" in r.reason.lower()


def test_close_only_symbol_is_not_entry_candidate():
    close_only = spec("XAUUSD.vx", trade_mode=3)
    r = resolve_symbol("XAUUSD", [close_only])
    assert r.broker_symbol is None
    assert "trade_mode=3" in r.reason


def test_manual_override_cannot_bypass_replay_rejection():
    replay = spec("XAUUSDreplay")
    r = resolve_symbol("XAUUSD", [replay], override="XAUUSDreplay")
    assert r.broker_symbol is None
    assert "manual override rejected" in r.reason


def test_suffix_symbol_resolves_with_partial_broker_currency_metadata():
    # Some CFD brokers leave currency_base blank while still reporting the
    # correct profit currency. A strong canonical+affix match must still resolve.
    s = spec("XAUUSD.vx", base="", profit="USD")
    r = resolve_symbol("XAUUSD", [s])
    assert r.broker_symbol == "XAUUSD.vx"
    assert r.resolution_confidence >= 0.90


def test_unrelated_usd_profit_symbol_stays_far_below_threshold():
    other = spec("XTIUSD.vx", base="XTI", profit="USD", description="WTI Crude Oil", path="Energy")
    r = resolve_symbol("XAUUSD", [other])
    assert r.broker_symbol is None
    assert r.resolution_confidence < 0.30
