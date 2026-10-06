"""Run a bounded analysis/paper soak on the real MT5 host.

The script deliberately refuses LIVE mode. It is preparation evidence only and never sets
LIVE_SOAK_TEST_PASSED automatically.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from config.settings import Settings, TradingMode
from config.validation import validate_settings
from layer1_market.mt5_client import MT5Client
from main import _load_brain
from runtime.orchestrator import NeuralMT5Runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=100)
    args = parser.parse_args()
    if args.cycles < 1:
        raise SystemExit("--cycles must be >= 1")
    settings = validate_settings(Settings())
    if settings.trading_mode is TradingMode.LIVE:
        raise SystemExit("host_soak refuses TRADING_MODE=live; use analysis or paper")
    model, scaler = _load_brain(settings)
    runtime = NeuralMT5Runtime(settings, client=MT5Client(), model=model, scaler=scaler)
    failures = []
    started = datetime.now(UTC)
    try:
        runtime.start()
        for i in range(args.cycles):
            r = runtime.run_once()
            if r.errors:
                failures.append({"cycle": i + 1, "errors": r.errors, "cycle_id": r.cycle_id})
    finally:
        runtime.stop()
    report = {
        "started_at_utc": started.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "mode": settings.trading_mode.value,
        "cycles": args.cycles,
        "failures": failures,
        "passed": not failures,
        "attestation_changed": False,
        "note": "Review logs/database/reconciliation manually before setting LIVE_SOAK_TEST_PASSED=true.",
    }
    Path("storage/reports").mkdir(parents=True, exist_ok=True)
    out = Path("storage/reports/host_soak.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
