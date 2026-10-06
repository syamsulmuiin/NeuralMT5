# Phase 5 — Dashboard

## Scope

Phase 5 adds a responsive local dashboard, versioned REST API, WebSocket event stream,
read-only telemetry views, and a validated command-intent gateway. It does **not** make the
dashboard a trading layer and does not give the UI direct broker execution access.

## API contract

Implemented read endpoints:

- `GET /api/v1/status`
- `GET /api/v1/market`
- `GET /api/v1/brain`
- `GET /api/v1/opportunities`
- `GET /api/v1/positions`
- `GET /api/v1/trades`
- `GET /api/v1/performance`
- `GET /api/v1/learning`
- `GET /api/v1/risk`
- `GET /api/v1/system`
- `GET /api/v1/system/events`
- `WS /ws/v1/events`

Safe control intents use `POST /api/v1/commands`. Supported intents are pause new entry,
resume new entry, emergency-stop new entry, mode change, and Champion promotion request.
They are queued for the runtime safety gate; the dashboard does not execute broker orders.

## Live-mode and promotion confirmation

A mode change to `live` requires `explicit_confirmation=true`. A model-promotion intent also
requires an artifact ID and explicit confirmation. Layer 3 and Layer 4 still perform their
own safety checks when consuming these intents.

## Event stream

`EventBus` is a bounded fan-out queue. Slow WebSocket clients cannot block trading/event
producers. Under UI backpressure, old telemetry for that subscriber may be dropped rather
than blocking the runtime.

## Security

Default bind remains `127.0.0.1`. Loopback access does not require an auth token.

A non-loopback bind is rejected by configuration validation unless all of these are true:

- `DASHBOARD_REMOTE_ACCESS_ENABLED=true`
- `DASHBOARD_AUTH_TOKEN` is set
- `DASHBOARD_TRUST_HTTPS_PROXY=true`

Remote HTTP requests require a bearer token and use an in-memory rate limit. TLS is expected
at the trusted reverse proxy boundary. MT5 credentials and dashboard auth tokens are masked
from `/api/v1/system` and are never written to frontend storage.

## Failure isolation

`start_dashboard_isolated()` runs the server in a daemon thread and treats dashboard startup
or runtime failure as non-fatal to the trading runtime. The trading engine must not depend on
the dashboard process to monitor existing positions.

## Frontend

The bundled frontend is responsive for desktop, tablet and mobile and displays runtime mode,
entry gate, basic performance, latest neural state, risk decisions, open positions, learning
artifacts and live events. It polls low-frequency summary endpoints and uses WebSocket for
events rather than polling the event database every second.
