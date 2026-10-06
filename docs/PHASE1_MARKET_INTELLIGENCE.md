# Phase 1 — Market Intelligence

## Scope

Phase 1 implements only market-side intelligence. It does **not** create BUY/SELL decisions,
neural inference, position sizing, or MT5 order execution.

## Implemented pipeline

`MT5 connection -> broker metadata -> generic symbol resolution -> closed market bars -> data validation -> point-in-time features -> confirmed structure -> regime -> derived orderflow proxy -> HTF/MTF/LTF sequences`

## MT5 isolation

`MT5Client` is a thin adapter around an injectable backend. The native `MetaTrader5` package
is imported lazily so development and CI can test deterministic market logic without an MT5
terminal. Install the `mt5` optional dependency only on the host that runs MT5.

No order-send API exists in this layer.

## Symbol resolution

Resolution is not based on substring alone. Candidate confidence aggregates normalized name,
known semantic aliases (for example `GOLD` for canonical `XAUUSD`), base/profit currencies,
description/path and trade-enabled metadata. Manual `.env` override remains possible.

A candidate below `MIN_SYMBOL_RESOLUTION_CONFIDENCE`, or two sufficiently close qualified
candidates, returns no broker symbol. Downstream behavior must therefore be HOLD / NO TRADE.

## Data integrity

Candle validation rejects insufficient history, duplicates, malformed/future bars, unsupported
timeframes and excessive missing-bar ratio. Fetching defaults to `start_pos=1`, deliberately
excluding the currently forming MT5 candle.

Tick staleness is separately detectable against a configured maximum age.

## Point-in-time features

Feature generation uses prefix-only histories. Modifying a future candle cannot alter prior
feature rows. No target/label fields exist in the feature payload.

Current baseline features include OHLC, one-period returns/log returns, candle geometry, tick
volume, spread, ATR, momentum, realized volatility, tick-volume ratio and spread ratio.

## Structure

Swing points require right-side confirmation. A pivot is unavailable until all configured
confirmation candles have closed. Structure output therefore cannot use a future-confirmed
swing at its historical decision timestamp.

## Regime

The deterministic baseline classifies trend/range/compression/high-volatility/chaotic states
from price-path efficiency and normalized range. These are context features, not direct trade
signals.

## Orderflow terminology

The baseline orderflow implementation is explicitly `DERIVED_PROXY`. It uses tick activity,
candle directional pressure and spread quality. It does not claim centralized exchange volume
or true aggressor-side order flow.

A future Market Depth adapter may emit real broker-provided depth separately if the feed is
available and validated.

## Multi-timeframe sequences

HTF, MTF and LTF keep independent configurable windows. Sequence construction applies an
as-of cutoff at the decision timestamp and refuses to pad insufficient history.

## Leakage audit

Controls implemented in this phase:

- forming candle excluded by default;
- future timestamps rejected by data validator;
- prefix-only feature calculations;
- confirmed-pivot semantics documented and tested;
- sequence as-of cutoff;
- no feature-label mixing;
- no whole-dataset scaler exists yet (normalization remains Phase 2 training responsibility).

## Phase 1 exit criteria

Phase 1 is complete when unit tests cover broker discovery, generic resolution including
ambiguity rejection, data-quality rejection, point-in-time feature behavior, bounded 0..1
semantic scores, proxy labeling and multi-timeframe alignment.
