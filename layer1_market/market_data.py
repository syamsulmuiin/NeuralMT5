from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from layer1_market.models import Candle
from layer1_market.mt5_client import MT5Client
from layer1_market.timeframes import native_timeframe


def _field(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row[name]
    try:
        return row[name]
    except (TypeError, KeyError, IndexError):
        return getattr(row, name)


def rates_to_candles(rates: Any) -> tuple[Candle, ...]:
    if rates is None:
        return ()
    candles = []
    for row in rates:
        candles.append(Candle(
            time_utc=datetime.fromtimestamp(int(_field(row, "time")), tz=UTC),
            open=float(_field(row, "open")),
            high=float(_field(row, "high")),
            low=float(_field(row, "low")),
            close=float(_field(row, "close")),
            tick_volume=float(_field(row, "tick_volume")),
            spread_points=float(_field(row, "spread")),
        ))
    return tuple(candles)


def fetch_recent_candles(
    client: MT5Client,
    symbol: str,
    timeframe: str,
    count: int,
    *,
    include_forming: bool = False,
) -> tuple[Candle, ...]:
    client.require_connected()
    if count <= 0:
        raise ValueError("count must be positive")
    start_pos = 0 if include_forming else 1
    tf = native_timeframe(client.backend, timeframe)
    try:
        rates = client.backend.copy_rates_from_pos(symbol, tf, start_pos, count)
    except Exception as exc:
        raise RuntimeError(f"copy_rates_from_pos raised for {symbol}/{timeframe}: {exc}") from exc
    if rates is None:
        raise RuntimeError(f"copy_rates_from_pos failed for {symbol}/{timeframe}: {client.backend.last_error()}")
    try:
        return rates_to_candles(rates)
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError) as exc:
        raise RuntimeError(f"invalid MT5 candle payload for {symbol}/{timeframe}: {exc}") from exc
