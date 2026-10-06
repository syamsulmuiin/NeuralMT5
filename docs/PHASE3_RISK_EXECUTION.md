# Phase 3 — Risk & Execution

## Scope

Phase 3 converts a validated non-HOLD Layer-2 opportunity into a broker-normalized,
risk-bounded trade plan and provides the guarded execution path. It does not change neural
weights and it cannot bypass the Risk Firewall.

## Deterministic planning

- BUY entry uses the refreshed ask; SELL entry uses the refreshed bid.
- SL is derived from volatility/noise, optional structure invalidation, broker stops level,
  and tick size. No valid SL means no plan.
- TP is derived from minimum RR, volatility and optional reachable structure. Broker tick
  normalization is applied before RR validation.
- If tick normalization or structure capping makes RR lower than `MIN_RR`, the plan is rejected.
- Layer 2 never supplies absolute SL/TP prices.

## Broker-aware sizing

Position sizing uses account equity, requested risk fraction, stop distance, broker
`tick_size`, `tick_value`, `volume_min`, `volume_max`, and `volume_step`. Volumes are floored
to the broker step so normalization cannot silently increase risk. If the broker minimum lot
already exceeds the risk budget, the trade is rejected.

## Risk Firewall

Hard vetoes cover stale quotes, spread, daily realized loss, daily committed risk,
consecutive losses, maximum positions, total exposure, and correlated exposure. Risk
rejection is final for the opportunity.

## Execution preflight

Immediately before execution the runtime must refresh the quote and revalidate:

- symbol identity;
- stale state;
- current spread;
- slippage from the planned executable price;
- trading session and new-entry cutoff;
- broker stops level after price movement;
- BUY/SELL price geometry.

A plan is never sent from a stale historical price without this preflight.

## Idempotency and duplicate prevention

`client_order_key` is deterministic for symbol + direction + decision id. A durable SQLite
claim is inserted before execution. The primary-key constraint prevents the same plan from
being sent twice, including after process restart.

## Execution modes

- `analysis`: never calls a broker and does not simulate a fill.
- `paper`: creates a paper fill only and never calls the broker.
- `live`: requires the live mode configuration gate and an explicit backend adapter.

The native MT5 adapter translates the generic request to `TRADE_ACTION_DEAL`, carries SL and
TP in the initial request, uses the discovered broker filling mode, calls `order_check`, and
accepts only explicit successful MT5 retcodes.

## Reconciliation and restart recovery

Broker position tickets and journal tickets are compared after restart. Any unmanaged broker
position or journal position missing at the broker blocks new positions until reconciled.
Existing-position safety monitoring remains independent of the new-entry gate.
