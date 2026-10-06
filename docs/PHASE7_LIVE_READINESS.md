# Phase 7 — Live-Readiness Audit

Phase 7 hardens the live execution path but does **not** claim broker-host validation from offline tests.

## Safety gates

Live mode requires explicit credentials plus `LIVE_EXECUTION_ENABLED=true`, `LIVE_READINESS_ACKNOWLEDGED=true`, and attestations that broker-host fault-injection and soak testing have passed. Defaults are false.

The native MT5 adapter performs `order_check` before `order_send`, submits SL/TP in the initial request, preserves the broker filling mode, and treats `DONE_PARTIAL` as a distinct `PARTIALLY_FILLED` state requiring reconciliation.

## Required real-host validation before enabling live

- terminal/account trading permissions;
- broker symbol metadata and filling/execution modes;
- stops/freeze levels and minimum volume risk;
- disconnect/reconnect with an open position;
- terminal restart and journal reconciliation;
- partial fill/requote/rejection behavior where broker permits;
- server clock/session/timezone correctness;
- model/scaler artifact compatibility after restart;
- long-duration paper/analysis soak on the actual host.

Passing unit tests does not establish profitability or complete live readiness.
