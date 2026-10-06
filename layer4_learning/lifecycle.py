from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .challenger import register_challenger
from .evaluator import validate_challenger
from .models import PerformanceMetrics, ValidationReport
from .shadow import ShadowComparison, compare


@dataclass(frozen=True)
class ChallengerLifecycleResult:
    artifact_id: str | None
    validation: ValidationReport
    shadow: ShadowComparison
    ready_for_manual_promotion: bool


def run_challenger_lifecycle(
    *, db_path: Any, train: Callable[[], Any], evaluate: Callable[[Any], PerformanceMetrics],
    champion_metrics: PerformanceMetrics | None, challenger_shadow_scores: list[float],
    champion_shadow_scores: list[float], min_trades: int, max_drawdown: float,
    min_expectancy_r: float, artifact: dict[str, Any],
) -> ChallengerLifecycleResult:
    """Train -> evaluate -> shadow -> register CHALLENGER, never auto-promote.

    The caller supplies the concrete training job so this coordinator remains
    framework-independent. Registration occurs only after validation and an
    aligned shadow comparison that is not worse than the current champion.
    """
    trained = train()
    metrics = evaluate(trained)
    report = validate_challenger(metrics, champion_metrics, min_trades=min_trades,
                                 max_drawdown=max_drawdown, min_expectancy_r=min_expectancy_r)
    shadow = compare(challenger_shadow_scores, champion_shadow_scores)
    shadow_ok = shadow.observations > 0 and shadow.challenger_wins >= shadow.champion_wins
    ready = report.passed and shadow_ok
    artifact_id = None
    if ready:
        artifact_id = register_challenger(db_path, metrics=metrics.__dict__, **artifact)
    return ChallengerLifecycleResult(artifact_id, report, shadow, ready)
