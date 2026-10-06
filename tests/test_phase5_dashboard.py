from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from config.settings import Settings
from config.validation import validate_settings
from contracts.events import EventType, SystemEvent
from dashboard.api import create_app, masked_config
from dashboard.commands import CommandGateway
from dashboard.schemas import CommandRequest, CommandType, RuntimeMode
from dashboard.state import RuntimeState
from dashboard.websocket import EventBus
from layer4_learning.journal import Journal


def settings(**overrides):
    return Settings(_env_file=None, database_url="sqlite:///:memory-does-not-exist.db", **overrides)


def test_required_api_routes_exist():
    app = create_app(settings())
    paths = {route.path for route in app.routes}
    for required in {
        "/api/v1/status", "/api/v1/market", "/api/v1/brain", "/api/v1/opportunities",
        "/api/v1/positions", "/api/v1/trades", "/api/v1/performance", "/api/v1/learning",
        "/api/v1/risk", "/api/v1/system", "/ws/v1/events",
    }:
        assert required in paths


def test_status_and_empty_database_are_safe():
    with TestClient(create_app(settings())) as client:
        assert client.get("/api/v1/status").status_code == 200
        r = client.get("/api/v1/system")
        assert r.status_code == 200
        assert r.json()["database_available"] is False


def test_secrets_are_masked():
    s = settings(mt5_login="123", mt5_password="secret", dashboard_auth_token="token")
    cfg = masked_config(s)
    assert cfg["mt5_login"] == "***"
    assert cfg["mt5_password"] == "***"
    assert cfg["dashboard_auth_token"] == "***"
    assert "secret" not in str(cfg)


def test_live_mode_requires_explicit_confirmation():
    state = RuntimeState()
    gateway = CommandGateway(state)
    rejected = gateway.submit(CommandRequest(command=CommandType.SET_MODE, mode=RuntimeMode.LIVE))
    assert rejected.accepted is False
    accepted = gateway.submit(CommandRequest(command=CommandType.SET_MODE, mode=RuntimeMode.LIVE, explicit_confirmation=True))
    assert accepted.accepted is True
    assert state.mode is RuntimeMode.ANALYSIS  # queueing must not mutate runtime directly


def test_promotion_requires_confirmation_and_artifact():
    gateway = CommandGateway(RuntimeState())
    a = gateway.submit(CommandRequest(command=CommandType.PROMOTE_MODEL, artifact_id="challenger"))
    b = gateway.submit(CommandRequest(command=CommandType.PROMOTE_MODEL, explicit_confirmation=True))
    c = gateway.submit(CommandRequest(command=CommandType.PROMOTE_MODEL, artifact_id="challenger", explicit_confirmation=True))
    assert not a.accepted and not b.accepted and c.accepted


def test_emergency_stop_cannot_be_resumed_until_runtime_clears_it():
    state = RuntimeState()
    gateway = CommandGateway(state)
    gateway.apply_runtime_control(CommandRequest(command=CommandType.EMERGENCY_STOP_NEW_ENTRY))
    assert state.emergency_stop and state.new_entries_paused
    with pytest.raises(PermissionError):
        gateway.apply_runtime_control(CommandRequest(command=CommandType.RESUME_NEW_ENTRY))


def test_remote_bind_requires_security_controls():
    with pytest.raises(ValueError, match="REMOTE_ACCESS"):
        validate_settings(settings(dashboard_host="0.0.0.0"))
    with pytest.raises(ValueError, match="AUTH_TOKEN"):
        validate_settings(settings(dashboard_host="0.0.0.0", dashboard_remote_access_enabled=True))
    s = settings(dashboard_host="0.0.0.0", dashboard_remote_access_enabled=True, dashboard_auth_token="abc", dashboard_trust_https_proxy=True)
    assert validate_settings(s) is s


def test_remote_http_requires_bearer_token():
    s = settings(dashboard_host="0.0.0.0", dashboard_remote_access_enabled=True, dashboard_auth_token="abc", dashboard_trust_https_proxy=True)
    with TestClient(create_app(s)) as client:
        assert client.get("/api/v1/status").status_code == 401
        assert client.get("/api/v1/status", headers={"Authorization": "Bearer abc"}).status_code == 200


def test_event_bus_fanout_and_history():
    async def run():
        bus = EventBus(history_size=2, subscriber_queue_size=2)
        q = await bus.subscribe()
        event = SystemEvent(event_type=EventType.SYSTEM_WARNING, occurred_at_utc=datetime.now(UTC), source="test")
        await bus.publish(event)
        received = await asyncio.wait_for(q.get(), 0.2)
        assert received.event_id == event.event_id
        assert bus.history()[-1].event_id == event.event_id
        await bus.unsubscribe(q)
    asyncio.run(run())


def test_websocket_replays_history():
    bus = EventBus()
    event = SystemEvent(event_type=EventType.MARKET_UPDATE, occurred_at_utc=datetime.now(UTC), source="test")
    asyncio.run(bus.publish(event))
    with TestClient(create_app(settings(), event_bus=bus)) as client:
        with client.websocket_connect("/ws/v1/events") as ws:
            payload = ws.receive_json()
            assert payload["event_type"] == "MARKET_UPDATE"


def test_dashboard_sources_do_not_import_execution_adapter():
    from pathlib import Path
    root = Path(__file__).parents[1] / "dashboard"
    source = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
    assert "layer3_execution.mt5_execution_adapter" not in source
    assert ".order_send(" not in source


def test_api_command_rejects_unconfirmed_live():
    with TestClient(create_app(settings())) as client:
        r = client.post("/api/v1/commands", json={"command":"SET_MODE", "mode":"live"})
        assert r.status_code == 422

def test_trade_replay_route_exists():
    app = create_app(settings())
    assert "/api/v1/trades/{trade_id}/replay" in {route.path for route in app.routes}


def test_dashboard_initialization_failure_is_contained():
    from dashboard.isolation import start_dashboard_isolated
    bad = Settings(_env_file=None, database_url="postgresql://unsupported")
    result = start_dashboard_isolated(bad)
    assert result.started is False
    assert "initialization failed" in result.reason
