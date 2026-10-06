from __future__ import annotations

from dataclasses import dataclass
from layer3_execution.reconciliation import ReconciliationReport, reconcile_positions


@dataclass(frozen=True)
class RecoveryDecision:
    safe_to_open_new_positions: bool
    reason: str
    report: ReconciliationReport


def assess_restart_recovery(*, broker_tickets: set[int], journal_tickets: set[int]) -> RecoveryDecision:
    report = reconcile_positions(broker_tickets=broker_tickets, journal_tickets=journal_tickets)
    if not report.clean:
        return RecoveryDecision(False, "reconciliation mismatch requires operator/runtime resolution", report)
    return RecoveryDecision(True, "broker and journal positions reconciled", report)
