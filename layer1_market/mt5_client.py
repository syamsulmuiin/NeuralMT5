from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol, Sequence


class MT5Backend(Protocol):
    def initialize(self, **kwargs: Any) -> bool: ...
    def shutdown(self) -> None: ...
    def last_error(self) -> Any: ...
    def terminal_info(self) -> Any: ...
    def account_info(self) -> Any: ...
    def symbols_get(self) -> Sequence[Any] | None: ...
    def symbol_info(self, symbol: str) -> Any: ...
    def symbol_select(self, symbol: str, enable: bool) -> bool: ...
    def symbol_info_tick(self, symbol: str) -> Any: ...
    def copy_rates_from_pos(self, symbol: str, timeframe: int, start_pos: int, count: int) -> Any: ...


def load_native_backend() -> Any:
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "MetaTrader5 package is not installed. Install the optional 'mt5' dependency on a supported MT5 host."
        ) from exc
    return mt5


class MT5Client(AbstractContextManager["MT5Client"]):
    """Thin, testable MT5 adapter. Trading/order methods intentionally do not exist in Phase 1."""

    def __init__(self, backend: MT5Backend | None = None) -> None:
        self.backend = backend or load_native_backend()
        self.connected = False

    def connect(
        self,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        path: str | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if login is not None:
            kwargs["login"] = login
        if password:
            kwargs["password"] = password
        if server:
            kwargs["server"] = server
        if path:
            kwargs["path"] = path
        if not self.backend.initialize(**kwargs):
            raise ConnectionError(f"MT5 initialize failed: {self.backend.last_error()}")
        self.connected = True
        terminal = self.backend.terminal_info()
        if terminal is None:
            self.shutdown()
            raise ConnectionError(f"MT5 terminal_info unavailable: {self.backend.last_error()}")

    def require_connected(self) -> None:
        if not self.connected:
            raise RuntimeError("MT5 client is not connected")

    def shutdown(self) -> None:
        if self.connected:
            self.backend.shutdown()
        self.connected = False

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()
