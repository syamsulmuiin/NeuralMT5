from datetime import UTC, datetime, timedelta

import pytest

from layer1_market.models import FeatureRow
from layer1_market.sequences import build_sequence, synchronize_sequences


def rows(tf: str, minutes: int, n: int) -> tuple[FeatureRow, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(FeatureRow(timestamp_utc=start + timedelta(minutes=i * minutes), timeframe=tf, feature_version="x", values={"x": float(i)}) for i in range(n))


def test_sequence_never_reads_after_decision_time():
    rs = rows("M1", 1, 20)
    decision = rs[9].timestamp_utc
    seq = build_sequence(rs, "M1", 5, decision)
    assert len(seq.rows) == 5
    assert seq.rows[-1].timestamp_utc == decision
    assert all(r.timestamp_utc <= decision for r in seq.rows)


def test_insufficient_history_is_rejected_not_padded():
    rs = rows("M1", 1, 4)
    with pytest.raises(ValueError, match="insufficient"):
        build_sequence(rs, "M1", 5, rs[-1].timestamp_utc)


def test_multitimeframe_windows_are_independent():
    h = rows("M15", 15, 20)
    m = rows("M5", 5, 40)
    l = rows("M1", 1, 100)
    decision = datetime(2026,1,1,1,30,tzinfo=UTC)
    seq = synchronize_sequences(
        htf_rows=h, mtf_rows=m, ltf_rows=l,
        htf="M15", mtf="M5", ltf="M1",
        htf_window=4, mtf_window=8, ltf_window=16,
        decision_time_utc=decision,
    )
    assert len(seq.htf.rows) == 4
    assert len(seq.mtf.rows) == 8
    assert len(seq.ltf.rows) == 16
