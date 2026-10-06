from datetime import UTC,datetime,timedelta
from layer1_market.models import Candle
from training_pipeline import _direction_label, split_samples, TrainingSample

def candle(i,h,l,c):
    return Candle(time_utc=datetime(2026,1,1,tzinfo=UTC)+timedelta(minutes=i),open=c,high=h,low=l,close=c,tick_volume=1,spread_points=1)

def test_direction_label_buy():
    d,q,e=_direction_label(100,1,(candle(1,102,99.5,101.5),),1.5)
    assert d==0 and 0<=q[0]<=1

def test_direction_label_ambiguous_is_hold():
    d,_,_=_direction_label(100,1,(candle(1,102,98,100),),1.5)
    assert d==2

from types import SimpleNamespace
import json
import pytest
import torch
from config.settings import Settings
from layer1_market.models import BrokerSymbolSpec, FeatureRow, TimeframeSequence, MultiTimeframeSequences
from layer2_brain.network import MultiTimeframeBrain
from layer2_brain.scaler import StandardScalerArtifact
from training_pipeline import evaluate, fit_scaler


def _seq_sample(direction:int, minute:int=0):
    base=datetime(2026,1,1,tzinfo=UTC)+timedelta(minutes=minute)
    def seq(tf,step):
        rs=tuple(FeatureRow(timestamp_utc=base+timedelta(minutes=i*step),timeframe=tf,feature_version='x',values={'x':float(i+1)}) for i in range(4))
        return TimeframeSequence(timeframe=tf,decision_time_utc=base+timedelta(hours=2),rows=rs)
    m=MultiTimeframeSequences(decision_time_utc=base+timedelta(hours=2),htf=seq('M15',15),mtf=seq('M5',5),ltf=seq('M1',1))
    return TrainingSample('XAUUSD',base+timedelta(hours=2),base+timedelta(hours=2,minutes=30),m,direction,(.5,.5),(1.,.5))


def test_balanced_accuracy_penalizes_missing_classes():
    samples=[_seq_sample(2,i) for i in range(10)]
    scaler=fit_scaler(samples)
    model=MultiTimeframeBrain(1,8,0)
    metrics=evaluate(model,samples,scaler,8)
    assert metrics['class_counts']['BUY']==0
    assert metrics['balanced_accuracy'] <= 1/3


def test_direction_label_excursions_are_direction_aware():
    future=(candle(1,100.4,98.0,98.5),)
    d,_,e=_direction_label(100,1,future,1.5)
    assert d==1
    assert e[0] > e[1]


def test_build_samples_from_mt5_shaped_history_is_nonzero():
    from tests.test_phase6_integration import FakeBackend
    from layer1_market.mt5_client import MT5Client
    from config.validation import validate_settings
    from training_pipeline import build_samples
    settings=validate_settings(Settings(_env_file=None,symbols=['XAUUSD'],htf='M15',mtf='M5',ltf='M1',
        htf_window=32,mtf_window=32,ltf_window=32,train_history_bars=500,train_min_samples=50,
        label_horizon_bars=10,purge_bars=10,embargo_bars=10))
    client=MT5Client(FakeBackend()); client.connect(); diagnostics={}
    try:
        samples=build_samples(settings,client,diagnostics=diagnostics)
    finally:
        client.shutdown()
    assert len(samples) >= 50
    assert diagnostics['symbols']['XAUUSD']['history_counts']['M1'] == 500
    assert diagnostics['symbols']['XAUUSD']['status'] == 'OK'


def test_compute_class_weights_upweights_minority_class():
    from training_pipeline import compute_class_weights
    samples=[_seq_sample(0,i) for i in range(8)] + [_seq_sample(1,20+i) for i in range(8)] + [_seq_sample(2,40+i) for i in range(2)]
    w=compute_class_weights(samples,0.5)
    assert w.shape == (3,)
    assert float(w[2]) > float(w[0])
    assert abs(float(w.mean())-1.0) < 1e-6


def test_evaluate_reports_confusion_and_prediction_counts():
    samples=[_seq_sample(i%3,i) for i in range(12)]
    scaler=fit_scaler(samples)
    model=MultiTimeframeBrain(1,8,0)
    metrics=evaluate(model,samples,scaler,4)
    assert set(metrics['predicted_class_counts']) == {'BUY','SELL','HOLD'}
    assert sum(metrics['predicted_class_counts'].values()) == len(samples)
    assert set(metrics['confusion_matrix']) == {'BUY','SELL','HOLD'}
    assert sum(sum(row.values()) for row in metrics['confusion_matrix'].values()) == len(samples)
