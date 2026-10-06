from __future__ import annotations
import random, numpy as np, torch
from torch import nn
from layer2_brain.encoders import TemporalEncoder

def set_deterministic(seed:int)->None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)

class MultiTimeframeBrain(nn.Module):
    def __init__(self,feature_count:int,hidden_size:int=64,dropout:float=.2):
        super().__init__();
        self.htf=TemporalEncoder(feature_count,hidden_size,dropout); self.mtf=TemporalEncoder(feature_count,hidden_size,dropout); self.ltf=TemporalEncoder(feature_count,hidden_size,dropout)
        self.fusion=nn.Sequential(nn.Linear(hidden_size*3,hidden_size),nn.ReLU(),nn.Dropout(dropout))
        self.classifier=nn.Linear(hidden_size,3); self.quality=nn.Linear(hidden_size,2); self.excursion=nn.Linear(hidden_size,2)
    def forward(self,htf,mtf,ltf):
        z=self.fusion(torch.cat([self.htf(htf),self.mtf(mtf),self.ltf(ltf)],dim=1))
        return {'probabilities':torch.softmax(self.classifier(z),dim=1),'quality':torch.sigmoid(self.quality(z)),'excursion':torch.nn.functional.softplus(self.excursion(z))}
