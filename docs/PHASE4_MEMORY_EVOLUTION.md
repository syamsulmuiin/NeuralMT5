# Phase 4 — Memory & Evolution

Phase 4 implements local memory and controlled learning without allowing learning code to bypass Layer 3 safety.

## Implemented

- append-only observation journal with one-time post-horizon labels;
- forward-path labels with conservative same-bar SL/TP ambiguity handling;
- MFE/MAE and quality/confidence targets;
- deterministic dataset hashing and versionable rows;
- chronological train/validation/test split with purge/embargo and horizon-overlap removal;
- expanding walk-forward fold generation;
- backtest/replay performance aggregation;
- challenger validation gates for minimum sample size, expectancy and drawdown;
- shadow comparison;
- standardized distribution-drift warning primitive;
- challenger registry and explicit Champion promotion with audit trail;
- previous Champion is retained as RETIRED for rollback history.

## Safety boundaries

Training produces a Challenger only. `AUTO_PROMOTION_ENABLED=true` cannot be used by the registry. A Challenger becomes Champion only after a passing validation report and explicit confirmation. Layer 4 never calls MT5 execution and cannot alter Layer 3 risk decisions.

Labels are generated only from a forward path after the observation time. Same-bar TP+SL ambiguity is labeled HOLD rather than assuming a favorable fill order. Chronological splits remove samples whose label horizon overlaps the next partition, in addition to configured purge/embargo bars.

## Not implemented in Phase 4

Dashboard/API presentation remains Phase 5. Long-duration runtime orchestration and failure recovery integration remain Phase 6. Live-readiness remains Phase 7.
