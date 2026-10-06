from datetime import UTC, datetime, timedelta
import numpy as np, pytest, torch
from config.settings import Settings
from contracts.domain import EvidenceScores, NeuralOutput, Direction
from layer1_market.models import FeatureRow,TimeframeSequence,MultiTimeframeSequences
from layer2_brain.scaler import StandardScalerArtifact
from layer2_brain.network import MultiTimeframeBrain,set_deterministic
from layer2_brain.inference import infer
from layer2_brain.brainflow import calculate_brainflow
from layer2_brain.decision import decide

def seq(tf):
 t=datetime(2026,1,1,tzinfo=UTC); rows=tuple(FeatureRow(timestamp_utc=t+timedelta(minutes=i),timeframe=tf,feature_version='v1',values={'a':float(i),'b':float(i+1)}) for i in range(8)); return TimeframeSequence(timeframe=tf,decision_time_utc=rows[-1].timestamp_utc,rows=rows)
def mtf():
 a,b,c=seq('M15'),seq('M5'),seq('M1'); return MultiTimeframeSequences(decision_time_utc=c.decision_time_utc,htf=a,mtf=b,ltf=c)
def test_scaler_training_only_contract_and_schema():
 x=np.array([[1.,2.],[3.,4.]],dtype=np.float32); sc=StandardScalerArtifact.fit(x,('a','b')); assert np.allclose(sc.transform(x,('a','b')).mean(0),0)
 with pytest.raises(ValueError): sc.transform(x,('b','a'))
def test_seeded_models_are_identical():
 set_deterministic(7); a=MultiTimeframeBrain(2,8,0); set_deterministic(7); b=MultiTimeframeBrain(2,8,0)
 assert all(torch.equal(x,y) for x,y in zip(a.state_dict().values(),b.state_dict().values()))
def test_inference_is_deterministic_and_probabilities_valid():
 sc=StandardScalerArtifact.fit(np.array([[0,1],[8,9]],dtype=np.float32),('a','b')); set_deterministic(42); model=MultiTimeframeBrain(2,8,0)
 a=infer(model,mtf(),sc); b=infer(model,mtf(),sc); assert a==b; assert abs(a.buy_score+a.sell_score+a.hold_score-1)<1e-6
 assert all(0<=x<=1 for x in [a.buy_score,a.sell_score,a.hold_score,a.setup_quality,a.direction_confidence])
def test_ambiguity_forces_hold():
 n=NeuralOutput(buy_score=.52,sell_score=.44,hold_score=.04,setup_quality=.8,direction_confidence=.9,expected_favorable_excursion=1,expected_adverse_excursion=.5)
 assert decide(n,.9,Settings(_env_file=None)).direction is Direction.HOLD
def test_clear_signal_can_pass():
 s=Settings(_env_file=None); n=NeuralOutput(buy_score=.8,sell_score=.1,hold_score=.1,setup_quality=.8,direction_confidence=.9,expected_favorable_excursion=1,expected_adverse_excursion=.5)
 assert decide(n,.9,s).direction is Direction.BUY
def test_brainflow_is_zero_one():
 e=EvidenceScores(htf_strength=.8,mtf_quality=.8,ltf_quality=.8,structure_score=.8,orderflow_score=.8,regime_fitness=.8,momentum_score=.8)
 n=NeuralOutput(buy_score=.8,sell_score=.1,hold_score=.1,setup_quality=.8,direction_confidence=.9,expected_favorable_excursion=1,expected_adverse_excursion=.5)
 x=calculate_brainflow(e,n,Settings(_env_file=None)); assert 0<=x<=1

def test_model_artifact_enforces_scaler_and_feature_pairing(tmp_path):
 from layer2_brain.artifacts import save_model_artifact,load_model_artifact
 set_deterministic(3); m=MultiTimeframeBrain(2,8,0); p=tmp_path/'m.pt'; meta=save_model_artifact(m,p,feature_names=('a','b'),feature_version='f1',network_version='n1',scaler_version='s1',random_seed=3)
 assert len(meta['weights_hash'])==64
 target=MultiTimeframeBrain(2,8,0); load_model_artifact(p,target,expected_feature_names=('a','b'),expected_feature_version='f1',expected_scaler_version='s1')
 with pytest.raises(ValueError,match='scaler'): load_model_artifact(p,target,expected_feature_names=('a','b'),expected_feature_version='f1',expected_scaler_version='wrong')

def test_multitask_training_baseline_changes_weights():
 from layer2_brain.trainer import TrainingBatch,train_epoch
 set_deterministic(4); m=MultiTimeframeBrain(2,8,0); before={k:v.clone() for k,v in m.state_dict().items()}; opt=torch.optim.Adam(m.parameters(),lr=.001)
 x=torch.randn(2,8,2); b=TrainingBatch(x,x,x,torch.tensor([0,2]),torch.tensor([[.8,.7],[.2,.3]]),torch.tensor([[1.,.5],[.2,.8]]))
 loss=train_epoch(m,[b],opt); assert loss>0; assert any(not torch.equal(before[k],v) for k,v in m.state_dict().items())


def test_model_rejects_scaler_content_hash_mismatch(tmp_path):
    from layer2_brain.artifacts import save_model_artifact, load_model_artifact
    set_deterministic(4)
    m=MultiTimeframeBrain(2,8,0); p=tmp_path/'m2.pt'
    save_model_artifact(m,p,feature_names=('a','b'),feature_version='f1',network_version='n1',scaler_version='s1',scaler_hash='abc',random_seed=4)
    target=MultiTimeframeBrain(2,8,0)
    with pytest.raises(ValueError,match='content hash'):
        load_model_artifact(p,target,expected_feature_names=('a','b'),expected_feature_version='f1',expected_scaler_version='s1',expected_scaler_hash='changed')
