from datetime import UTC, datetime, timedelta

from layer1_market.models import Candle, DataSource
from layer1_market.orderflow import build_orderflow_proxy
from layer1_market.regime import detect_regime
from layer1_market.structure import analyze_structure


def make(values: list[float]) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        Candle(
            time_utc=start + timedelta(minutes=i), open=v - 0.2, high=v + 0.5,
            low=v - 0.5, close=v + 0.2, tick_volume=100 + i, spread_points=2,
        ) for i, v in enumerate(values)
    )


def test_structure_uses_confirmed_pivots():
    cs = make([10,11,13,11,10,12,14,12,11,13,15,13,12])
    s = analyze_structure(cs)
    assert s.source is DataSource.DERIVED_PROXY
    assert 0 <= s.structure_score <= 1


def test_regime_scores_are_bounded():
    cs = make([100 + i for i in range(30)])
    r = detect_regime(cs)
    assert r.regime in {"TREND_UP", "HIGH_VOLATILITY", "RANGE", "CHAOTIC", "COMPRESSION"}
    assert 0 <= r.regime_fitness <= 1
    assert 0 <= r.volatility_score <= 1
    assert 0 <= r.trend_strength <= 1


def test_orderflow_is_explicit_proxy_and_bounded():
    cs = make([100 + i * 0.2 for i in range(30)])
    o = build_orderflow_proxy(cs)
    assert o.source is DataSource.DERIVED_PROXY
    assert 0 <= o.orderflow_score <= 1
    assert -1 <= o.directional_pressure <= 1
