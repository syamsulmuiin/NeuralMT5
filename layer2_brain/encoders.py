from __future__ import annotations
import torch
from torch import nn

class TemporalEncoder(nn.Module):
    def __init__(self,input_size:int,hidden_size:int,dropout:float):
        super().__init__(); channels=max(8,hidden_size//2)
        self.conv=nn.Conv1d(input_size,channels,kernel_size=3,padding=1)
        self.act=nn.ReLU(); self.gru=nn.GRU(channels,hidden_size,batch_first=True)
        self.dropout=nn.Dropout(dropout)
    def forward(self,x:torch.Tensor)->torch.Tensor:
        x=self.act(self.conv(x.transpose(1,2))).transpose(1,2)
        _,h=self.gru(x); return self.dropout(h[-1])
