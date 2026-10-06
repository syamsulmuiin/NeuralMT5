from __future__ import annotations

import argparse
import json
import sys

from config.settings import Settings, TradingMode
from config.validation import validate_settings
from training_pipeline import TrainingDataError, promote_existing, run_diagnostics, run_training


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train, diagnose, or promote a local NeuralMT5 Challenger")
    actions = p.add_mutually_exclusive_group()
    actions.add_argument("--promote", action="store_true", help="promote the existing validated Challenger; does not retrain")
    actions.add_argument("--diagnose", action="store_true", help="inspect MT5 history/sample generation without training")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = validate_settings(Settings())
    if settings.trading_mode is TradingMode.LIVE:
        print("Training/diagnostics are blocked while TRADING_MODE=live", file=sys.stderr)
        return 2
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
            return 0
        report = run_training(settings)
        print(json.dumps(report, indent=2))
        print("Challenger training completed. Review storage/reports/training_report.json before promotion.")
        return 0
    except TrainingDataError as exc:
        print(f"Training data validation failed: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
