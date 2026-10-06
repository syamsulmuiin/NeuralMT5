from datetime import UTC, datetime
from types import SimpleNamespace

from config.settings import TradingMode
from contracts.domain import Direction
from layer3_execution.executor import execute_plan
from layer3_execution.idempotency import OrderRegistry
from layer3_execution.models import PlannedTrade, PreflightResult, ExecutionState


def _plan():
    return PlannedTrade(
        client_order_key='audit-key', symbol='XAUUSD', direction=Direction.BUY,
        planned_at_utc=datetime.now(UTC), entry=2000.0, stop_loss=1999.0,
        take_profit=2001.5, rr=1.5, sl_distance=1.0, tp_distance=1.5,
        lot=0.1, estimated_loss_at_sl=10.0, risk_fraction=0.005,
    )


class DealOnlyBackend:
    def order_send(self, request):
        return SimpleNamespace(order=None, deal=987654, retcode=10009, partial=False,
                               filled_volume=0.1, price=2000.25)


def test_live_deal_only_receipt_is_persistable_fill(tmp_path):
    result = execute_plan(
        plan=_plan(), preflight=PreflightResult(allowed=True), mode=TradingMode.LIVE,
        registry=OrderRegistry(tmp_path/'db.sqlite'), backend=DealOnlyBackend(),
    )
    assert result.state is ExecutionState.FILLED
    assert result.order_ticket is None
    assert result.deal_ticket == 987654
    assert result.actual_entry == 2000.25
