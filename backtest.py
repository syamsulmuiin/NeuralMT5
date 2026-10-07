from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
import sys

from config.settings import Settings, TradingMode
from config.validation import validate_settings
from layer1_market.broker_discovery import discover_symbols
from layer1_market.market_data import fetch_recent_candles
from layer1_market.mt5_client import MT5Client
from layer1_market.symbol_resolver import inspect_symbol_candidates, resolve_symbol
from layer1_market.features import FEATURE_VERSION
from layer2_brain.artifacts import load_model_artifact
from layer2_brain.network import NETWORK_VERSION, MultiTimeframeBrain, set_deterministic
from layer2_brain.scaler import StandardScalerArtifact
from layer4_learning.backtest import run_historical_pipeline
from utils.error_handling import write_crash_report


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run NeuralMT5 historical backtest with the active Champion")
    p.add_argument("--bars", type=int, default=None, help="override BACKTEST_HISTORY_BARS for this run")
    p.add_argument("--symbol", action="append", default=None, help="canonical symbol to backtest; repeat for multiple symbols")
    return p


def _load_champion(settings: Settings):
    scaler_path = Path(settings.scaler_artifact_path)
    model_path = Path(settings.model_artifact_path)
    if not scaler_path.exists():
        raise FileNotFoundError(f"scaler artifact not found: {scaler_path}; run train.py then train.py --promote")
    if not model_path.exists():
        raise FileNotFoundError(f"model artifact not found: {model_path}; run train.py then train.py --promote")
    scaler = StandardScalerArtifact.load(scaler_path)
    scaler_hash = hashlib.sha256(scaler_path.read_bytes()).hexdigest()
    set_deterministic(settings.random_seed)
    model = MultiTimeframeBrain(len(scaler.feature_names), settings.hidden_size, settings.dropout)
    meta = load_model_artifact(
        model_path,
        model,
        expected_feature_names=scaler.feature_names,
        expected_feature_version=FEATURE_VERSION,
        expected_scaler_version=scaler.version,
        expected_scaler_hash=scaler_hash,
        expected_network_version=NETWORK_VERSION,
    )
    model.eval()
    return model, scaler, meta




def _strict_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _strict_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_json(v) for v in value]
    return value

def _write_reports(report: dict, trades: list[dict]) -> None:
    out = Path("storage/reports")
    fields = [
        "symbol", "broker_symbol", "decision_time_utc", "entry_time_utc", "exit_time_utc",
        "direction", "entry", "stop_loss", "take_profit", "exit_price", "exit_reason", "realized_r",
    ]
    try:
        out.mkdir(parents=True, exist_ok=True)
        (out / "backtest_report.json").write_text(json.dumps(_strict_json(report), indent=2, default=str, allow_nan=False), encoding="utf-8")
        path = out / "backtest_trades.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for row in trades:
                w.writerow({k: row.get(k) for k in fields})
    except (OSError, TypeError, ValueError, csv.Error) as exc:
        raise RuntimeError(f"failed to write backtest reports in {out}: {exc}") from exc


