from __future__ import annotations

import argparse
import json
import sys

from config.settings import Settings, TradingMode
from config.validation import validate_settings
from training_pipeline import TrainingDataError, promote_existing, run_diagnostics, run_training
from utils.error_handling import write_crash_report


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train, diagnose, or promote a local NeuralMT5 Challenger")
    actions = p.add_mutually_exclusive_group()
    actions.add_argument("--promote", action="store_true", help="promote the existing validated Challenger; does not retrain")
    actions.add_argument("--diagnose", action="store_true", help="inspect MT5 history/sample generation without training")
    return p


def _print_next_steps(action: str, exc: Exception) -> None:
    print(f"NeuralMT5 {action} could not continue: {exc}", file=sys.stderr)
    if action == "promotion":
        print("Next step: review storage/reports/training_report.json.", file=sys.stderr)
        print("If passed=false, run: python train.py  (train a new Challenger).", file=sys.stderr)
        print("Only retry: python train.py --promote  after passed=true.", file=sys.stderr)
    elif action == "training":
        print("Next step: run python train.py --diagnose and review storage/reports/training_data_diagnostics.json.", file=sys.stderr)
    else:
        print("Next step: verify MT5 connection, symbol resolution, and history with python train.py --diagnose.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = validate_settings(Settings())
    except Exception as exc:
        print(f"Configuration validation failed: {exc}", file=sys.stderr)
        print("Next step: compare .env with .env.example, fix the reported key, then rerun python main.py.", file=sys.stderr)
        return 2
    if settings.trading_mode is TradingMode.LIVE:
        print("Training/diagnostics are blocked while TRADING_MODE=live", file=sys.stderr)
        print("Next step: set TRADING_MODE=analysis (or paper) before training/diagnostics.", file=sys.stderr)
        return 2
    action = "diagnostics" if args.diagnose else "promotion" if args.promote else "training"
    try:
        if args.diagnose:
            report = run_diagnostics(settings)
            print(json.dumps(report, indent=2))
            print("Diagnostics saved to storage/reports/training_data_diagnostics.json")
            return 0
        if args.promote:
            report = promote_existing(settings)
            print(json.dumps(report, indent=2))
            print("Existing validated Challenger promoted to Champion.")
            print("Next step: python backtest.py")
            return 0
        report = run_training(settings)
        print(json.dumps(report, indent=2))
        print("Challenger training completed. Review storage/reports/training_report.json before promotion.")
        if report.get("passed"):
            print("Validation passed. Next step: python train.py --promote")
        else:
            print("Validation did not pass. Do NOT promote; inspect promotion_blockers/validation metrics and retrain after correcting the cause.")
        return 0
    except (TrainingDataError, FileNotFoundError, RuntimeError, ValueError, ConnectionError) as exc:
        _print_next_steps(action, exc)
        return 2
    except Exception as exc:
        path = write_crash_report(f"train:{action}", exc)
        print(f"Unexpected NeuralMT5 {action} failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        if path is not None:
            print(f"Technical traceback saved to {path}", file=sys.stderr)
        print("Do not bypass safety gates; inspect the crash report and correct the root cause before retrying.", file=sys.stderr)
        return 3



if __name__ == "__main__":
    raise SystemExit(main())
