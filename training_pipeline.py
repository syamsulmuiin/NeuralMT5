from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import json
import math
import shutil

import numpy as np
import torch

from config.settings import Settings
from layer1_market.broker_discovery import discover_symbols
from layer1_market.features import FEATURE_VERSION, build_feature_rows
from layer1_market.market_data import fetch_recent_candles
from layer1_market.models import Candle, MultiTimeframeSequences
from layer1_market.mt5_client import MT5Client
from layer1_market.sequences import synchronize_sequences
from layer1_market.symbol_resolver import inspect_symbol_candidates, resolve_symbol
from layer1_market.timeframes import timeframe_delta
from layer2_brain.artifacts import save_model_artifact
from layer2_brain.network import NETWORK_VERSION, MultiTimeframeBrain, set_deterministic
from layer2_brain.scaler import StandardScalerArtifact
from layer2_brain.trainer import TrainingBatch, train_epoch


class TrainingDataError(RuntimeError):
    """Raised when market history cannot produce a leakage-safe training dataset."""


@dataclass(frozen=True)
class TrainingSample:
    symbol: str
    timestamp: datetime          # decision time, after LTF candle close
    label_end_time: datetime
    sequences: MultiTimeframeSequences
    direction: int  # BUY=0 SELL=1 HOLD=2
    quality: tuple[float, float]
    excursion: tuple[float, float]


def _direction_label(entry: float, atr: float, future: tuple[Candle, ...], min_rr: float) -> tuple[int, tuple[float, float], tuple[float, float]]:
    risk = max(float(atr), abs(entry) * 1e-8)
    buy_tp, buy_sl = entry + risk * min_rr, entry - risk
    sell_tp, sell_sl = entry - risk * min_rr, entry + risk
    buy_success = sell_success = None
    buy_dead = sell_dead = False
    max_up = max((c.high - entry for c in future), default=0.0)
    max_down = max((entry - c.low for c in future), default=0.0)
    for i, c in enumerate(future):
        if not buy_dead:
            tp, sl = c.high >= buy_tp, c.low <= buy_sl
            if tp and sl:
                buy_dead = True
            elif tp:
                buy_success = i
                buy_dead = True
            elif sl:
                buy_dead = True
        if not sell_dead:
            tp, sl = c.low <= sell_tp, c.high >= sell_sl
            if tp and sl:
                sell_dead = True
            elif tp:
                sell_success = i
                sell_dead = True
            elif sl:
                sell_dead = True

    if buy_success is not None and (sell_success is None or buy_success < sell_success):
        direction = 0
        favorable, adverse = max_up / risk, max_down / risk
        signed_final = (future[-1].close - entry) / risk if future else 0.0
    elif sell_success is not None and (buy_success is None or sell_success < buy_success):
        direction = 1
        favorable, adverse = max_down / risk, max_up / risk
        signed_final = (entry - future[-1].close) / risk if future else 0.0
    else:
        direction = 2
        favorable, adverse = max(max_up, max_down) / risk, min(max_up, max_down) / risk
        signed_final = 0.0

    setup_quality = max(0.0, min(1.0, favorable / (favorable + adverse + 1e-12)))
    confidence = max(0.0, min(1.0, max(0.0, signed_final))) if direction != 2 else max(0.0, min(1.0, 1.0 - min(1.0, favorable / max(min_rr, 1e-12))))
    return direction, (setup_quality, confidence), (favorable, adverse)


def _feature_names(seqs: MultiTimeframeSequences) -> tuple[str, ...]:
    names = tuple(sorted(seqs.ltf.rows[0].values))
    for seq in (seqs.htf, seqs.mtf, seqs.ltf):
        for row in seq.rows:
            if tuple(sorted(row.values)) != names:
                raise ValueError("inconsistent feature schema")
    return names


