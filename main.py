"""NeuralMT5 safe bootstrap with Phase 7 live-readiness gates.

Default invocation validates configuration only. LIVE is opt-in and remains blocked unless
all explicit Phase 7 host-readiness gates pass.
"""

from __future__ import annotations

import argparse
import hashlib
import signal
from pathlib import Path

from config.settings import Settings, TradingMode
from config.validation import validate_settings
from dashboard.isolation import start_dashboard_isolated
from layer1_market.mt5_client import MT5Client
from layer1_market.features import FEATURE_VERSION
from layer2_brain.artifacts import load_model_artifact
from layer2_brain.network import MultiTimeframeBrain, set_deterministic
from layer2_brain.scaler import StandardScalerArtifact
from runtime.orchestrator import NeuralMT5Runtime
from runtime.worker import IsolatedWorker


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NeuralMT5 local deterministic trading runtime")
    parser.add_argument("--run", action="store_true", help="start the integrated runtime")
    parser.add_argument("--once", action="store_true", help="run one integrated market cycle then exit")
    parser.add_argument("--no-dashboard", action="store_true", help="do not start the optional dashboard")
    return parser


def _load_brain(settings: Settings):
    scaler_path = Path(settings.scaler_artifact_path)
    model_path = Path(settings.model_artifact_path)
    if not scaler_path.exists():
        raise FileNotFoundError(f"scaler artifact not found: {scaler_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"model artifact not found: {model_path}")
    scaler = StandardScalerArtifact.load(scaler_path)
    scaler_hash = hashlib.sha256(scaler_path.read_bytes()).hexdigest()
    set_deterministic(settings.random_seed)
    model = MultiTimeframeBrain(len(scaler.feature_names), settings.hidden_size, settings.dropout)
    load_model_artifact(
        model_path,
        model,
        expected_feature_names=scaler.feature_names,
        expected_feature_version=FEATURE_VERSION,
        expected_scaler_version=scaler.version,
        expected_scaler_hash=scaler_hash,
    )
    return model, scaler


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = validate_settings(Settings())
    print("NeuralMT5 configuration validated.")
    print(f"mode={settings.trading_mode} symbols={','.join(settings.symbols)}")
    print(f"timeframes={settings.htf}/{settings.mtf}/{settings.ltf}")
    print("Phases 1-7 modules are available.")

    if not args.run:
        print("Safe bootstrap only. Use --run explicitly to start MT5 integration.")
        return 0
    model, scaler = _load_brain(settings)
    runtime = NeuralMT5Runtime(settings, client=MT5Client(), model=model, scaler=scaler)
    learning_worker = IsolatedWorker()
    learning_worker.start()

    def request_stop(*_args) -> None:
        runtime.stop()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    try:
        runtime.start()
        if settings.dashboard_enabled and not args.no_dashboard:
            start_dashboard_isolated(
                settings,
                state=runtime.state,
                event_bus=runtime.bus,
                command_gateway=runtime.gateway,
            )
        runtime.run(max_cycles=1 if args.once else None)
    finally:
        learning_worker.stop()
        runtime.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
