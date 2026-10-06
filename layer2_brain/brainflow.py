from contracts.domain import EvidenceScores, NeuralOutput
from config.settings import Settings

def calculate_brainflow(e:EvidenceScores,n:NeuralOutput,s:Settings)->float:
    neural=max(n.buy_score,n.sell_score)
    vals=(e.htf_strength,e.mtf_quality,e.ltf_quality,e.structure_score,e.orderflow_score,e.regime_fitness,e.momentum_score,neural)
    return max(0.0,min(1.0,sum(v*w for v,w in zip(vals,s.brainflow_weights))))
