from __future__ import annotations

from datetime import datetime

from layer1_market.models import FeatureRow, MultiTimeframeSequences, TimeframeSequence
from layer1_market.timeframes import timeframe_delta


def build_sequence(rows: tuple[FeatureRow, ...], timeframe: str, window: int, decision_time_utc: datetime) -> TimeframeSequence:
    """Build a strictly point-in-time sequence.

    FeatureRow.timestamp_utc is the candle *open* timestamp. A row is therefore only
    observable after that timeframe's candle has closed. This prevents an HTF/MTF
    candle that is still forming at decision time from leaking into inference.
    """
    if window <= 0:
        raise ValueError("window must be positive")
    tf = timeframe.upper()
    close_delta = timeframe_delta(tf)
    eligible = [r for r in rows if r.timestamp_utc + close_delta <= decision_time_utc]
    if len(eligible) < window:
        raise ValueError(f"insufficient closed {tf} feature history: {len(eligible)} < {window}")
    chosen = tuple(eligible[-window:])
    if any(row.timeframe != tf for row in chosen):
        raise ValueError(f"timeframe mismatch in {tf} sequence")
    return TimeframeSequence(timeframe=tf, decision_time_utc=decision_time_utc, rows=chosen)


def synchronize_sequences(
    *,
    htf_rows: tuple[FeatureRow, ...],
    mtf_rows: tuple[FeatureRow, ...],
    ltf_rows: tuple[FeatureRow, ...],
    htf: str,
    mtf: str,
    ltf: str,
    htf_window: int,
    mtf_window: int,
    ltf_window: int,
    decision_time_utc: datetime,
) -> MultiTimeframeSequences:
    return MultiTimeframeSequences(
        decision_time_utc=decision_time_utc,
        htf=build_sequence(htf_rows, htf, htf_window, decision_time_utc),
        mtf=build_sequence(mtf_rows, mtf, mtf_window, decision_time_utc),
        ltf=build_sequence(ltf_rows, ltf, ltf_window, decision_time_utc),
    )
