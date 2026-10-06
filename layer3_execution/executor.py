from __future__ import annotations

from typing import Any, Protocol

from config.settings import TradingMode
from layer3_execution.idempotency import OrderRegistry
from layer3_execution.models import ExecutionResult, ExecutionState, PlannedTrade, PreflightResult


class OrderBackend(Protocol):
    def order_send(self, request: dict[str, Any]) -> Any: ...


def execute_plan(
    *, plan: PlannedTrade, preflight: PreflightResult, mode: TradingMode,
    registry: OrderRegistry, backend: OrderBackend | None = None,
) -> ExecutionResult:
    if not preflight.allowed:
        return ExecutionResult(
            state=ExecutionState.PREFLIGHT_REJECTED,
            client_order_key=plan.client_order_key, symbol=plan.symbol,
            reason="; ".join(preflight.reasons),
        )
    registry.claim(plan.client_order_key, plan.planned_at_utc.isoformat())
    if mode is TradingMode.ANALYSIS:
        registry.update_state(plan.client_order_key, "ANALYSIS_ONLY")
        return ExecutionResult(
            state=ExecutionState.PREFLIGHT_REJECTED,
            client_order_key=plan.client_order_key, symbol=plan.symbol,
            reason="analysis mode never sends or simulates orders",
        )
    if mode is TradingMode.PAPER:
        registry.update_state(plan.client_order_key, "PAPER_FILLED")
        return ExecutionResult(
            state=ExecutionState.PAPER_FILLED,
            client_order_key=plan.client_order_key, symbol=plan.symbol,
            actual_entry=plan.entry, reason="paper execution",
        )
    if backend is None:
        registry.update_state(plan.client_order_key, "FAILED")
        return ExecutionResult(
            state=ExecutionState.FAILED, client_order_key=plan.client_order_key,
            symbol=plan.symbol, reason="live backend unavailable",
        )
    request = {
        "symbol": plan.symbol,
        "volume": plan.lot,
        "price": plan.entry,
        "sl": plan.stop_loss,
        "tp": plan.take_profit,
        "direction": plan.direction.value,
        "client_order_key": plan.client_order_key,
    }
    try:
        result = backend.order_send(request)
    except Exception as exc:
        registry.update_state(plan.client_order_key, "FAILED")
        return ExecutionResult(
            state=ExecutionState.FAILED, client_order_key=plan.client_order_key,
            symbol=plan.symbol, reason=f"order_send exception: {exc}",
        )
    ticket = getattr(result, "order", None)
    deal = getattr(result, "deal", None)
    retcode = getattr(result, "retcode", None)
    partial = bool(getattr(result, "partial", False))
    filled_volume = getattr(result, "filled_volume", None)
    actual_entry = getattr(result, "price", None)
    # Market execution may return a deal without a durable order ticket.  A
    # successful receipt must therefore be identified by either broker id,
    # never by ``order`` alone.
    if not ticket and not deal:
        registry.update_state(plan.client_order_key, "FAILED")
        return ExecutionResult(
            state=ExecutionState.FAILED, client_order_key=plan.client_order_key,
            symbol=plan.symbol, reason=f"order rejected retcode={retcode}",
        )
    if partial:
        registry.update_state(plan.client_order_key, "PARTIALLY_FILLED")
        return ExecutionResult(
            state=ExecutionState.PARTIALLY_FILLED, client_order_key=plan.client_order_key,
            symbol=plan.symbol, order_ticket=int(ticket) if ticket else None,
            deal_ticket=int(deal) if deal else None,
            actual_entry=float(actual_entry) if actual_entry else None,
            requested_volume=plan.lot, filled_volume=filled_volume,
            reason=f"partial fill retcode={retcode}; reconciliation required",
        )
    fully_filled = bool(deal) or actual_entry is not None
    final_state = ExecutionState.FILLED if fully_filled else ExecutionState.SENT
    registry.update_state(plan.client_order_key, final_state.value)
    return ExecutionResult(
        state=final_state, client_order_key=plan.client_order_key,
        symbol=plan.symbol, order_ticket=int(ticket) if ticket else None,
        deal_ticket=int(deal) if deal else None,
        actual_entry=float(actual_entry) if actual_entry is not None else None,
        requested_volume=plan.lot, filled_volume=filled_volume,
        reason=(f"retcode={retcode}; position identity requires reconciliation"
                if fully_filled else f"retcode={retcode}; broker acknowledgement requires reconciliation"),
    )
