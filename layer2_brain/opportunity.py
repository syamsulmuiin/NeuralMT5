from __future__ import annotations
from contracts.domain import BrainflowResult, EvidenceScores, NeuralOutput
from config.settings import Settings
from layer2_brain.brainflow import calculate_brainflow
from layer2_brain.decision import decide

def evaluate_neural_opportunity(neural:NeuralOutput,evidence:EvidenceScores,settings:Settings)->BrainflowResult:
    """Aggregate evidence and classify edge. This does not create Entry/SL/TP; Layer 3 owns those."""
    score=calculate_brainflow(evidence,neural,settings)
    return decide(neural,score,settings)
