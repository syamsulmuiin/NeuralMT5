from __future__ import annotations

import asyncio
from collections import deque
from threading import RLock

from contracts.events import SystemEvent


class EventBus:
    """Thread-safe in-process fan-out bus.

    Trading producers may publish from a non-async thread. Each WebSocket subscriber
    records its owning event loop so delivery uses call_soon_threadsafe. Slow clients
    remain lossy by design and can never block the trading loop.
    """

    def __init__(self, history_size: int = 200, subscriber_queue_size: int = 100):
        self._history: deque[SystemEvent] = deque(maxlen=history_size)
        self._subscribers: dict[asyncio.Queue[SystemEvent], asyncio.AbstractEventLoop] = {}
        self._subscriber_queue_size = subscriber_queue_size
        self._lock = RLock()

    def _offer(self, queue: asyncio.Queue[SystemEvent], event: SystemEvent) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def publish_threadsafe(self, event: SystemEvent) -> None:
        with self._lock:
            self._history.append(event)
            subscribers = tuple(self._subscribers.items())
        for queue, loop in subscribers:
            if loop.is_closed():
                continue
            loop.call_soon_threadsafe(self._offer, queue, event)

    async def publish(self, event: SystemEvent) -> None:
        self.publish_threadsafe(event)

    async def subscribe(self) -> asyncio.Queue[SystemEvent]:
        queue: asyncio.Queue[SystemEvent] = asyncio.Queue(maxsize=self._subscriber_queue_size)
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subscribers[queue] = loop
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[SystemEvent]) -> None:
        with self._lock:
            self._subscribers.pop(queue, None)

    def history(self) -> list[SystemEvent]:
        with self._lock:
            return list(self._history)
