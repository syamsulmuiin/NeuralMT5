from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Fold:
    train:slice; validation:slice

def expanding_walkforward(n:int,*,min_train:int,validation_size:int,step:int|None=None)->list[Fold]:
    if min_train<=0 or validation_size<=0 or n<min_train+validation_size: return []
    step=step or validation_size; out=[]; end=min_train
    while end+validation_size<=n:
        out.append(Fold(slice(0,end),slice(end,end+validation_size))); end+=step
    return out
