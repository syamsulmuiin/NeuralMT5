from __future__ import annotations

from datetime import datetime

from layer1_market.models import FeatureRow, MultiTimeframeSequences, TimeframeSequence


def build_sequence(rows: tuple[FeatureRow, ...], timeframe: str, window: int, decision_time_utc: datetime) -> TimeframeSequence:
    if window <= 0:
        raise ValueError("window must be positive")
    eligible = [r for r in rows if r.timestamp_utc <= decision_time_utc]
    if len(eligible) < window:
        raise ValueError(f"insufficient {timeframe} feature history: {len(eligible)} < {window}")
    chosen = tuple(eligible[-window:])
    if any(row.timeframe != timeframe.upper() for row in chosen):
        raise ValueError(f"timeframe mismatch in {timeframe} sequence")
    return TimeframeSequence(timeframe=timeframe.upper(), decision_time_utc=decision_time_utc, rows=chosen)


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
