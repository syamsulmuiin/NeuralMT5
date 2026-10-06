from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ShadowComparison:
    observations:int; challenger_wins:int; champion_wins:int; ties:int
    @property
    def challenger_win_rate(self): return self.challenger_wins/self.observations if self.observations else 0.0

def compare(challenger_scores:list[float],champion_scores:list[float])->ShadowComparison:
    if len(challenger_scores)!=len(champion_scores): raise ValueError('aligned shadow observations required')
    cw=sum(a>b for a,b in zip(challenger_scores,champion_scores)); pw=sum(a<b for a,b in zip(challenger_scores,champion_scores))
    return ShadowComparison(len(challenger_scores),cw,pw,len(challenger_scores)-cw-pw)
