from __future__ import annotations
import numpy as np, torch
from contracts.domain import NeuralOutput
from layer1_market.models import MultiTimeframeSequences, TimeframeSequence
from layer2_brain.scaler import StandardScalerArtifact

def _matrix(seq:TimeframeSequence, names:tuple[str,...])->np.ndarray:
    out=[]
    for row in seq.rows:
        if tuple(sorted(row.values)) != tuple(sorted(names)): raise ValueError('feature schema mismatch in sequence')
        out.append([row.values[n] for n in names])
    return np.asarray(out,dtype=np.float32)

def prepare_inputs(seqs:MultiTimeframeSequences, scaler:StandardScalerArtifact):
    tensors=[]
    for seq in (seqs.htf,seqs.mtf,seqs.ltf):
        x=_matrix(seq,scaler.feature_names); x=scaler.transform(x,scaler.feature_names); tensors.append(torch.from_numpy(x).unsqueeze(0))
    return tuple(tensors)

def infer(model,seqs,scaler)->NeuralOutput:
    model.eval(); inputs=prepare_inputs(seqs,scaler)
    with torch.inference_mode(): o=model(*inputs)
    p=o['probabilities'][0].cpu().tolist(); q=o['quality'][0].cpu().tolist(); e=o['excursion'][0].cpu().tolist()
    return NeuralOutput(buy_score=p[0],sell_score=p[1],hold_score=p[2],setup_quality=q[0],direction_confidence=q[1],expected_favorable_excursion=e[0],expected_adverse_excursion=e[1])
