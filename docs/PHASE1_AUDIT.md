# Phase 1 Audit

## Result

Phase 1 passes its local deterministic test suite and is ready to serve as the input boundary
for Phase 2. This is not a live-readiness claim.

## Hardcoding audit

- HTF/MTF/LTF defaults exist only as configuration defaults.
- Supported timeframe names live in the timeframe/config capability maps; strategy code does
  not force M15/M5/M1.
- Broker symbol suffixes are not hardcoded.
- Broker contract/tick/volume/stops properties are discovered from MT5 metadata.
- Feature/regime/structure/orderflow lookbacks are available in `.env` typed settings.

## Leakage audit

- Market fetch excludes the forming candle by default.
- Future candle timestamps are rejected.
- Feature rows are generated from historical prefixes only.
- Confirmed swings require right-side closed bars.
- Multi-timeframe sequences apply an as-of decision-time cutoff.
- Labels do not exist in the feature schema.

## Safety audit

- No `order_send` implementation exists in Layer 1.
- No BUY/SELL/HOLD decision implementation exists in Layer 1.
- Ambiguous/low-confidence symbol resolution returns no broker symbol.
- Invalid market history fails validation instead of being silently repaired.
- Orderflow derived from candle/tick data is explicitly tagged `DERIVED_PROXY`.

## Error-handling audit

- MT5 initialization, terminal-info, symbols-get and rates failures surface explicit exceptions.
- Insufficient sequence history is rejected instead of padded.
- Unsupported timeframes are rejected.
- Invalid broker metadata is excluded from discovery instead of becoming a tradable contract.

## Configuration audit

Runtime-changing Layer 1 thresholds/lookbacks are represented in typed settings and the
`.env.example`. Native MT5 is an optional dependency so tests do not pretend that an MT5
terminal is available on unsupported CI/development hosts.

## Deferred by design

The following belong to later README phases and are intentionally not implemented here:
normalization/scaler fitting, local neural architecture and inference, Brainflow decision,
trade planning, SL/TP, position sizing, order execution, reconciliation, learning and dashboard.
