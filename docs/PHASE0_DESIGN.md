# NeuralMT5 Phase 0 Design Baseline

## Status

This document turns the root README into implementation contracts. Phase 0 contains no trading signal generator, no MT5 order execution, no fake orderflow, and no pretrained model. The default mode is `analysis`.

## Architecture contract

The system has exactly four trading domains: Market Intelligence, Local Neural Brain, Risk & Execution, and Memory & Evolution. The dashboard is observational/control infrastructure, not a fifth trading layer. Layer 3 has absolute veto power. Layer 4 may propose a Challenger but cannot bypass Layer 3.

All semantic score/probability/confidence/strength/quality/fitness values use `0.0..1.0`. Physical quantities keep their natural units.

## Minimal dependencies

Phase 0 intentionally uses only Pydantic + pydantic-settings for typed contracts/configuration and Pytest for tests. MetaTrader5, numerical/data libraries and PyTorch are deferred until the phase that actually uses them. This prevents a false impression that Phase 0 already has a market or neural runtime.

## Cross-layer contracts

Layer 1 emits validated point-in-time market snapshots and feature sequences. Layer 2 consumes validated sequences and emits neural probabilities plus Brainflow evidence. Layer 3 refreshes the market, builds deterministic Entry/SL/TP/RR, sizes risk and returns ALLOWED/REJECTED. Layer 4 consumes immutable observations, decisions, orders and outcomes. Every historical decision must carry a version stamp linking strategy, feature, network, dataset, scaler, config and hashes.

## Generic symbols

Users provide canonical symbols. Phase 1 must resolve broker symbols using normalized identity plus broker metadata (base/profit/margin currencies, description/path, trade mode, digits, point and contract size), not suffix substring matching alone. Manual `SYMBOL_<CANONICAL>` overrides remain supported. Ambiguous or low-confidence results produce HOLD / NO TRADE.

## Generic timeframes and point-in-time data

HTF/MTF/LTF and all windows are configuration, not strategy constants. Multi-timeframe joins must be backward-looking and anchored on the decision timestamp. HTF/MTF candles are usable only once closed. Centered windows, future-confirmed pivots, future normalization and whole-dataset fitting are prohibited.

## Feature and label boundary

Feature groups may include raw candle data, returns, structure, volatility, momentum, derived orderflow proxies and regime. Real market data and derived proxies must remain explicitly distinguished.

Labels are generated after the observation timestamp and stored separately. Baseline multi-task targets are BUY/SELL/HOLD, setup quality, direction confidence, favorable excursion and adverse excursion. Forward barriers, horizon and trading costs must be versioned. Training splits are chronological with purge and embargo. No label may enter the feature pipeline.

## Neural baseline

The first benchmark candidate is three independent branches (HTF/MTF/LTF), each with a small Temporal Conv1D encoder plus GRU, followed by a compact dense fusion head. No pretrained weights. Initialization is local and seeded. Final architecture is selected by out-of-sample evidence, not complexity.

## Normalization and Brainflow

Scalers fit training data only. Validation/test/paper/live reuse the exact persisted scaler paired with the model. Brainflow is a weighted sum of eight normalized inputs, and startup validation requires all weights in 0..1 with sum 1.0. Direction selection must enforce minimum direction score, direction margin, confidence and Brainflow; ambiguity returns HOLD.

## Deterministic SL/TP and risk

Layer 2 never outputs absolute SL/TP. Layer 3 derives entry from a refreshed executable quote, SL from structural invalidation + volatility/noise + broker stop constraints, and TP from reachable structure/liquidity + volatility. Prices normalize to tick size. `NO SL = NO TRADE`; plans below `MIN_RR` are rejected. SL must never be moved only to manufacture RR.

Risk sizing uses actual account equity and broker tick/contract/volume constraints. Daily limits, consecutive losses, open positions, total/correlated exposure, spread, slippage, session state and broker execution validity are hard vetoes. Dashboard/neural code cannot bypass them.

## Champion / Challenger

Training creates a Challenger only. Promotion requires chronological OOS evaluation, walk-forward, purge/embargo, cost/slippage stress, drawdown constraints and shadow validation. `AUTO_PROMOTION_ENABLED=false` is the baseline. Promotion/rejection is audited and rollback keeps a compatible previous Champion.

## Dashboard contract

Required versioned read APIs are `/api/v1/status`, `/market`, `/brain`, `/opportunities`, `/positions`, `/trades`, `/performance`, `/learning`, `/risk`, `/system`; WebSocket is `/ws/v1/events`. Dashboard binds `127.0.0.1` by default, never receives MT5 secrets, cannot call `order_send` directly, and requires explicit confirmation for LIVE transition and model promotion.

## Database baseline

SQLite is the Phase 0 local baseline. Core tables separate observations, opportunities, trade plans, orders, trades, model artifacts, promotion audit and system events. `orders.client_order_key` is unique for future duplicate-order prevention. Core score/risk fields are first-class constrained columns; versioned feature/label/event payloads may use JSON.

## Leakage risk register

Critical controls: closed-candle cutoff; pivot confirmation timestamps; no centered rolling calculations; scaler fit on train only; separate feature/label schemas; purge + embargo overlapping horizons; point-in-time regime/normalization; one feature implementation for backtest/paper/live; retain rejected observations to reduce selection bias. Any failed leakage audit blocks Challenger promotion.

## Phase 0 exit criteria

Phase 0 is complete when configuration validation, score contracts, event contracts and database schema tests pass; `.env` secrets are ignored; no fake trading/execution exists; and Phase 1 can be implemented without changing these safety principles.
