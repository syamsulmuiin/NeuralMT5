from datetime import UTC, datetime, timedelta

from layer1_market.models import Candle
from layer1_market.validator import is_tick_stale, validate_candles


def candles(n: int, *, gap_at: int | None = None) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    out = []
    offset = 0
    for i in range(n):
        if gap_at is not None and i == gap_at:
            offset += 1
        t = start + timedelta(minutes=i + offset)
        out.append(Candle(time_utc=t, open=100, high=102, low=99, close=101, tick_volume=10, spread_points=2))
    return tuple(out)


def test_valid_candle_history():
    cs = candles(40)
    decision = cs[-1].time_utc + timedelta(minutes=1)
    r = validate_candles(cs, "M1", decision_time_utc=decision, minimum_history=32, max_missing_ratio=0.01)
    assert r.valid
    assert r.quality_score == 1.0


def test_missing_candle_rejected():
    cs = candles(40, gap_at=20)
    decision = cs[-1].time_utc + timedelta(minutes=1)
    r = validate_candles(cs, "M1", decision_time_utc=decision, minimum_history=32, max_missing_ratio=0.01)
    assert not r.valid
    assert r.missing_ratio > 0.01


def test_long_session_gap_is_not_called_missing_without_calendar():
    first = candles(20)
    shift = timedelta(days=2)
    second = tuple(c.model_copy(update={"time_utc": c.time_utc + shift}) for c in candles(20))
    cs = first + second
    decision = cs[-1].time_utc + timedelta(minutes=1)
    r = validate_candles(cs, "M1", decision_time_utc=decision, minimum_history=32, max_missing_ratio=0.01)
    assert r.missing_ratio == 0.0


def test_incomplete_candle_rejected():
    cs = candles(40)
    r = validate_candles(cs, "M1", decision_time_utc=cs[-1].time_utc, minimum_history=32, max_missing_ratio=0.01)
    assert not r.valid
    assert any("future/incomplete" in reason for reason in r.reasons)


def test_duplicate_candle_rejected():
    cs = candles(40)
    dup = cs + (cs[-1],)
    decision = cs[-1].time_utc + timedelta(minutes=1)
    r = validate_candles(dup, "M1", decision_time_utc=decision, minimum_history=32, max_missing_ratio=0.01)
    assert not r.valid
    assert r.duplicate_count == 1


def test_tick_staleness():
    now = datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC)
    assert is_tick_stale(now - timedelta(seconds=6), now, 5)
    assert not is_tick_stale(now - timedelta(seconds=5), now, 5)
    assert is_tick_stale(now + timedelta(seconds=1), now, 5)
