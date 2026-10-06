from datetime import UTC, datetime

from contracts.domain import Direction
from layer3_execution.models import PositionSnapshot
from layer3_execution.monitor import safety_issue
from layer3_execution.reconciliation import reconcile_positions
from layer3_execution.recovery import assess_restart_recovery


def test_position_without_sl_is_critical_issue():
    p = PositionSnapshot(ticket=1, symbol="EURUSD", direction=Direction.BUY, volume=0.1,
        entry=1.1, stop_loss=None, take_profit=1.12, current_price=1.105,
        unrealized_pnl=5, opened_at_utc=datetime.now(UTC))
    assert safety_issue(p) == "position has no valid stop loss"


def test_reconciliation_detects_unmanaged_and_missing():
    r = reconcile_positions(broker_tickets={1,2}, journal_tickets={2,3})
    assert r.unmanaged_broker_tickets == (1,)
    assert r.missing_broker_tickets == (3,)
    assert not r.clean


def test_restart_blocks_new_positions_on_mismatch():
    r = assess_restart_recovery(broker_tickets={10}, journal_tickets=set())
    assert not r.safe_to_open_new_positions


def test_restart_allows_only_after_clean_reconciliation():
    r = assess_restart_recovery(broker_tickets={10}, journal_tickets={10})
    assert r.safe_to_open_new_positions