def run_backtest(settings: Settings, *, bars: int | None = None, symbols: list[str] | None = None) -> dict:
    if settings.trading_mode is TradingMode.LIVE:
        raise RuntimeError("historical backtest is blocked while TRADING_MODE=live")
    count = int(bars if bars is not None else settings.backtest_history_bars)
    if count < 500:
        raise ValueError("backtest requires at least 500 bars")
    requested = [s.upper() for s in (symbols or list(settings.symbols))]
    model, scaler, meta = _load_champion(settings)
    client = MT5Client()
    report: dict = {
        "feature_version": FEATURE_VERSION,
        "network_version": meta.get("network_version"),
        "weights_hash": meta.get("weights_hash"),
        "requested_bars": count,
        "initial_equity": settings.backtest_initial_equity,
        "timeframes": {"htf": settings.htf, "mtf": settings.mtf, "ltf": settings.ltf},
        "symbols": {},
    }
    all_trades: list[dict] = []
    client.connect(
        login=int(settings.mt5_login) if settings.mt5_login else None,
        password=settings.mt5_password,
        server=settings.mt5_server,
        path=settings.mt5_path,
    )
    try:
        specs = discover_symbols(client)
        spec_by_name = {s.name: s for s in specs}
        for canonical in requested:
            entry: dict = {"canonical": canonical}
            report["symbols"][canonical] = entry
            entry["resolver_candidates"] = inspect_symbol_candidates(
                canonical, specs, exclude_tokens=settings.symbol_exclude_tokens
            )[:10]
            resolved = resolve_symbol(
                canonical,
                specs,
                min_confidence=settings.min_symbol_resolution_confidence,
                override=settings.symbol_override(canonical),
                exclude_tokens=settings.symbol_exclude_tokens,
            )
            entry["resolution"] = resolved.model_dump(mode="json")
            if not resolved.broker_symbol:
                entry["status"] = "UNRESOLVED_SYMBOL"
                continue
            broker_symbol = resolved.broker_symbol
            if not client.backend.symbol_select(broker_symbol, True):
                entry["status"] = "SYMBOL_SELECT_FAILED"
                entry["last_error"] = str(client.backend.last_error())
                continue
            spec = spec_by_name[broker_symbol]
            candles = {
                settings.htf: fetch_recent_candles(client, broker_symbol, settings.htf, count),
                settings.mtf: fetch_recent_candles(client, broker_symbol, settings.mtf, count),
                settings.ltf: fetch_recent_candles(client, broker_symbol, settings.ltf, count),
            }
            entry["history_counts"] = {tf: len(v) for tf, v in candles.items()}
            minimum_ltf = settings.ltf_window + max(
                settings.atr_period, settings.momentum_period, settings.volatility_period,
                settings.regime_lookback, settings.orderflow_lookback,
            ) + settings.structure_pivot_left + settings.structure_pivot_right + 6
            if len(candles[settings.ltf]) < minimum_ltf:
                entry["status"] = "INSUFFICIENT_HISTORY"
                entry["minimum_ltf_history"] = minimum_ltf
                continue
            result = run_historical_pipeline(
                canonical_symbol=canonical,
                spec=spec,
                candles_by_timeframe=candles,
                model=model,
                scaler=scaler,
                settings=settings,
                initial_equity=settings.backtest_initial_equity,
            )
            entry["status"] = "OK"
            entry["metrics"] = asdict(result.metrics)
            entry["trades"] = len(result.trades)
            for t in result.trades:
                row = asdict(t)
                row["symbol"] = canonical
                row["broker_symbol"] = broker_symbol
                row["direction"] = t.direction.value
                all_trades.append(row)
    finally:
        client.shutdown()

    completed = [v for v in report["symbols"].values() if v.get("status") == "OK"]
    report["completed_symbols"] = len(completed)
    report["total_trades"] = len(all_trades)
    _write_reports(report, all_trades)
    return report


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = validate_settings(Settings())
        report = run_backtest(settings, bars=args.bars, symbols=args.symbol)
        print(json.dumps(_strict_json(report), indent=2, default=str, allow_nan=False))
        print("Backtest reports saved to storage/reports/backtest_report.json and backtest_trades.csv")
        if report["completed_symbols"] == 0:
            print("No symbol completed backtest; review the report before forward testing.", file=sys.stderr)
            return 2
        return 0
    except (FileNotFoundError, RuntimeError, ValueError, ConnectionError, OSError) as exc:
        print(f"Backtest failed: {exc}", file=sys.stderr)
        print("Next step: correct the reported prerequisite/data/artifact problem, then rerun python backtest.py.", file=sys.stderr)
        return 2
    except Exception as exc:
        path = write_crash_report("backtest", exc)
        print(f"Unexpected backtest failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        if path is not None:
            print(f"Technical traceback saved to {path}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
