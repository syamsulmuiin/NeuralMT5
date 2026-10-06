# Phase 6 Audit

## Integration

- Layer 1 through Layer 4 contracts are connected by `runtime/orchestrator.py`.
- Analysis mode records opportunities/plans but never simulates or sends an order.
- Paper mode executes through the existing generic executor and never calls MT5 `order_send`.
- LIVE mode is blocked in both startup and dashboard runtime command processing.

## Restart / reconciliation

- Broker/journal open tickets are compared at startup.
- Any mismatch pauses new entries and marks reconciliation unhealthy.
- Durable execution claims survive restart.

## Failure containment

- Per-symbol failures are caught, persisted and surfaced as `SYSTEM_ERROR` events while the
  remaining symbols continue.
- Dashboard startup/server failure remains isolated.
- Learning worker failures are isolated.
- Event delivery is cross-thread safe and backpressure cannot block the runtime.
- MT5 reconnect is bounded; repeated failure aborts startup rather than pretending success.

## Leakage / reproducibility

- Runtime feature construction reuses the same Phase 1 point-in-time implementation.
- Closed candles are fetched (`start_pos=1`), future candles are rejected, and sequences are
  synchronized at the LTF decision timestamp.
- Runtime inference reuses the persisted training scaler; it never fits a scaler live.
- Config hash excludes secrets and is stored with opportunity version metadata.

## Known Phase 7 boundary

Phase 6 is not a live-readiness declaration. Production LIVE activation still requires the
Phase 7 audit: broker-specific execution verification, long-running host tests, fault
injection, position lifecycle reconciliation against real MT5 deals, operational monitoring,
and explicit operator approval.
