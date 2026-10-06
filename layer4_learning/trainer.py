from __future__ import annotations
import torch
from layer2_brain.trainer import train_epoch

def train_challenger(model,batches,optimizer,epochs:int)->list[float]:
    if epochs<1: raise ValueError('epochs must be >= 1')
    history=[]
    for _ in range(epochs): history.append(train_epoch(model,batches,optimizer))
    return history
