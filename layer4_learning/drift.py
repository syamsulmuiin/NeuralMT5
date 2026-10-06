from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class DriftResult:
    score:float; warning:bool

def standardized_mean_drift(reference:list[float],current:list[float],threshold:float=1.0)->DriftResult:
    if len(reference)<2 or not current: raise ValueError('insufficient drift samples')
    mean=sum(reference)/len(reference); var=sum((x-mean)**2 for x in reference)/(len(reference)-1); sd=math.sqrt(var)
    score=abs(sum(current)/len(current)-mean)/(sd+1e-12)
    return DriftResult(score,score>=threshold)
