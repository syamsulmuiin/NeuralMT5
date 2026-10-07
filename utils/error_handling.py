from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import traceback


class BoundaryOperationError(RuntimeError):
    """Adds operation context without discarding the original exception chain."""


def write_crash_report(context: str, exc: BaseException, *, directory: str | Path = "storage/logs") -> Path | None:
    """Best-effort crash report. Never masks the original failure if logging itself fails."""
    try:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        path = root / f"crash-{stamp}.log"
        body = (
            f"context={context}\n"
            f"occurred_at_utc={datetime.now(UTC).isoformat()}\n"
            f"exception={type(exc).__name__}: {exc}\n\n"
            + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        )
        path.write_text(body, encoding="utf-8")
        return path
    except Exception:
        return None
