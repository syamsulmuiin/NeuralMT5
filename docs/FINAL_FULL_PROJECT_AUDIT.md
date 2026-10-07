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

The complete suite contains **143 tests** and passes after blocker closure. `python -m compileall` also passes.

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


## Full-code audit hardening update

The post-training-CLI audit closed additional defects that were not exercised by the earlier synthetic-only tests:

- candle/feature eligibility now uses candle **close time**, preventing forming HTF/MTF rows from entering point-in-time sequences;
- training writes `storage/reports/training_data_diagnostics.json` and exposes `python train.py --diagnose`;
- exact broker symbol names can resolve even when optional currency metadata is blank, while affix/alias candidates still require corroborating metadata;
- feature generation was reduced from effectively quadratic history slicing to bounded rolling-window work;
- MFE/MAE targets are direction-aware for BUY versus SELL;
- balanced accuracy now scores all three classes and promotion requires minimum validation samples per class;
- training splits use label horizon timestamps so forward targets cannot cross split boundaries;
- paper position monitoring now reads the persisted execution request symbol correctly;
- SQLite foreign keys and busy timeout are enabled on every runtime-store connection;
- account equity is refreshed each runtime cycle before new risk sizing;
- model loading verifies feature implementation version and scaler content hash, not version strings alone.

The regression baseline after this audit is **146 tests passing** plus successful `compileall`. Real-host/broker evidence remains separate from software regression.

## Documentation synchronization rule

Repository documentation is treated as part of the software contract. Changes to CLI workflows, configuration, broker/symbol resolution, training/promotion, risk/execution/reconciliation, live-readiness, artifacts, APIs, or dependencies must update the corresponding active documentation and `.env.example` in the same change set. Development-history-only documents should not be reintroduced; Git history is the source of historical change records.


## Backtest CLI and canonical workflow synchronization

The production historical replay engine is exposed through the top-level `python backtest.py` CLI. It loads the promoted Champion and paired scaler, resolves the configured broker symbols, fetches closed MT5 history, replays the existing Layer 1/2/3 implementation, applies historical daily/consecutive-loss Risk Firewall state plus execution preflight, and writes JSON plus per-trade CSV evidence. The canonical user workflow is now documented and tested as diagnose → train Challenger → explicit promotion → historical backtest → analysis forward test → paper forward test → real-host preflight/fault injection/soak → human LIVE-readiness review. Backtest completion never bypasses Layer 3 safety or any LIVE-readiness flag.

## Challenger classification validation

Training applies deterministic class-balanced classification weights derived from the training split only and keeps the classification objective dominant over auxiliary quality/excursion heads. The training report records class weights, predicted-class counts, per-class recall, and a confusion matrix. A failed validation keeps `python train.py --promote` blocked; the gate must not be bypassed by editing reports or lowering thresholds solely to obtain a pass.


## Training checkpoint selection

Training evaluates the chronological validation split after every epoch. The saved Challenger is restored from the epoch with the best validation balanced accuracy, using classification loss as a tie-break. Deterministic early stopping is controlled by `TRAIN_EARLY_STOPPING_PATIENCE` and `TRAIN_EARLY_STOPPING_MIN_DELTA`. This prevents a lower-quality final epoch from replacing an earlier better validation checkpoint. Promotion thresholds are not weakened by this mechanism.
## Hierarchical Neural Classification Hardening

The local neural brain now uses network version `cnn-gru-hierarchical-v2`. The classification path is hierarchical: an actionability head first learns `TRADE` versus `HOLD`, then a direction head learns `BUY` versus `SELL` only for actionable samples. Runtime still receives normalized BUY/SELL/HOLD probabilities, so Layer 3 contracts do not change. Training-only balancing weights are derived from the chronological training split. The TRADE/HOLD gate uses full binary balancing; BUY/SELL direction weights use the configured tempered correction.

Validation checkpoint selection uses macro-F1 as the primary metric, then balanced accuracy and classification loss as deterministic tie-breaks. This explicitly penalizes single-class prediction collapse; a model that predicts every validation row as one class can no longer be retained merely because balanced accuracy equals `1/3`. Model artifacts now enforce `network_version`, and old flat-head artifacts fail closed and require retraining. Promotion thresholds remain unchanged.



## Workflow prerequisite errors and historical-range auditability

Top-level CLI commands are required to fail closed with a concise prerequisite explanation and a next-step command for expected operational errors (for example promotion before validation, runtime before Champion promotion, or training while LIVE mode is selected). Expected user-order failures must not require interpreting an unhandled Python traceback.

Training-data provenance is also part of the audit contract. `TRAIN_HISTORY_BARS` is a count of most-recent closed candles **per timeframe**, not a fixed number of calendar days. `training_data_diagnostics.json` records actual per-timeframe UTC history ranges and the effective sample range. `training_report.json` records the full dataset decision-time range plus the chronological train/validation/test ranges. These timestamps are the authoritative record of what period was actually used on a specific broker/host.

## Exception-handling boundary audit

The current baseline includes a full boundary-focused exception-handling pass. Guarded areas include MT5 initialization/shutdown, symbol/account/history/tick calls, native order check/send, SQLite runtime/journal/idempotency/model-registry transactions, model/scaler artifact loading and saving, Challenger promotion file operations, training/backtest/preflight report writes, dashboard database reads, startup recovery, and CLI entry points.

The audit explicitly rejects blanket `try/except` around deterministic pure functions. Boundary failures add operation context and preserve the original cause; SQLite operations rollback on failure; expected duplicate-key integrity errors remain typed where runtime logic depends on them; dashboard database failures surface as degraded `503` responses instead of empty datasets; unexpected CLI exceptions are retained in `storage/logs/crash-*.log`; and runtime safety-maintenance failures pause new entries. Silent `except: pass` handling is not permitted for operational failures.

Regression baseline after this audit: **146 tests passing** plus successful `compileall`.

