"""Read-only real-host validation for NeuralMT5.

This script never sends an order and never changes LIVE_* attestations. It verifies the
Windows/MT5 host, account, broker symbol metadata, ticks, history availability, and local
model/scaler artifacts before any live validation is attempted.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from config.settings import Settings
from config.validation import validate_settings
from layer1_market.broker_discovery import discover_symbols
from layer1_market.market_data import fetch_recent_candles
from layer1_market.mt5_client import MT5Client
from layer1_market.symbol_resolver import resolve_many
from layer1_market.validator import validate_candles
from live_readiness.audit import build_report


def main() -> int:
    settings = validate_settings(Settings())
    client = MT5Client()
    checks: list[dict[str, object]] = []
    try:
        client.connect(
            login=int(settings.mt5_login) if settings.mt5_login else None,
            password=settings.mt5_password,
            server=settings.mt5_server,
            path=settings.mt5_path,
        )
        specs = discover_symbols(client)
        resolutions = resolve_many(
            settings.symbols, specs,
            min_confidence=settings.min_symbol_resolution_confidence,
            overrides={},
            exclude_tokens=settings.symbol_exclude_tokens,
        )
        by_name = {s.name: s for s in specs}
        selected = []
        for canonical, r in resolutions.items():
            ok = r.broker_symbol is not None and r.broker_symbol in by_name
            checks.append({"check": f"symbol:{canonical}", "passed": ok,
                           "detail": r.reason, "broker_symbol": r.broker_symbol,
                           "confidence": r.resolution_confidence})
            if not ok:
                continue
            spec = by_name[r.broker_symbol]
            selected.append(spec)
            tick = client.backend.symbol_info_tick(spec.name)
            tick_ok = tick is not None and float(getattr(tick, "bid", 0) or 0) > 0 and float(getattr(tick, "ask", 0) or 0) > 0
            checks.append({"check": f"tick:{spec.name}", "passed": tick_ok,
                           "detail": "readable bid/ask" if tick_ok else "missing/invalid tick"})
            for tf, window in ((settings.htf, settings.htf_window), (settings.mtf, settings.mtf_window), (settings.ltf, settings.ltf_window)):
                candles = fetch_recent_candles(client, spec.name, tf, window, include_forming=False)
                report = validate_candles(candles, tf, decision_time_utc=datetime.now(UTC), minimum_history=window,
                                          max_missing_ratio=settings.max_missing_candle_ratio)
                checks.append({"check": f"history:{spec.name}:{tf}", "passed": report.valid,
                               "detail": "; ".join(report.reasons) if report.reasons else f"{len(candles)} closed candles"})
        readiness = build_report(settings, client.backend, selected)
        for c in readiness.checks:
            checks.append({"check": f"readiness:{c.name}", "passed": c.passed, "detail": c.detail})
    except Exception as exc:
        checks.append({"check": "preflight_exception", "passed": False, "detail": repr(exc)})
    finally:
        try:
            client.shutdown()
        except Exception:
            pass

    output = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "read_only": True,
        "orders_sent": 0,
        "passed": all(bool(c["passed"]) for c in checks),
        "checks": checks,
        "note": "Passing this report does NOT set LIVE_FAULT_INJECTION_PASSED or LIVE_SOAK_TEST_PASSED.",
    }
    Path("storage/reports").mkdir(parents=True, exist_ok=True)
    out = Path("storage/reports/real_host_preflight.json")
    out.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(json.dumps(output, indent=2, default=str))
    print(f"report={out}")
    return 0 if output["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
