from __future__ import annotations
from dataclasses import dataclass
import torch
from torch import nn

@dataclass(frozen=True)
class TrainingBatch:
    htf: torch.Tensor; mtf: torch.Tensor; ltf: torch.Tensor
    direction: torch.Tensor; quality: torch.Tensor; excursion: torch.Tensor

def multitask_loss(outputs:dict, direction_target, quality_target, excursion_target):
    eps=1e-8
    cls=nn.functional.nll_loss(torch.log(outputs['probabilities'].clamp_min(eps)),direction_target)
    quality=nn.functional.mse_loss(outputs['quality'],quality_target)
    excursion=nn.functional.smooth_l1_loss(outputs['excursion'],excursion_target)
    return cls + quality + excursion

def train_epoch(model, batches:list[TrainingBatch], optimizer)->float:
    if not batches: raise ValueError('training batches cannot be empty')
    model.train(); total=0.0
    for b in batches:
        optimizer.zero_grad(set_to_none=True); out=model(b.htf,b.mtf,b.ltf)
        loss=multitask_loss(out,b.direction,b.quality,b.excursion)
        if not torch.isfinite(loss): raise FloatingPointError('non-finite training loss')
        loss.backward(); optimizer.step(); total+=float(loss.detach())
    return total/len(batches)