def _minimum_history(settings: Settings, timeframe: str) -> int:
    warmup = max(settings.atr_period, settings.momentum_period, settings.volatility_period) + 1
    window = {settings.htf: settings.htf_window, settings.mtf: settings.mtf_window, settings.ltf: settings.ltf_window}[timeframe]
    extra = settings.label_horizon_bars + settings.train_min_samples + settings.purge_bars + settings.embargo_bars if timeframe == settings.ltf else 0
    return window + warmup + extra


def _diagnostics_path() -> Path:
    p = Path("storage/reports/training_data_diagnostics.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _time_range(items, *, attr: str) -> dict:
    if not items:
        return {"start_utc": None, "end_utc": None, "duration_seconds": 0}
    values = [getattr(item, attr) for item in items]
    start, end = min(values), max(values)
    return {
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "duration_seconds": max(0.0, (end - start).total_seconds()),
    }


def _split_range(samples: list[TrainingSample]) -> dict:
    if not samples:
        return {"samples": 0, "decision_start_utc": None, "decision_end_utc": None, "label_end_utc": None}
    return {
        "samples": len(samples),
        "decision_start_utc": min(s.timestamp for s in samples).isoformat(),
        "decision_end_utc": max(s.timestamp for s in samples).isoformat(),
        "label_end_utc": max(s.label_end_time for s in samples).isoformat(),
    }


def build_samples(settings: Settings, client: MT5Client, *, diagnostics: dict | None = None) -> list[TrainingSample]:
    specs = discover_symbols(client)
    samples: list[TrainingSample] = []
    diag = diagnostics if diagnostics is not None else {}
    diag.clear()
    diag.update({"symbols": {}, "requested_symbols": list(settings.symbols), "total_samples": 0})
    warmup = max(settings.atr_period, settings.momentum_period, settings.volatility_period) + 4
    requested_count = max(
        settings.train_history_bars,
        settings.train_min_samples + settings.ltf_window + settings.label_horizon_bars + warmup + settings.purge_bars + settings.embargo_bars,
        settings.htf_window + warmup,
        settings.mtf_window + warmup,
    )

    for canonical in settings.symbols:
        sd: dict = {"canonical": canonical, "requested_bars": requested_count, "samples": 0}
        diag["symbols"][canonical] = sd
        sd["resolver_candidates"] = inspect_symbol_candidates(
            canonical, specs, exclude_tokens=settings.symbol_exclude_tokens
        )
        resolved = resolve_symbol(
            canonical,
            specs,
            min_confidence=settings.min_symbol_resolution_confidence,
            override=settings.symbol_override(canonical),
            exclude_tokens=settings.symbol_exclude_tokens,
        )
        sd.update({"resolution": resolved.model_dump(mode="json")})
        if not resolved.broker_symbol:
            sd["status"] = "UNRESOLVED_SYMBOL"
            continue
        symbol = resolved.broker_symbol
        if not client.backend.symbol_select(symbol, True):
            sd["status"] = "SYMBOL_SELECT_FAILED"
            sd["last_error"] = str(client.backend.last_error())
            continue

        try:
            htf_c = fetch_recent_candles(client, symbol, settings.htf, requested_count)
            mtf_c = fetch_recent_candles(client, symbol, settings.mtf, requested_count)
            ltf_c = fetch_recent_candles(client, symbol, settings.ltf, requested_count)
        except Exception as exc:
            sd["status"] = "HISTORY_FETCH_FAILED"
            sd["error"] = str(exc)
            continue

        sd["history_counts"] = {settings.htf: len(htf_c), settings.mtf: len(mtf_c), settings.ltf: len(ltf_c)}
        sd["history_ranges"] = {
            settings.htf: _time_range(htf_c, attr="time_utc"),
            settings.mtf: _time_range(mtf_c, attr="time_utc"),
            settings.ltf: _time_range(ltf_c, attr="time_utc"),
        }
        minimums = {tf: _minimum_history(settings, tf) for tf in (settings.htf, settings.mtf, settings.ltf)}
        sd["minimum_history"] = minimums
        shortages = {tf: f"{sd['history_counts'][tf]} < {minimums[tf]}" for tf in minimums if sd["history_counts"][tf] < minimums[tf]}
        if shortages:
            sd["history_shortages"] = shortages

        htf_r = build_feature_rows(htf_c, settings.htf, atr_period=settings.atr_period, momentum_period=settings.momentum_period, volatility_period=settings.volatility_period)
        mtf_r = build_feature_rows(mtf_c, settings.mtf, atr_period=settings.atr_period, momentum_period=settings.momentum_period, volatility_period=settings.volatility_period)
        ltf_r = build_feature_rows(ltf_c, settings.ltf, atr_period=settings.atr_period, momentum_period=settings.momentum_period, volatility_period=settings.volatility_period)
        sd["feature_counts"] = {settings.htf: len(htf_r), settings.mtf: len(mtf_r), settings.ltf: len(ltf_r)}
        candle_by_time = {c.time_utc: i for i, c in enumerate(ltf_c)}
        atr_by_time = {r.timestamp_utc: r.values["atr"] for r in ltf_r}
        sync_failures = 0
        candidate_rows = 0

        for row in ltf_r:
            idx = candle_by_time.get(row.timestamp_utc)
            if idx is None or idx + settings.label_horizon_bars >= len(ltf_c):
                continue
            candidate_rows += 1
            decision_time = row.timestamp_utc + timeframe_delta(settings.ltf)
            try:
                seqs = synchronize_sequences(
                    htf_rows=htf_r,
                    mtf_rows=mtf_r,
                    ltf_rows=ltf_r,
                    htf=settings.htf,
                    mtf=settings.mtf,
                    ltf=settings.ltf,
                    htf_window=settings.htf_window,
                    mtf_window=settings.mtf_window,
                    ltf_window=settings.ltf_window,
                    decision_time_utc=decision_time,
                )
            except ValueError:
                sync_failures += 1
                continue
            future = tuple(ltf_c[idx + 1: idx + 1 + settings.label_horizon_bars])
            direction, quality, excursion = _direction_label(ltf_c[idx].close, atr_by_time[row.timestamp_utc], future, settings.min_rr)
            label_end = future[-1].time_utc + timeframe_delta(settings.ltf)
            samples.append(TrainingSample(canonical, decision_time, label_end, seqs, direction, quality, excursion))
            sd["samples"] += 1

        sd["candidate_rows"] = candidate_rows
        sd["sequence_failures"] = sync_failures
        symbol_samples = [sample for sample in samples if sample.symbol == canonical]
        sd["sample_range"] = _split_range(symbol_samples)
        sd["status"] = "OK" if sd["samples"] else "NO_SAMPLES"

    samples.sort(key=lambda x: (x.timestamp, x.symbol))
    diag["total_samples"] = len(samples)
    diag["class_counts"] = {
        "BUY": sum(s.direction == 0 for s in samples),
        "SELL": sum(s.direction == 1 for s in samples),
        "HOLD": sum(s.direction == 2 for s in samples),
    }
    return samples


def split_samples(samples: list[TrainingSample], purge: int, embargo: int):
    if not samples:
        return [], [], []
    ordered = sorted(samples, key=lambda s: (s.timestamp, s.symbol))
    timestamps = sorted({s.timestamp for s in ordered})
    a_i = min(len(timestamps) - 1, max(1, int(len(timestamps) * 0.70)))
    b_i = min(len(timestamps) - 1, max(a_i + 1, int(len(timestamps) * 0.85)))
    train_cut = timestamps[a_i]
    test_cut = timestamps[b_i]
    ltf_step = timeframe_delta(ordered[0].sequences.ltf.timeframe)
    purge_delta = ltf_step * max(purge, 0)
    embargo_delta = ltf_step * max(embargo, 0)

    train = [s for s in ordered if s.timestamp < train_cut and s.label_end_time < train_cut]
    val = [s for s in ordered if s.timestamp >= train_cut + purge_delta and s.timestamp < test_cut and s.label_end_time < test_cut]
    test = [s for s in ordered if s.timestamp >= test_cut + embargo_delta]
    return train, val, test


def fit_scaler(train: list[TrainingSample], version: str = "scaler-v1") -> StandardScalerArtifact:
    if not train:
        raise ValueError("empty training split")
    names = _feature_names(train[0].sequences)
    matrices = []
    for sample in train:
        for seq in (sample.sequences.htf, sample.sequences.mtf, sample.sequences.ltf):
            matrices.append(np.asarray([[r.values[n] for n in names] for r in seq.rows], dtype=np.float32))
    matrix = np.concatenate(matrices, axis=0)
    if not np.isfinite(matrix).all():
        raise FloatingPointError("non-finite feature values in training matrix")
    return StandardScalerArtifact.fit(matrix, names, version)


def _tensor(sample: TrainingSample, scaler: StandardScalerArtifact, attr: str) -> torch.Tensor:
    seq = getattr(sample.sequences, attr)
    x = np.asarray([[r.values[n] for n in scaler.feature_names] for r in seq.rows], dtype=np.float32)
    return torch.from_numpy(scaler.transform(x, scaler.feature_names))




def compute_hierarchical_weights(samples: list[TrainingSample], power: float = 0.5) -> tuple[torch.Tensor, torch.Tensor]:
    """Return TRAIN-only balancing weights for TRADE/HOLD and BUY/SELL.

    The actionability head is binary (TRADE vs HOLD). ``trade_pos_weight`` is
    the BCE positive-class weight for TRADE. The direction head is trained only
    on BUY/SELL samples and receives normalized BUY/SELL weights. ``power``
    tempers inverse-frequency correction: 0 disables it, 0.5 uses square-root
    correction, and 1.0 uses full inverse-frequency correction for BUY/SELL.
    The TRADE/HOLD gate is always fully balanced because those are aggregate
    binary classes.
    """
    counts = np.asarray([sum(s.direction == i for s in samples) for i in range(3)], dtype=np.float64)
    if np.any(counts <= 0):
        raise TrainingDataError(
            f"training split missing class coverage: BUY={int(counts[0])} SELL={int(counts[1])} HOLD={int(counts[2])}"
        )
    buy, sell, hold = counts.tolist()
    trade = buy + sell
    # BCE pos_weight applies to TRADE=1. Fully balance TRADE/HOLD aggregate
    # contribution so the gate is not biased by BUY+SELL being the majority.
    trade_pos_weight = hold / trade
    if power <= 0:
        direction_weights = np.ones(2, dtype=np.float64)
    else:
        inv = np.asarray([trade / (2.0 * buy), trade / (2.0 * sell)], dtype=np.float64)
        direction_weights = np.power(inv, power)
        direction_weights /= direction_weights.mean()
    return (
        torch.tensor(float(trade_pos_weight), dtype=torch.float32),
        torch.tensor(direction_weights, dtype=torch.float32),
    )


def compute_class_weights(samples: list[TrainingSample], power: float = 0.5) -> torch.Tensor:
    """Compatibility diagnostic: normalized flat BUY/SELL/HOLD weights.

    Kept for reports/tests while training itself uses hierarchical weights.
    """
    counts = np.asarray([sum(s.direction == i for s in samples) for i in range(3)], dtype=np.float64)
    if np.any(counts <= 0):
        raise TrainingDataError(
            f"training split missing class coverage: BUY={int(counts[0])} SELL={int(counts[1])} HOLD={int(counts[2])}"
        )
    if power <= 0:
        weights = np.ones(3, dtype=np.float64)
    else:
        inv = counts.sum() / (len(counts) * counts)
        weights = np.power(inv, power)
        weights /= weights.mean()
    return torch.tensor(weights, dtype=torch.float32)

def batches(samples: list[TrainingSample], scaler: StandardScalerArtifact, batch_size: int, shuffle: bool, seed: int) -> list[TrainingBatch]:
    idx = np.arange(len(samples))
    if shuffle:
        np.random.default_rng(seed).shuffle(idx)
    out = []
    for start in range(0, len(idx), batch_size):
        ss = [samples[int(i)] for i in idx[start:start + batch_size]]
        out.append(TrainingBatch(
            torch.stack([_tensor(s, scaler, "htf") for s in ss]),
            torch.stack([_tensor(s, scaler, "mtf") for s in ss]),
            torch.stack([_tensor(s, scaler, "ltf") for s in ss]),
            torch.tensor([s.direction for s in ss], dtype=torch.long),
            torch.tensor([s.quality for s in ss], dtype=torch.float32),
            torch.tensor([s.excursion for s in ss], dtype=torch.float32),
        ))
    return out


def evaluate(model, samples: list[TrainingSample], scaler: StandardScalerArtifact, batch_size: int) -> dict:
    model.eval()
    correct = [0, 0, 0]
    total = [0, 0, 0]
    predicted = [0, 0, 0]
    confusion = [[0, 0, 0] for _ in range(3)]
    losses = []
    with torch.inference_mode():
        for b in batches(samples, scaler, batch_size, False, 0):
            o = model(b.htf, b.mtf, b.ltf)
            pred = o["probabilities"].argmax(dim=1)
            for y, p in zip(b.direction.tolist(), pred.tolist()):
                total[y] += 1
                predicted[p] += 1
                confusion[y][p] += 1
                correct[y] += int(y == p)
            eps = 1e-8
            loss = torch.nn.functional.nll_loss(torch.log(o["probabilities"].clamp_min(eps)), b.direction)
            losses.append(float(loss))
    recalls = [correct[i] / total[i] if total[i] else 0.0 for i in range(3)]
    precisions = [correct[i] / predicted[i] if predicted[i] else 0.0 for i in range(3)]
    f1 = [
        2.0 * precisions[i] * recalls[i] / (precisions[i] + recalls[i])
        if precisions[i] + recalls[i] > 0 else 0.0
        for i in range(3)
    ]
    names = ["BUY", "SELL", "HOLD"]
    predicted_classes = sum(v > 0 for v in predicted)
    return {
        "samples": len(samples),
        "classification_loss": sum(losses) / len(losses) if losses else math.inf,
        "balanced_accuracy": sum(recalls) / 3.0,
        "macro_f1": sum(f1) / 3.0,
        "predicted_class_coverage": predicted_classes,
        "per_class_recall": dict(zip(names, recalls)),
        "per_class_precision": dict(zip(names, precisions)),
        "per_class_f1": dict(zip(names, f1)),
        "class_counts": dict(zip(names, total)),
        "predicted_class_counts": dict(zip(names, predicted)),
        "confusion_matrix": {names[i]: dict(zip(names, confusion[i])) for i in range(3)},
    }


def dataset_digest(samples: list[TrainingSample]) -> str:
    h = hashlib.sha256()
    for s in samples:
        h.update(f"{s.symbol}|{s.timestamp.isoformat()}|{s.label_end_time.isoformat()}|{s.direction}|{s.quality}|{s.excursion}".encode())
    return h.hexdigest()


def _write_diagnostics(diag: dict) -> None:
    path = _diagnostics_path()
    try:
        path.write_text(json.dumps(diag, indent=2, default=str), encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        raise RuntimeError(f"failed to write training diagnostics {path}: {exc}") from exc



def run_diagnostics(settings: Settings) -> dict:
    """Connect to MT5 and explain exactly how many training samples can be built."""
    client = MT5Client()
    client.connect(
        login=int(settings.mt5_login) if settings.mt5_login else None,
        password=settings.mt5_password, server=settings.mt5_server, path=settings.mt5_path,
    )
    diagnostics: dict = {}
    try:
        build_samples(settings, client, diagnostics=diagnostics)
    finally:
        shutdown_error = None
        try:
            client.shutdown()
        except Exception as exc:
            shutdown_error = exc
        try:
            _write_diagnostics(diagnostics)
        except Exception:
            if shutdown_error is not None:
                raise RuntimeError(f"MT5 shutdown also failed: {shutdown_error}") from shutdown_error
            raise
        if shutdown_error is not None:
            raise RuntimeError(f"MT5 shutdown failed after diagnostics: {shutdown_error}") from shutdown_error
    return diagnostics


def run_training(settings: Settings) -> dict:
    set_deterministic(settings.random_seed)
    client = MT5Client()
    client.connect(
        login=int(settings.mt5_login) if settings.mt5_login else None,
        password=settings.mt5_password,
        server=settings.mt5_server,
        path=settings.mt5_path,
    )
    diagnostics: dict = {}
    try:
        samples = build_samples(settings, client, diagnostics=diagnostics)
    finally:
        shutdown_error = None
        try:
            client.shutdown()
        except Exception as exc:
            shutdown_error = exc
        try:
            _write_diagnostics(diagnostics)
        except Exception:
            if shutdown_error is not None:
                raise RuntimeError(f"MT5 shutdown also failed: {shutdown_error}") from shutdown_error
            raise
        if shutdown_error is not None:
            raise RuntimeError(f"MT5 shutdown failed after training data collection: {shutdown_error}") from shutdown_error

    if len(samples) < settings.train_min_samples:
        statuses = ", ".join(f"{k}:{v.get('status')} samples={v.get('samples', 0)} history={v.get('history_counts', {})}" for k, v in diagnostics.get("symbols", {}).items())
        raise TrainingDataError(
            f"insufficient training samples: {len(samples)} < {settings.train_min_samples}. "
            f"Per-symbol diagnostics: {statuses}. See {_diagnostics_path()}"
        )

    train, val, test = split_samples(samples, settings.purge_bars, settings.embargo_bars)
    if min(len(train), len(val), len(test)) == 0:
        raise TrainingDataError(f"chronological split produced an empty partition: train={len(train)} val={len(val)} test={len(test)}")

    scaler = fit_scaler(train)
    class_weights = compute_class_weights(train, settings.train_class_weight_power)
    trade_pos_weight, direction_weights = compute_hierarchical_weights(train, settings.train_class_weight_power)
    model = MultiTimeframeBrain(len(scaler.feature_names), settings.hidden_size, settings.dropout)
    opt = torch.optim.Adam(model.parameters(), lr=settings.learning_rate)
    history = []
    validation_history = []
    best_state = None
    best_epoch = 0
    best_val_macro_f1 = -math.inf
    best_val_balanced_accuracy = -math.inf
    best_val_loss = math.inf
    epochs_without_improvement = 0
    stopped_early = False

    for epoch in range(settings.epochs):
        train_batches = batches(train, scaler, settings.batch_size, True, settings.random_seed + epoch)
        train_loss = train_epoch(
            model, train_batches, opt,
            trade_pos_weight=trade_pos_weight,
            direction_weights=direction_weights,
            classification_weight=settings.train_classification_loss_weight,
            quality_weight=settings.train_quality_loss_weight,
            excursion_weight=settings.train_excursion_loss_weight,
        )
        history.append(train_loss)
        epoch_val = evaluate(model, val, scaler, settings.batch_size)
        validation_history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "balanced_accuracy": epoch_val["balanced_accuracy"],
            "macro_f1": epoch_val["macro_f1"],
            "predicted_class_coverage": epoch_val["predicted_class_coverage"],
            "classification_loss": epoch_val["classification_loss"],
            "per_class_recall": epoch_val["per_class_recall"],
            "predicted_class_counts": epoch_val["predicted_class_counts"],
        })

        # Macro-F1 is the primary checkpoint metric because it penalizes a
        # collapsed single-class predictor that can still report balanced
        # accuracy=1/3. Balanced accuracy and loss are deterministic tie-breaks.
        f1_gain = epoch_val["macro_f1"] - best_val_macro_f1
        f1_tie = abs(f1_gain) <= settings.train_early_stopping_min_delta
        balanced_gain = epoch_val["balanced_accuracy"] - best_val_balanced_accuracy
        tie_or_better = f1_tie and (
            balanced_gain > settings.train_early_stopping_min_delta
            or (abs(balanced_gain) <= settings.train_early_stopping_min_delta
                and epoch_val["classification_loss"] < best_val_loss)
        )
        improved = f1_gain > settings.train_early_stopping_min_delta or tie_or_better
        if improved or best_state is None:
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            best_epoch = epoch + 1
            best_val_macro_f1 = epoch_val["macro_f1"]
            best_val_balanced_accuracy = epoch_val["balanced_accuracy"]
            best_val_loss = epoch_val["classification_loss"]
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        print(
            f"epoch {epoch + 1}/{settings.epochs} "
            f"loss={train_loss:.6f} "
            f"val_bal_acc={epoch_val['balanced_accuracy']:.6f} "
            f"val_macro_f1={epoch_val['macro_f1']:.6f} "
            f"val_loss={epoch_val['classification_loss']:.6f}"
        )

        if epochs_without_improvement >= settings.train_early_stopping_patience:
            stopped_early = True
            print(
                f"early stopping at epoch {epoch + 1}; "
                f"restoring best epoch {best_epoch} "
                f"val_macro_f1={best_val_macro_f1:.6f} "
                f"val_bal_acc={best_val_balanced_accuracy:.6f}"
            )
            break

    if best_state is None:
        raise RuntimeError("training did not produce a model checkpoint")
    model.load_state_dict(best_state)

    val_metrics = evaluate(model, val, scaler, settings.batch_size)
    test_metrics = evaluate(model, test, scaler, settings.batch_size)
    class_ok = all(v >= settings.train_min_class_samples for v in val_metrics["class_counts"].values())
    passed = (
        val_metrics["samples"] >= max(30, settings.train_min_samples // 10)
        and class_ok
        and val_metrics["balanced_accuracy"] >= settings.train_min_balanced_accuracy
    )

    model_dir = Path("storage/models")
    scaler_dir = Path("storage/scalers")
    report_dir = Path("storage/reports")
    model_dir.mkdir(parents=True, exist_ok=True)
    scaler_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    c_model = model_dir / "challenger.pt"
    c_scaler = scaler_dir / "challenger.json"
    scaler.save(c_scaler)
    scaler_hash = hashlib.sha256(c_scaler.read_bytes()).hexdigest()
    meta = save_model_artifact(
        model,
        c_model,
        feature_names=scaler.feature_names,
        feature_version=FEATURE_VERSION,
        network_version=NETWORK_VERSION,
        scaler_version=scaler.version,
        scaler_hash=scaler_hash,
        random_seed=settings.random_seed,
    )
    report = {
        "passed": passed,
        "promotion_blockers": [] if passed else [
            *([] if class_ok else [f"validation class coverage below TRAIN_MIN_CLASS_SAMPLES={settings.train_min_class_samples}"]),
            *([] if val_metrics["balanced_accuracy"] >= settings.train_min_balanced_accuracy else ["balanced accuracy below threshold"]),
        ],
        "promoted": False,
        "dataset_hash": dataset_digest(samples),
        "feature_version": FEATURE_VERSION,
        "dataset_time_range": _split_range(samples),
        "split_time_ranges": {
            "train": _split_range(train),
            "validation": _split_range(val),
            "test": _split_range(test),
        },
        "train_samples": len(train),
        "train_class_counts": {
            "BUY": sum(s.direction == 0 for s in train),
            "SELL": sum(s.direction == 1 for s in train),
            "HOLD": sum(s.direction == 2 for s in train),
        },
        "class_weights": {
            "BUY": float(class_weights[0]),
            "SELL": float(class_weights[1]),
            "HOLD": float(class_weights[2]),
        },
        "hierarchical_weights": {
            "trade_pos_weight": float(trade_pos_weight),
            "direction_buy": float(direction_weights[0]),
            "direction_sell": float(direction_weights[1]),
        },
        "loss_weights": {
            "classification": settings.train_classification_loss_weight,
            "quality": settings.train_quality_loss_weight,
            "excursion": settings.train_excursion_loss_weight,
        },
        "val": val_metrics,
        "test": test_metrics,
        "loss_history": history,
        "validation_history": validation_history,
        "best_epoch": best_epoch,
        "epochs_completed": len(history),
        "stopped_early": stopped_early,
        "early_stopping": {
            "patience": settings.train_early_stopping_patience,
            "min_delta": settings.train_early_stopping_min_delta,
            "selection_metric": "validation macro_f1; balanced_accuracy then classification_loss tie-break",
        },
        "weights_hash": meta["weights_hash"],
        "scaler_hash": scaler_hash,
    }
    report_path = report_dir / "training_report.json"
    try:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        raise RuntimeError(f"failed to write training report {report_path}: {exc}") from exc
    return report


def promote_existing(settings: Settings) -> dict:
    report_path = Path("storage/reports/training_report.json")
    model = Path("storage/models/challenger.pt")
    scaler = Path("storage/scalers/challenger.json")
    if not report_path.exists() or not model.exists() or not scaler.exists():
        raise FileNotFoundError("challenger/report not found; run python train.py first")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read training report {report_path}: {exc}") from exc
    if not report.get("passed"):
        blockers = report.get("promotion_blockers") or ["challenger validation did not pass"]
        val = report.get("val") or {}
        detail = "; ".join(str(x) for x in blockers)
        if "balanced_accuracy" in val:
            detail += f"; validation balanced_accuracy={val['balanced_accuracy']:.6f} required>={settings.train_min_balanced_accuracy:.6f}"
        recalls = val.get("per_class_recall")
        if recalls:
            detail += "; recall=" + ",".join(f"{k}:{float(v):.4f}" for k, v in recalls.items())
        raise RuntimeError(f"promotion blocked: {detail}. Retrain a new Challenger; do not bypass the validation gate.")
    meta_path = Path(str(model) + ".json")
    if not meta_path.exists():
        raise FileNotFoundError(f"challenger metadata not found: {meta_path}")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read Challenger metadata {meta_path}: {exc}") from exc
    if meta.get("weights_hash") != report.get("weights_hash"):
        raise RuntimeError("promotion blocked: challenger weights hash/report mismatch")
    try:
        scaler_hash = hashlib.sha256(scaler.read_bytes()).hexdigest()
    except OSError as exc:
        raise RuntimeError(f"cannot read Challenger scaler {scaler}: {exc}") from exc
    if scaler_hash != report.get("scaler_hash") or meta.get("scaler_hash") != scaler_hash:
        raise RuntimeError("promotion blocked: challenger scaler hash/report mismatch")
    target_model = Path(settings.model_artifact_path)
    target_scaler = Path(settings.scaler_artifact_path)
    try:
        target_model.parent.mkdir(parents=True, exist_ok=True)
        target_scaler.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(model, target_model)
        shutil.copy2(meta_path, Path(str(target_model) + ".json"))
        shutil.copy2(scaler, target_scaler)
        report["promoted"] = True
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        raise RuntimeError(f"promotion artifact installation failed: {exc}") from exc
    return report
