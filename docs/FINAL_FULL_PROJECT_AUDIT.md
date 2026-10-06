# NeuralMT5 Final Full-Project Audit — Post-Closure

## Verdict

**SOFTWARE BLOCKERS CLOSED; REAL-HOST VALIDATION REQUIRED.**

The repository now closes the code-level Critical and H1–H5 blockers identified by the previous final audit. LIVE remains intentionally blocked because real MT5 broker/host fault-injection and soak evidence cannot be manufactured offline.

## Verified software controls

- order → deal → position identity is reconciled from MT5 deal history rather than guessed;
- active paper/live position lifecycle updates excursions and reconciles broker closes;
- close accounting persists gross P/L, commission, swap, net P/L, realized R and close reason;
- force-flat is executable in paper/live lifecycle;
- historical strategy replay uses production Layer 1/2/3 components and next-bar execution;
- semantic scores remain 0..1 and Brainflow weights sum to 1.0;
- Layer 3 keeps absolute risk veto authority;
- preflight applies spread, slippage, session, stops and freeze constraints;
- session checks use validated IANA timezone semantics;
- live readiness measures broker/host clock skew;
- symbol filling capability flags are mapped to order filling enums and still pass native `order_check`;
- correlated exposure is based on overlapping currencies instead of total exposure;
- durable idempotency claim remains before broker send;
- dashboard/runtime have no direct native `order_send` path;
- auto-promotion remains disabled; Challenger registration is separated from manual Champion promotion;
- duplicate observation handling does not hide unrelated database integrity failures.

## Regression evidence

The complete suite contains **112 tests** and passes after blocker closure. `python -m compileall` also passes.

## Remaining real-host gate

The following are intentionally **NOT** self-certified:

- real broker fault injection;
- disconnect/reconnect while positions are active;
- broker-specific hedging/netting behavior;
- live partial fill behavior;
- real filling/stops/freeze acceptance;
- broker session/calendar confirmation;
- long-duration host soak and restart recovery evidence.

Therefore:

```env
LIVE_FAULT_INJECTION_PASSED=false
LIVE_SOAK_TEST_PASSED=false
```

must remain false until `REAL_HOST_VALIDATION.md` is completed on the target MT5 host.

See `BLOCKER_CLOSURE.md` for the implementation-level closure details.
