from contracts.domain import BrainflowResult, Direction, NeuralOutput
from config.settings import Settings

def decide(n:NeuralOutput,brainflow:float,s:Settings)->BrainflowResult:
    directional=[(Direction.BUY,n.buy_score),(Direction.SELL,n.sell_score)]
    directional.sort(key=lambda x:x[1],reverse=True); direction,score=directional[0]; margin=score-directional[1][1]
    reasons=[]
    if n.hold_score >= score: reasons.append('HOLD probability is highest')
    if score < s.min_direction_score: reasons.append('direction score below threshold')
    if margin < s.min_direction_margin: reasons.append('direction margin below threshold')
    if n.direction_confidence < s.min_confidence: reasons.append('confidence below threshold')
    if brainflow < s.min_brainflow_score: reasons.append('brainflow below threshold')
    if reasons: return BrainflowResult(direction=Direction.HOLD,brainflow_score=brainflow,confidence=n.direction_confidence,reason='; '.join(reasons))
    return BrainflowResult(direction=direction,brainflow_score=brainflow,confidence=n.direction_confidence,reason='thresholds satisfied')
