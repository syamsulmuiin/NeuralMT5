from __future__ import annotations

import logging
from queue import Empty, Queue
from threading import Event, Thread
from typing import Callable

log = logging.getLogger(__name__)


class IsolatedWorker:
    """Single background worker for non-critical learning jobs.

    Exceptions are contained and jobs can never execute on the trading loop thread.
    """

    def __init__(self, name: str = "neuralmt5-learning") -> None:
        self._jobs: Queue[Callable[[], None]] = Queue()
        self._stop = Event()
        self._thread = Thread(target=self._run, name=name, daemon=True)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def submit(self, job: Callable[[], None]) -> None:
        self._jobs.put(job)

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._jobs.get(timeout=0.2)
            except Empty:
                continue
            try:
                job()
            except Exception:
                log.exception("isolated worker job failed")
            finally:
                self._jobs.task_done()
