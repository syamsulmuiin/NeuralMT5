from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


@dataclass(frozen=True)
class TrainingBatch:
    htf: torch.Tensor
    mtf: torch.Tensor
    ltf: torch.Tensor
    direction: torch.Tensor
    quality: torch.Tensor
    excursion: torch.Tensor


def hierarchical_classification_loss(
    outputs: dict,
    direction_target: torch.Tensor,
    *,
    trade_pos_weight: torch.Tensor | None = None,
    direction_weights: torch.Tensor | None = None,
) -> torch.Tensor:
    """Learn HOLD separately from BUY/SELL direction.

    Stage 1 learns TRADE (BUY or SELL) versus HOLD. Stage 2 learns BUY versus
    SELL only for actionable samples. This avoids forcing HOLD to compete with
    two directional classes in a single flat softmax.
    """
    trade_target = (direction_target != 2).to(dtype=torch.float32)
    gate_loss = nn.functional.binary_cross_entropy_with_logits(
        outputs["trade_logit"],
        trade_target,
        pos_weight=trade_pos_weight,
    )

    trade_mask = direction_target != 2
    if bool(trade_mask.any()):
        direction_loss = nn.functional.cross_entropy(
            outputs["direction_logits"][trade_mask],
            direction_target[trade_mask],
            weight=direction_weights,
        )
    else:
        direction_loss = outputs["direction_logits"].sum() * 0.0
    return gate_loss + direction_loss


def multitask_loss(
    outputs: dict,
    direction_target,
    quality_target,
    excursion_target,
    *,
    trade_pos_weight: torch.Tensor | None = None,
    direction_weights: torch.Tensor | None = None,
    classification_weight: float = 1.0,
    quality_weight: float = 0.25,
    excursion_weight: float = 0.25,
):
    cls = hierarchical_classification_loss(
        outputs,
        direction_target,
        trade_pos_weight=trade_pos_weight,
        direction_weights=direction_weights,
    )
    quality = nn.functional.mse_loss(outputs["quality"], quality_target)
    excursion = nn.functional.smooth_l1_loss(outputs["excursion"], excursion_target)
    return classification_weight * cls + quality_weight * quality + excursion_weight * excursion


def train_epoch(
    model,
    batches: list[TrainingBatch],
    optimizer,
    *,
    trade_pos_weight: torch.Tensor | None = None,
    direction_weights: torch.Tensor | None = None,
    classification_weight: float = 1.0,
    quality_weight: float = 0.25,
    excursion_weight: float = 0.25,
) -> float:
    if not batches:
        raise ValueError("training batches cannot be empty")
    model.train()
    total = 0.0
    for b in batches:
        optimizer.zero_grad(set_to_none=True)
        out = model(b.htf, b.mtf, b.ltf)
        loss = multitask_loss(
            out,
            b.direction,
            b.quality,
            b.excursion,
            trade_pos_weight=trade_pos_weight,
            direction_weights=direction_weights,
            classification_weight=classification_weight,
            quality_weight=quality_weight,
            excursion_weight=excursion_weight,
        )
        if not torch.isfinite(loss):
            raise FloatingPointError("non-finite training loss")
        loss.backward()
        optimizer.step()
        total += float(loss.detach())
    return total / len(batches)
