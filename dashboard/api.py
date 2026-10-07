from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config.settings import Settings
from config.validation import validate_settings

from .auth import DashboardSecurity
from .commands import CommandGateway
from .schemas import CommandReceipt, CommandRequest, PaginatedResult, RuntimeMode, SystemInfo
from .service import DashboardDataError, DashboardRepository
from .state import RuntimeState
from .websocket import EventBus

API_VERSION = "v1"
DASHBOARD_VERSION = "0.5.0"


def sqlite_path_from_url(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Phase 5 dashboard currently supports sqlite:/// database URLs only")
    return Path(database_url[len(prefix):])


def masked_config(settings: Settings) -> dict[str, Any]:
    sensitive = {"mt5_login", "mt5_password", "dashboard_auth_token"}
    result: dict[str, Any] = {}
    for name in type(settings).model_fields:
        value = getattr(settings, name)
        if name in sensitive:
            result[name] = "***" if value else None
        else:
            result[name] = value.value if hasattr(value, "value") else value
    return result


def create_app(
    settings: Settings | None = None,
    *,
    state: RuntimeState | None = None,
    event_bus: EventBus | None = None,
    command_gateway: CommandGateway | None = None,
    repository: DashboardRepository | None = None,
) -> FastAPI:
    settings = validate_settings(settings or Settings())
    state = state or RuntimeState(mode=RuntimeMode(settings.trading_mode.value))
    bus = event_bus or EventBus()
    gateway = command_gateway or CommandGateway(state)
    repository = repository or DashboardRepository(sqlite_path_from_url(settings.database_url))
    security = DashboardSecurity(host=settings.dashboard_host, auth_token=settings.dashboard_auth_token, rate_limit_per_minute=settings.dashboard_rate_limit_per_minute)

    app = FastAPI(title="NeuralMT5 Dashboard API", version=DASHBOARD_VERSION, docs_url="/docs" if settings.dashboard_docs_enabled else None, redoc_url=None)
    app.state.runtime_state = state
    app.state.event_bus = bus
    app.state.command_gateway = gateway
    app.state.repository = repository
    app.state.settings = settings

    @app.exception_handler(DashboardDataError)
    async def dashboard_data_error_handler(_request: Request, exc: DashboardDataError):
        with state._lock:
            state.last_error = str(exc)
        return JSONResponse(status_code=503, content={"detail": str(exc), "status": "DEGRADED"})

    async def secure(request: Request) -> None:
        security.verify_request(request)

    secure_dep = Depends(secure)

    @app.get("/api/v1/status", dependencies=[secure_dep])
    async def status_endpoint():
        return state.snapshot()

    @app.get("/api/v1/market", dependencies=[secure_dep])
    async def market_endpoint(limit: int = Query(50, ge=1, le=500)):
        return {"items": repository.recent_market(limit)}

    @app.get("/api/v1/brain", dependencies=[secure_dep])
    async def brain_endpoint(limit: int = Query(50, ge=1, le=500)):
        return {"items": repository.recent_brain(limit)}

    @app.get("/api/v1/opportunities", response_model=PaginatedResult, dependencies=[secure_dep])
    async def opportunities_endpoint(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
        items, total = repository.opportunities(limit, offset)
        return PaginatedResult(items=items, limit=limit, offset=offset, total=total)

    @app.get("/api/v1/positions", dependencies=[secure_dep])
    async def positions_endpoint():
        return {"items": repository.positions()}

    @app.get("/api/v1/trades", response_model=PaginatedResult, dependencies=[secure_dep])
    async def trades_endpoint(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
        items, total = repository.trades(limit, offset)
        return PaginatedResult(items=items, limit=limit, offset=offset, total=total)

    @app.get("/api/v1/trades/{trade_id}/replay", dependencies=[secure_dep])
    async def trade_replay_endpoint(trade_id: str):
        replay = repository.trade_replay(trade_id)
        if replay is None:
            raise HTTPException(status_code=404, detail="trade not found")
        return replay

    @app.get("/api/v1/performance", dependencies=[secure_dep])
    async def performance_endpoint():
        return repository.performance()

    @app.get("/api/v1/learning", dependencies=[secure_dep])
    async def learning_endpoint():
        return repository.learning()

    @app.get("/api/v1/risk", dependencies=[secure_dep])
    async def risk_endpoint():
        return repository.risk()

    @app.get("/api/v1/system", response_model=SystemInfo, dependencies=[secure_dep])
    async def system_endpoint():
        warnings: list[str] = []
        if not repository.available:
            warnings.append("database is not available yet")
        return SystemInfo(
            dashboard_version=DASHBOARD_VERSION,
            api_version=API_VERSION,
            database_available=repository.available,
            config=masked_config(settings),
            warnings=warnings,
        )

    @app.get("/api/v1/system/events", dependencies=[secure_dep])
    async def events_endpoint(limit: int = Query(50, ge=1, le=500)):
        db_events = repository.recent_events(limit)
        live_events = [event.model_dump(mode="json") for event in bus.history()[-limit:]]
        return {"database": db_events, "live": live_events}

    @app.post("/api/v1/commands", response_model=CommandReceipt, dependencies=[secure_dep])
    async def command_endpoint(request: CommandRequest):
        receipt = gateway.submit(request)
        if not receipt.accepted:
            raise HTTPException(status_code=422, detail=receipt.reason)
        return receipt

    @app.websocket("/ws/v1/events")
    async def events_websocket(ws: WebSocket):
        # WebSocket auth for remote binds uses the same bearer token via header.
        if not security.local_only:
            supplied = ws.headers.get("authorization", "")
            expected = f"Bearer {settings.dashboard_auth_token}"
            import hmac
            if not hmac.compare_digest(supplied, expected):
                await ws.close(code=4401)
                return
        await ws.accept()
        queue = await bus.subscribe()
        try:
            for event in bus.history()[-20:]:
                await ws.send_json(event.model_dump(mode="json"))
            while True:
                event = await queue.get()
                await ws.send_json(event.model_dump(mode="json"))
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            await bus.unsubscribe(queue)

    frontend = Path(__file__).with_name("frontend")
    if frontend.exists():
        app.mount("/assets", StaticFiles(directory=frontend), name="assets")

        @app.get("/", include_in_schema=False)
        async def root():
            return FileResponse(frontend / "index.html")

    return app
