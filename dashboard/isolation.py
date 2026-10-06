from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from config.settings import Settings
from dashboard.commands import CommandGateway
from dashboard.state import RuntimeState
from dashboard.websocket import EventBus

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DashboardStartResult:
    started: bool
    reason: str
    thread: threading.Thread | None = None


def start_dashboard_isolated(
    settings: Settings,
    *,
    state: RuntimeState | None = None,
    event_bus: EventBus | None = None,
    command_gateway: CommandGateway | None = None,
) -> DashboardStartResult:
    """Start UI in a daemon thread with shared runtime controls/events when supplied."""
    if not settings.dashboard_enabled:
        return DashboardStartResult(False, "dashboard disabled")
    try:
        import uvicorn
        from .api import create_app
        app = create_app(settings, state=state, event_bus=event_bus, command_gateway=command_gateway)
    except Exception as exc:
        log.exception("Dashboard initialization failed")
        return DashboardStartResult(False, f"dashboard initialization failed: {exc}")

    def runner() -> None:
        try:
            uvicorn.run(app, host=settings.dashboard_host, port=settings.dashboard_port, log_level=settings.log_level.lower())
        except Exception:
            log.exception("Dashboard server failed; trading runtime remains independent")

    thread = threading.Thread(target=runner, name="neuralmt5-dashboard", daemon=True)
    thread.start()
    return DashboardStartResult(True, "dashboard started", thread)
