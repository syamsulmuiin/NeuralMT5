from __future__ import annotations
from .models import PerformanceMetrics,ValidationReport

def metrics_from_r(rs:list[float])->PerformanceMetrics:
    if not rs: return PerformanceMetrics(0,0.0,0.0,0.0,0.0,0.0)
    wins=[x for x in rs if x>0]; losses=[x for x in rs if x<0]
    gp=sum(wins); gl=abs(sum(losses)); pf=(gp/gl if gl else (float('inf') if gp else 0.0))
    equity=peak=0.0; dd=0.0
    for r in rs:
        equity+=r; peak=max(peak,equity); dd=max(dd,peak-equity)
    return PerformanceMetrics(len(rs),sum(rs)/len(rs),pf,dd,sum(rs),len(wins)/len(rs))

def validate_challenger(challenger:PerformanceMetrics,champion:PerformanceMetrics|None,*,min_trades:int,max_drawdown:float,min_expectancy_r:float)->ValidationReport:
    reasons=[]
    if challenger.trades<min_trades: reasons.append('insufficient trades')
    if challenger.max_drawdown>max_drawdown: reasons.append('drawdown limit exceeded')
    if challenger.expectancy_r<=min_expectancy_r: reasons.append('expectancy threshold not exceeded')
    if champion and challenger.expectancy_r<=champion.expectancy_r: reasons.append('no expectancy improvement over champion')
    return ValidationReport(not reasons,tuple(reasons),challenger,champion)
