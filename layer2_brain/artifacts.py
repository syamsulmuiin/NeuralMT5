from __future__ import annotations
import hashlib, json
from pathlib import Path
import torch
from layer2_brain.network import MultiTimeframeBrain

def weights_hash(model: torch.nn.Module) -> str:
    h=hashlib.sha256()
    for name,tensor in sorted(model.state_dict().items()):
        h.update(name.encode()); h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()

def save_model_artifact(model:MultiTimeframeBrain,path:str|Path,*,feature_names:tuple[str,...],network_version:str,scaler_version:str,random_seed:int)->dict:
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    meta={'network_version':network_version,'scaler_version':scaler_version,'feature_names':list(feature_names),'random_seed':random_seed,'weights_hash':weights_hash(model)}
    torch.save({'state_dict':model.state_dict(),'metadata':meta},path)
    path.with_suffix(path.suffix+'.json').write_text(json.dumps(meta,indent=2),encoding='utf-8'); return meta

def load_model_artifact(path:str|Path,model:MultiTimeframeBrain,*,expected_feature_names:tuple[str,...],expected_scaler_version:str)->dict:
    payload=torch.load(Path(path),map_location='cpu',weights_only=True); meta=payload['metadata']
    if tuple(meta['feature_names'])!=tuple(expected_feature_names): raise ValueError('model feature schema mismatch')
    if meta['scaler_version']!=expected_scaler_version: raise ValueError('model/scaler version mismatch')
    model.load_state_dict(payload['state_dict'])
    if weights_hash(model)!=meta['weights_hash']: raise ValueError('model weights hash mismatch')
    return meta
