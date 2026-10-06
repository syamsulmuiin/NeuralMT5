from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock

from .schemas import RuntimeMode, RuntimeStatus


@dataclass
class RuntimeState:
    mode: RuntimeMode = RuntimeMode.ANALYSIS
    new_entries_paused: bool = False
    emergency_stop: bool = False
    reconciliation_ok: bool = True
    last_event_at_utc: datetime | None = None
    last_error: str | None = None
    _lock: RLock = field(default_factory=RLock, repr=False)

    def snapshot(self) -> RuntimeStatus:
        with self._lock:
            return RuntimeStatus(
                mode=self.mode,
                new_entries_paused=self.new_entries_paused,
                emergency_stop=self.emergency_stop,
                reconciliation_ok=self.reconciliation_ok,
                last_event_at_utc=self.last_event_at_utc,
                last_error=self.last_error,
            )

    def record_event(self) -> None:
        with self._lock:
            self.last_event_at_utc = datetime.now(UTC)
