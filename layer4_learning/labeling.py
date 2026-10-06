from __future__ import annotations
from datetime import datetime
from .models import OutcomeLabel

def label_forward_path(*,entry:float,sl:float,tp:float,highs:list[float],lows:list[float],closes:list[float],horizon_end_utc:datetime,direction_hint:str|None=None)->OutcomeLabel:
    if not highs or len(highs)!=len(lows) or len(highs)!=len(closes): raise ValueError('aligned non-empty forward path required')
    risk=abs(entry-sl)
    if risk<=0: raise ValueError('invalid risk distance')
    mfe=max(max(highs)-entry, entry-min(lows))/risk
    mae=max(entry-min(lows), max(highs)-entry)/risk
    buy_hit=next((i for i,(h,l) in enumerate(zip(highs,lows)) if h>=tp or l<=sl),None) if tp>entry>sl else None
    sell_hit=next((i for i,(h,l) in enumerate(zip(highs,lows)) if l<=tp or h>=sl),None) if tp<entry<sl else None
    direction='HOLD'
    if buy_hit is not None and tp>entry>sl:
        h,l=highs[buy_hit],lows[buy_hit]; direction='HOLD' if h>=tp and l<=sl else ('BUY' if h>=tp else 'HOLD')
    elif sell_hit is not None and tp<entry<sl:
        h,l=highs[sell_hit],lows[sell_hit]; direction='HOLD' if l<=tp and h>=sl else ('SELL' if l<=tp else 'HOLD')
    quality=max(0.0,min(1.0,mfe/(mfe+mae+1e-12)))
    conf=max(0.0,min(1.0,abs(closes[-1]-entry)/risk))
    return OutcomeLabel(direction,quality,conf,mfe,mae,horizon_end_utc)
