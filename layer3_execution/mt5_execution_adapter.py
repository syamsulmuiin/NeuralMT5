from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.settings import Settings
from layer1_market.models import BrokerSymbolSpec


@dataclass(frozen=True)
class MT5ExecutionReceipt:
    retcode: int
    order: int | None
    deal: int | None
    price: float | None
    requested_volume: float
    filled_volume: float | None
    partial: bool
    comment: str


class MT5ExecutionAdapter:
    """Native MT5 adapter with check-before-send and explicit partial-fill semantics."""

    def __init__(self, native_backend: Any, spec: BrokerSymbolSpec, settings: Settings) -> None:
        self.mt5 = native_backend
        self.spec = spec
        self.settings = settings


    def _filling_type(self) -> int:
        flags = int(self.spec.filling_mode)
        # MT5 symbol_info().filling_mode is a SYMBOL_FILLING_* capability bitmask,
        # while an order request expects ORDER_FILLING_* enum values.
        sfok = getattr(self.mt5, "SYMBOL_FILLING_FOK", None); sioc = getattr(self.mt5, "SYMBOL_FILLING_IOC", None)
        ofok = getattr(self.mt5, "ORDER_FILLING_FOK", None); oioc = getattr(self.mt5, "ORDER_FILLING_IOC", None); oreturn = getattr(self.mt5, "ORDER_FILLING_RETURN", None)
        if sfok is not None and ofok is not None and flags & int(sfok):
            return int(ofok)
        if sioc is not None and oioc is not None and flags & int(sioc):
            return int(oioc)
        market_exec = getattr(self.mt5, "SYMBOL_TRADE_EXECUTION_MARKET", None)
        if oreturn is not None and (market_exec is None or int(self.spec.execution_mode) != int(market_exec)):
            return int(oreturn)
        # Backward-compatible fallback for test doubles/older wrappers that already
        # expose an order filling enum rather than symbol capability flags.
        return flags

    def _native_request(self, request: dict[str, Any]) -> dict[str, Any]:
        direction = request["direction"]
        if direction == "BUY":
            order_type = self.mt5.ORDER_TYPE_BUY
        elif direction == "SELL":
            order_type = self.mt5.ORDER_TYPE_SELL
        else:
            raise ValueError("MT5 execution accepts BUY or SELL only")
        return {
            "action": self.mt5.TRADE_ACTION_DEAL, "symbol": request["symbol"],
            "volume": float(request["volume"]), "type": order_type,
            "price": float(request["price"]), "sl": float(request["sl"]),
            "tp": float(request["tp"]), "deviation": int(round(self.settings.max_slippage_points)),
            "magic": int(self.settings.mt5_magic_number), "comment": self.settings.mt5_order_comment,
            "type_time": self.mt5.ORDER_TIME_GTC, "type_filling": self._filling_type(),
        }

    def order_send(self, request: dict[str, Any]) -> MT5ExecutionReceipt:
        native = self._native_request(request)
        try:
            check = self.mt5.order_check(native)
        except Exception as exc:
            raise RuntimeError(f"MT5 order_check raised: {exc}") from exc
        if check is None:
            raise RuntimeError(f"MT5 order_check returned None: {self.mt5.last_error()}")
        if int(getattr(check, "retcode", -1)) != 0:
            raise RuntimeError(f"MT5 order_check rejected request: retcode={getattr(check, 'retcode', None)} comment={getattr(check, 'comment', '')}")
        try:
            result = self.mt5.order_send(native)
        except Exception as exc:
            raise RuntimeError(f"MT5 order_send raised: {exc}") from exc
        if result is None:
            raise RuntimeError(f"MT5 order_send returned None: {self.mt5.last_error()}")
        code = int(getattr(result, "retcode", -1))
        done = int(self.mt5.TRADE_RETCODE_DONE)
        partial_code = int(getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", -999999))
        placed = int(getattr(self.mt5, "TRADE_RETCODE_PLACED", done))
        if code not in {done, partial_code, placed}:
            raise RuntimeError(f"MT5 order_send rejected request: retcode={code} comment={getattr(result, 'comment', '')}")
        filled = getattr(result, "volume", None)
        return MT5ExecutionReceipt(
            retcode=code, order=getattr(result, "order", None), deal=getattr(result, "deal", None),
            price=getattr(result, "price", None), requested_volume=float(native["volume"]),
            filled_volume=float(filled) if filled is not None else None, partial=code == partial_code,
            comment=str(getattr(result, "comment", "")),
        )

    def close_position(self, *, position_ticket: int, symbol: str, volume: float, direction: str, price: float) -> MT5ExecutionReceipt:
        """Close an existing MT5 position using an explicit opposite market deal."""
        opposite = self.mt5.ORDER_TYPE_SELL if direction == "BUY" else self.mt5.ORDER_TYPE_BUY
        native = {
            "action": self.mt5.TRADE_ACTION_DEAL, "symbol": symbol, "position": int(position_ticket),
            "volume": float(volume), "type": opposite, "price": float(price),
            "deviation": int(round(self.settings.max_slippage_points)), "magic": int(self.settings.mt5_magic_number),
            "comment": f"{self.settings.mt5_order_comment}:flat"[:31], "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_type(),
        }
        try:
            check = self.mt5.order_check(native)
        except Exception as exc:
            raise RuntimeError(f"MT5 close order_check raised: {exc}") from exc
        if check is None or int(getattr(check, "retcode", -1)) != 0:
            raise RuntimeError(f"MT5 close order_check failed: {getattr(check, 'retcode', None)} {getattr(check, 'comment', '')}")
        try:
            result = self.mt5.order_send(native)
        except Exception as exc:
            raise RuntimeError(f"MT5 close order_send raised: {exc}") from exc
        if result is None:
            raise RuntimeError(f"MT5 close order_send returned None: {self.mt5.last_error()}")
        code = int(getattr(result, "retcode", -1))
        done = int(self.mt5.TRADE_RETCODE_DONE)
        partial_code = int(getattr(self.mt5, "TRADE_RETCODE_DONE_PARTIAL", -999999))
        if code not in {done, partial_code}:
            raise RuntimeError(f"MT5 close rejected: retcode={code} comment={getattr(result, 'comment', '')}")
        filled = getattr(result, "volume", None)
        return MT5ExecutionReceipt(code, getattr(result, "order", None), getattr(result, "deal", None), getattr(result, "price", None), float(volume), float(filled) if filled is not None else None, code == partial_code, str(getattr(result, "comment", "")))
