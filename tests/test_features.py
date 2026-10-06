from datetime import UTC, datetime, timedelta

from layer1_market.features import build_feature_rows
from layer1_market.models import Candle


def make_candles(n: int) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        Candle(
            time_utc=start + timedelta(minutes=i),
            open=100 + i * 0.1,
            high=101 + i * 0.1,
            low=99 + i * 0.1,
            close=100.5 + i * 0.1,
            tick_volume=100 + i,
            spread_points=2,
        ) for i in range(n)
    )


def test_feature_rows_are_point_in_time():
    cs = make_candles(50)
    baseline = build_feature_rows(cs, "M1")
    changed_future = list(cs)
    last = changed_future[-1]
    changed_future[-1] = last.model_copy(update={"close": last.close + 100})
    changed = build_feature_rows(tuple(changed_future), "M1")
    # All rows before the modified final candle remain byte-for-byte semantically identical.
    assert baseline[:-1] == changed[:-1]
    assert baseline[-1] != changed[-1]


def test_feature_schema_has_no_label_or_future_field():
    rows = build_feature_rows(make_candles(50), "M1")
    keys = set(rows[-1].values)
    assert not any("label" in k or "future" in k or "target" in k for k in keys)
    assert {"atr", "momentum", "realized_volatility", "tick_volume_ratio", "spread_ratio"} <= keys
