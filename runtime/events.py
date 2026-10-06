from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from contracts.events import EventType, SystemEvent
from dashboard.state import RuntimeState
from dashboard.websocket import EventBus
from runtime.store import RuntimeStore


class RuntimeEventPublisher:
    def __init__(self, store: RuntimeStore, state: RuntimeState, bus: EventBus | None = None) -> None:
        self.store = store
        self.state = state
        self.bus = bus

    def emit(self, event_type: EventType, *, source: str, payload: dict[str, Any] | None = None, correlation_id: str | None = None) -> SystemEvent:
        event = SystemEvent(
            event_type=event_type,
            occurred_at_utc=datetime.now(UTC),
            source=source,
            correlation_id=correlation_id,
            payload=payload or {},
        )
        self.store.record_event(str(event.event_id), event.event_type.value, event.occurred_at_utc, source, correlation_id, event.payload)
        self.state.record_event()
        if self.bus is not None:
            self.bus.publish_threadsafe(event)
        return event
