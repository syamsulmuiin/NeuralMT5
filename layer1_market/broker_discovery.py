from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from layer1_market.models import AccountSnapshot, BrokerSymbolSpec
from layer1_market.mt5_client import MT5Client


def _read(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def symbol_spec_from_mt5(info: Any) -> BrokerSymbolSpec:
    tick_size = float(_read(info, "trade_tick_size", 0.0) or _read(info, "point", 0.0))
    return BrokerSymbolSpec(
        name=str(_read(info, "name", "")),
        description=str(_read(info, "description", "") or ""),
        path=str(_read(info, "path", "") or ""),
        currency_base=str(_read(info, "currency_base", "") or "").upper(),
        currency_profit=str(_read(info, "currency_profit", "") or "").upper(),
        currency_margin=str(_read(info, "currency_margin", "") or "").upper(),
        digits=int(_read(info, "digits", 0)),
        point=float(_read(info, "point", 0.0)),
        tick_size=tick_size,
        tick_value=float(_read(info, "trade_tick_value", 0.0) or 0.0),
        contract_size=float(_read(info, "trade_contract_size", 0.0)),
        volume_min=float(_read(info, "volume_min", 0.0)),
        volume_max=float(_read(info, "volume_max", 0.0)),
        volume_step=float(_read(info, "volume_step", 0.0)),
        stops_level=int(_read(info, "trade_stops_level", 0) or 0),
        freeze_level=int(_read(info, "trade_freeze_level", 0) or 0),
        trade_mode=int(_read(info, "trade_mode", 0) or 0),
        filling_mode=int(_read(info, "filling_mode", 0) or 0),
        execution_mode=int(_read(info, "trade_exemode", 0) or 0),
        spread_points=float(_read(info, "spread", 0.0) or 0.0),
        visible=bool(_read(info, "visible", True)),
        custom=bool(_read(info, "custom", False)),
    )


def discover_symbols(client: MT5Client) -> tuple[BrokerSymbolSpec, ...]:
    client.require_connected()
    raw = client.backend.symbols_get()
    if raw is None:
        raise RuntimeError(f"MT5 symbols_get failed: {client.backend.last_error()}")
    specs: list[BrokerSymbolSpec] = []
    for info in raw:
        try:
            specs.append(symbol_spec_from_mt5(info))
        except ValueError:
            # Invalid broker metadata is deliberately excluded; resolver can never trade it.
            continue
    return tuple(specs)


def discover_account(client: MT5Client) -> AccountSnapshot:
    client.require_connected()
    info = client.backend.account_info()
    if info is None:
        raise RuntimeError(f"MT5 account_info failed: {client.backend.last_error()}")
    return AccountSnapshot(
        login=int(_read(info, "login", 0)),
        server=str(_read(info, "server", "")),
        currency=str(_read(info, "currency", "")),
        balance=float(_read(info, "balance", 0.0)),
        equity=float(_read(info, "equity", 0.0)),
        margin=float(_read(info, "margin", 0.0)),
        margin_free=float(_read(info, "margin_free", 0.0)),
    )
