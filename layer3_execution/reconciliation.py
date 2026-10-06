from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ReconciliationReport:
    unmanaged_broker_tickets: tuple[int, ...]
    missing_broker_tickets: tuple[int, ...]

    @property
    def clean(self) -> bool:
        return not self.unmanaged_broker_tickets and not self.missing_broker_tickets


@dataclass(frozen=True)
class BrokerExecutionIdentity:
    order_ticket: int | None
    deal_ticket: int | None
    position_ticket: int | None
    price: float | None
    volume: float | None
    time_utc: datetime | None


def reconcile_positions(*, broker_tickets: set[int], journal_tickets: set[int]) -> ReconciliationReport:
    return ReconciliationReport(
        unmanaged_broker_tickets=tuple(sorted(broker_tickets - journal_tickets)),
        missing_broker_tickets=tuple(sorted(journal_tickets - broker_tickets)),
    )


def execution_identity_from_mt5(backend: Any, *, order_ticket: int | None, deal_ticket: int | None) -> BrokerExecutionIdentity:
    """Resolve MT5 order/deal receipt into a durable position identity.

    MT5 market execution can return a deal without a useful order ticket.  The
    deal's position_id is the canonical link to the open/closed position and is
    therefore preferred over inferring identity from symbol alone (unsafe for
    hedging accounts).
    """
    deal = None
    if deal_ticket is not None and hasattr(backend, "history_deals_get"):
        rows = backend.history_deals_get(ticket=int(deal_ticket)) or ()
        if rows:
            deal = rows[-1]
    if deal is None and order_ticket is not None and hasattr(backend, "history_deals_get"):
        rows = backend.history_deals_get() or ()
        matches = [r for r in rows if int(getattr(r, "order", -1)) == int(order_ticket)]
        if matches:
            deal = matches[-1]
    position_id = getattr(deal, "position_id", None) if deal is not None else None
    raw_time = getattr(deal, "time", None) if deal is not None else None
    return BrokerExecutionIdentity(
        order_ticket=int(order_ticket) if order_ticket else (int(getattr(deal, "order")) if deal is not None and getattr(deal, "order", None) else None),
        deal_ticket=int(getattr(deal, "ticket")) if deal is not None and getattr(deal, "ticket", None) else (int(deal_ticket) if deal_ticket else None),
        position_ticket=int(position_id) if position_id else None,
        price=float(getattr(deal, "price")) if deal is not None and getattr(deal, "price", None) is not None else None,
        volume=float(getattr(deal, "volume")) if deal is not None and getattr(deal, "volume", None) is not None else None,
        time_utc=datetime.fromtimestamp(int(raw_time), tz=UTC) if raw_time is not None else None,
    )

@dataclass(frozen=True)
class BrokerCloseOutcome:
    position_ticket: int
    exit_price: float
    closed_at_utc: datetime
    gross_pnl: float
    commission: float
    swap: float
    net_pnl: float
    reason: str


def closed_position_outcome_from_mt5(backend: Any, position_ticket: int) -> BrokerCloseOutcome | None:
    """Build a close outcome from MT5 deal history for one position id.

    Returns None when history is unavailable/incomplete.  All monetary components
    are aggregated across the position's deals so commission and swap are not lost.
    """
    getter = getattr(backend, "history_deals_get", None)
    if not callable(getter):
        return None
    deals = getter(position=int(position_ticket)) or ()
    if not deals:
        return None
    deals = tuple(sorted(deals, key=lambda d: (int(getattr(d, "time", 0)), int(getattr(d, "ticket", 0)))))
    last = deals[-1]
    raw_time = getattr(last, "time", None)
    price = getattr(last, "price", None)
    if raw_time is None or price is None:
        return None
    profit = sum(float(getattr(d, "profit", 0.0) or 0.0) for d in deals)
    commission = sum(float(getattr(d, "commission", 0.0) or 0.0) for d in deals)
    swap = sum(float(getattr(d, "swap", 0.0) or 0.0) for d in deals)
    fee = sum(float(getattr(d, "fee", 0.0) or 0.0) for d in deals)
    reason_code = getattr(last, "reason", None)
    return BrokerCloseOutcome(
        position_ticket=int(position_ticket), exit_price=float(price),
        closed_at_utc=datetime.fromtimestamp(int(raw_time), tz=UTC),
        gross_pnl=profit, commission=commission + fee, swap=swap,
        net_pnl=profit + commission + swap + fee,
        reason=f"MT5_DEAL_REASON_{reason_code}" if reason_code is not None else "BROKER_CLOSE",
    )
