from __future__ import annotations

import random

import numpy as np
import torch
from torch import nn

from layer2_brain.encoders import TemporalEncoder

NETWORK_VERSION = "cnn-gru-hierarchical-v2"


def set_deterministic(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


class MultiTimeframeBrain(nn.Module):
    """Multi-timeframe encoder with hierarchical decision heads.

    HOLD is learned as the first-stage actionability decision (TRADE vs HOLD).
    Conditional on TRADE, a second head learns BUY vs SELL. The public output
    remains a normalized BUY/SELL/HOLD probability vector so downstream Layer 3
    contracts do not change.
    """

    def __init__(self, feature_count: int, hidden_size: int = 64, dropout: float = .2):
        super().__init__()
        self.htf = TemporalEncoder(feature_count, hidden_size, dropout)
        self.mtf = TemporalEncoder(feature_count, hidden_size, dropout)
        self.ltf = TemporalEncoder(feature_count, hidden_size, dropout)
        self.fusion = nn.Sequential(
            nn.Linear(hidden_size * 3, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.actionability = nn.Linear(hidden_size, 1)
        self.direction = nn.Linear(hidden_size, 2)
        self.quality = nn.Linear(hidden_size, 2)
        self.excursion = nn.Linear(hidden_size, 2)

    def forward(self, htf, mtf, ltf):
        z = self.fusion(torch.cat([self.htf(htf), self.mtf(mtf), self.ltf(ltf)], dim=1))
        trade_logit = self.actionability(z).squeeze(1)
        direction_logits = self.direction(z)
        trade_probability = torch.sigmoid(trade_logit)
        conditional_direction = torch.softmax(direction_logits, dim=1)
        buy = trade_probability * conditional_direction[:, 0]
        sell = trade_probability * conditional_direction[:, 1]
        hold = 1.0 - trade_probability
        probabilities = torch.stack((buy, sell, hold), dim=1)
        return {
            "probabilities": probabilities,
            "trade_logit": trade_logit,
            "direction_logits": direction_logits,
            "quality": torch.sigmoid(self.quality(z)),
            "excursion": torch.nn.functional.softplus(self.excursion(z)),
        }
