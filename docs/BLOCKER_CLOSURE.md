# Final-Audit Blocker Closure

## Status

The software-side blockers identified by `FINAL_FULL_PROJECT_AUDIT.md` have been closed. This does **not** self-certify LIVE operation: real MT5 broker/host fault-injection and soak evidence remain mandatory and the default live attestations remain false.

## Closed critical blockers

### C1 — Order / deal / position identity reconciliation

- execution receipts persist both order and deal tickets;
- deal history is used to resolve `position_id` without guessing from symbol;
- deal-only market fills are supported;
- migration-safe persistence adds `mt5_deal_ticket` to existing SQLite databases;
- unresolved filled/partial positions immediately mark reconciliation unhealthy and pause new entries;
- broker-side position disappearance is reconciled from position deal history before the journal is closed.

### C2 — Active-position lifecycle

- paper and live position maintenance runs before new-entry analysis;
- live positions update MFE/MAE from current executable price;
- invalid/missing protective-stop geometry pauses new entries and emits a system error;
- broker-side closes write exit price, gross P/L, commission, swap, net P/L, realized R and reason;
- paper positions deterministically process SL, TP and force-flat;
- `FORCE_FLAT_TIME` has an actual broker close path for LIVE and a deterministic close path for PAPER;
- partial force-flat fills fail closed and require reconciliation.

### C3 — Backtest/live pipeline parity

`run_historical_pipeline()` now reuses production components for:

- point-in-time feature generation;
- HTF/MTF/LTF sequence synchronization;
- structure, regime and orderflow proxy context;
- local neural inference;
- Brainflow opportunity gating;
- deterministic Layer-3 planning;
- risk firewall.

Historical entry occurs on the **next LTF bar**, not the decision bar. Same-bar SL+TP ambiguity is resolved conservatively to SL. The old `run_replay(realized_r)` function remains only as an explicitly documented metrics helper and is no longer the strategy backtest.

## Closed high blockers

### Session/timezone/DST

`TRADING_TIMEZONE` uses IANA `zoneinfo` and is validated at startup. Session/cutoff/force-flat comparisons are therefore timezone-aware and DST-aware. Broker-specific timezone/session correctness remains part of real-host validation because MT5 Python does not provide a uniform cross-broker session-calendar contract.

### Force-flat

Enforced by the position lifecycle in paper/live modes.

### Clock skew

Live readiness now compares current broker tick timestamp against host UTC and applies `LIVE_MAX_CLOCK_SKEW_SECONDS`.

### Freeze level

Preflight conservatively uses `max(stops_level, freeze_level)` for attached SL/TP distance validation.

### Filling mode

The adapter now maps MT5 `SYMBOL_FILLING_*` capability flags to `ORDER_FILLING_*` request enums instead of forwarding the symbol bitmask blindly. Final broker acceptance is still verified by native `order_check` and real-host testing.

## Additional audit improvements

- correlated exposure now uses currency overlap with the candidate symbol rather than equating correlated exposure with total exposure;
- dynamic `SYMBOL_<CANONICAL>` environment lookup is centralized in `Settings`;
- Challenger lifecycle provides train → evaluate → shadow → CHALLENGER registration and never auto-promotes;
- duplicate observation handling no longer swallows unrelated SQLite integrity failures.

## Remaining external blocker

The only critical blocker that cannot be truthfully closed without the user's MT5 host/broker is **real-host evidence**:

- fault injection;
- disconnect/reconnect with active positions;
- hedging and/or netting account identity behavior as applicable;
- broker filling/stops/freeze behavior;
- real session/calendar verification;
- long-duration analysis/paper soak;
- restart/reconciliation evidence.

Keep these false until evidence exists:

```env
LIVE_FAULT_INJECTION_PASSED=false
LIVE_SOAK_TEST_PASSED=false
```

Only after `docs/REAL_HOST_VALIDATION.md` is completed should those attestations be manually reviewed.
