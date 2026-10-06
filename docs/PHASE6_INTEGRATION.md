# Phase 6 — Integration

## Scope

Phase 6 connects the four domain layers into one restart-safe runtime for `analysis` and
`paper` modes. It deliberately blocks `live`; live readiness belongs to Phase 7.

The integrated cycle is:

`MT5 -> broker/symbol discovery -> validated closed candles -> point-in-time features ->
HTF/MTF/LTF sequences -> local neural inference -> Brainflow -> HOLD or deterministic
trade planning -> Risk Firewall -> refreshed preflight -> analysis/paper execution ->
journal/events/dashboard`.

## Startup and safety

Plain `python main.py` validates configuration only. MT5 is contacted only after an explicit
`python main.py --run`. `--once` runs one cycle and exits. The runtime refuses `TRADING_MODE=live`
even when credentials exist.

Model and scaler artifacts are loaded from `MODEL_ARTIFACT_PATH` and
`SCALER_ARTIFACT_PATH`. Model/scaler feature schema and scaler version are validated before
runtime start. Missing artifacts fail closed.

## Restart recovery

Startup compares open broker position tickets with open journal position tickets. Any
mismatch sets `reconciliation_ok=false` and pauses new entries. Existing position safety is
not delegated to the dashboard.

Execution idempotency remains durable through `execution_claims.client_order_key`.

## Runtime persistence

Phase 6 adds `runtime_state` and `runtime_cycles` tables. Every runtime event is persisted to
`system_events`. Observations, opportunities, plans, paper orders and paper trades use the
existing Phase 0–5 schema so dashboard replay remains compatible.

## Dashboard integration

The isolated dashboard now receives the *same* `RuntimeState`, `CommandGateway`, and
thread-safe `EventBus` as the trading runtime. WebSocket delivery uses the subscriber's event
loop via `call_soon_threadsafe`; slow UI clients remain lossy and never block trading.

Dashboard commands are intents only. Phase 6 rejects LIVE mode commands. Model promotion
commands are not applied by the runtime shortcut and must remain in the validated Layer 4
promotion workflow.

## Learning worker isolation

`IsolatedWorker` executes non-critical learning jobs on a daemon worker thread. Exceptions
are contained and cannot terminate or block the critical market loop.

## Reconnect and graceful shutdown

MT5 initialization uses bounded configurable retries. SIGINT/SIGTERM request runtime stop,
MT5 shutdown, and state persistence. There is no unbounded reconnect loop.

## New configuration

- `DATASET_VERSION`
- `MODEL_ARTIFACT_PATH`
- `SCALER_ARTIFACT_PATH`
- `RUNTIME_LOOP_SECONDS`
- `MT5_RECONNECT_ATTEMPTS`
- `MT5_RECONNECT_DELAY_SECONDS`

All are provided through `.env` as required by the project configuration contract.
