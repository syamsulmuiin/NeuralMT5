from __future__ import annotations

from datetime import UTC, datetime
from queue import Empty, Queue
from threading import RLock
from uuid import uuid4

from .schemas import CommandReceipt, CommandRequest, CommandType, RuntimeMode
from .state import RuntimeState


class CommandGateway:
    """Queues validated intents for the runtime. It has no broker/order API dependency."""

    def __init__(self, state: RuntimeState):
        self.state = state
        self._queue: Queue[tuple[str, CommandRequest]] = Queue()
        self._seen: set[str] = set()
        self._lock = RLock()

    def submit(self, request: CommandRequest) -> CommandReceipt:
        now = datetime.now(UTC)
        reason = self._validate(request)
        if reason is not None:
            return CommandReceipt(command_id=str(uuid4()), accepted=False, reason=reason, created_at_utc=now)
        command_id = str(uuid4())
        with self._lock:
            self._seen.add(command_id)
        self._queue.put((command_id, request))
        return CommandReceipt(command_id=command_id, accepted=True, reason="queued for runtime safety gate", created_at_utc=now)

    def next_command(self, timeout: float = 0.0) -> tuple[str, CommandRequest] | None:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def _validate(self, request: CommandRequest) -> str | None:
        if request.command is CommandType.SET_MODE:
            if request.mode is None:
                return "mode is required"
            if request.mode is RuntimeMode.LIVE and not request.explicit_confirmation:
                return "explicit confirmation is required for LIVE mode"
        elif request.command is CommandType.PROMOTE_MODEL:
            if not request.artifact_id:
                return "artifact_id is required"
            if not request.explicit_confirmation:
                return "explicit confirmation is required for model promotion"
        elif request.mode is not None or request.artifact_id is not None:
            return "unexpected command parameters"
        return None

    def apply_runtime_control(self, request: CommandRequest) -> None:
        """Used by the runtime only after its own safety checks have accepted the intent."""
        with self.state._lock:
            if request.command is CommandType.PAUSE_NEW_ENTRY:
                self.state.new_entries_paused = True
            elif request.command is CommandType.RESUME_NEW_ENTRY:
                if self.state.emergency_stop:
                    raise PermissionError("emergency stop must be cleared by the runtime before resume")
                self.state.new_entries_paused = False
            elif request.command is CommandType.EMERGENCY_STOP_NEW_ENTRY:
                self.state.emergency_stop = True
                self.state.new_entries_paused = True
            elif request.command is CommandType.SET_MODE and request.mode is not None:
                self.state.mode = request.mode
