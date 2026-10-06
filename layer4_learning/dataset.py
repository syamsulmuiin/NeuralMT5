from __future__ import annotations
import hashlib,json
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class DatasetRow:
    observation_id:str; timestamp:datetime; horizon_end:datetime; features:tuple[float,...]; label:object

def chronological_split(rows:list[DatasetRow],train_fraction=.7,val_fraction=.15,purge_bars=0,embargo_bars=0):
    if not rows: raise ValueError('rows required')
    ordered=sorted(rows,key=lambda r:r.timestamp); n=len(ordered)
    a=max(1,int(n*train_fraction)); b=max(a+1,int(n*(train_fraction+val_fraction)))
    train=ordered[:a]; val=ordered[min(n,a+purge_bars):b]; test=ordered[min(n,b+embargo_bars):]
    if train and val:
        cutoff=val[0].timestamp; train=[r for r in train if r.horizon_end < cutoff]
    if val and test:
        cutoff=test[0].timestamp; val=[r for r in val if r.horizon_end < cutoff]
    return train,val,test

def dataset_hash(rows:list[DatasetRow])->str:
    payload=[(r.observation_id,r.timestamp.isoformat(),r.horizon_end.isoformat(),r.features,str(r.label)) for r in sorted(rows,key=lambda x:x.observation_id)]
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
