# Phase 3 Audit

## Safety

- Layer 3 remains the final capital-risk veto.
- No trade can be planned from HOLD.
- No planned trade can omit SL or TP.
- SL/TP are broker tick-normalized before RR acceptance.
- Minimum broker volume that exceeds the risk budget is rejected.
- Duplicate execution is durably blocked before broker submission.
- Analysis and paper modes cannot call the broker.
- Native live execution uses `order_check` and validates send retcodes.
- Restart reconciliation mismatch blocks new positions.

## Hardcoding

No broker suffix, point, tick size/value, contract size, lot constraints, stops level or
filling mode is hardcoded into strategy logic. The MT5 magic number and order comment are
configuration values. MT5 protocol constants are read from the installed MT5 backend.

## Leakage

Phase 3 introduces no training features or labels, therefore no new future/scaler/target
leakage path. Plans consume only already-validated current state plus a refreshed execution
quote.

## Known phase boundary

Trade journal enrichment, MFE/MAE outcome labeling, historical dataset building, walk-forward
validation, Champion/Challenger and drift belong to Phase 4. Dashboard controls/API belong to
Phase 5. This phase does not claim those features are implemented.
