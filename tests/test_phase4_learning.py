from datetime import UTC,datetime,timedelta
import sqlite3
import pytest
from layer4_learning.dataset import DatasetRow,chronological_split,dataset_hash
from layer4_learning.labeling import label_forward_path
from layer4_learning.evaluator import metrics_from_r,validate_challenger
from layer4_learning.walkforward import expanding_walkforward
from layer4_learning.shadow import compare
from layer4_learning.drift import standardized_mean_drift
from layer4_learning.journal import Journal
from layer4_learning.models import ObservationRecord,OutcomeLabel
from layer4_learning.challenger import register_challenger
from layer4_learning.champion import ModelRegistry

NOW=datetime(2026,1,1,tzinfo=UTC)

def test_label_buy_tp_first():
    x=label_forward_path(entry=100,sl=99,tp=102,highs=[101,102.1],lows=[99.5,100],closes=[100.8,102],horizon_end_utc=NOW)
    assert x.direction=='BUY'; assert 0<=x.setup_quality<=1; assert 0<=x.direction_confidence<=1

def test_same_bar_sl_tp_is_hold_not_optimistic():
    x=label_forward_path(entry=100,sl=99,tp=101,highs=[101.2],lows=[98.8],closes=[100],horizon_end_utc=NOW)
    assert x.direction=='HOLD'

def test_split_purges_overlapping_horizon():
    rows=[]
    for i in range(20):
        ts=NOW+timedelta(minutes=i); rows.append(DatasetRow(str(i),ts,ts+timedelta(minutes=3),(float(i),),'x'))
    tr,val,te=chronological_split(rows,train_fraction=.5,val_fraction=.25,purge_bars=1,embargo_bars=1)
    assert tr and val and te
    assert all(r.horizon_end < val[0].timestamp for r in tr)
    assert all(r.horizon_end < te[0].timestamp for r in val)

def test_dataset_hash_stable_order():
    a=DatasetRow('a',NOW,NOW+timedelta(minutes=1),(1.0,),'BUY'); b=DatasetRow('b',NOW,NOW+timedelta(minutes=1),(2.0,),'HOLD')
    assert dataset_hash([a,b])==dataset_hash([b,a])

def test_metrics_and_validation():
    m=metrics_from_r([1,-.5,1,-.25])
    assert m.expectancy_r>0 and m.profit_factor>1
    report=validate_challenger(m,None,min_trades=4,max_drawdown=1,min_expectancy_r=0)
    assert report.passed

def test_walkforward_is_expanding():
    folds=expanding_walkforward(100,min_train=50,validation_size=10)
    assert len(folds)==5 and folds[0].train==slice(0,50) and folds[-1].train.stop==90

def test_shadow_alignment_required():
    with pytest.raises(ValueError): compare([.1],[.1,.2])

def test_drift_warning():
    r=standardized_mean_drift([0,1,0,1],[10,11],threshold=1)
    assert r.warning

def test_journal_observation_is_insert_only_and_label_once(tmp_path):
    db=tmp_path/'n.db'; j=Journal(db)
    obs=ObservationRecord('o1','XAUUSD',NOW,{'f':1.0},'f1','d1')
    j.append_observation(obs,'XAUUSDm','M15','M5','M1')
    with pytest.raises(sqlite3.IntegrityError): j.append_observation(obs,'XAUUSDm','M15','M5','M1')
    lab=OutcomeLabel('BUY',.8,.7,2.0,.5,NOW+timedelta(minutes=10))
    j.attach_label_once('o1',lab)
    with pytest.raises(ValueError): j.attach_label_once('o1',lab)

def _artifact(db,role,aid):
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO model_artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,role,'n','f','s','d','w','sh','dh','c',42,'{}',NOW.isoformat(),NOW.isoformat() if role=='CHAMPION' else None))

def test_promotion_requires_confirmation_and_passed_report(tmp_path):
    db=tmp_path/'n.db'; Journal(db); _artifact(db,'CHAMPION','old'); _artifact(db,'CHALLENGER','new')
    m=metrics_from_r([1]*5); report=validate_challenger(m,None,min_trades=1,max_drawdown=1,min_expectancy_r=0)
    registry=ModelRegistry(db)
    with pytest.raises(PermissionError): registry.promote('new',report,actor='user',explicit_confirmation=False)
    registry.promote('new',report,actor='user',explicit_confirmation=True)
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT role FROM model_artifacts WHERE artifact_id='new'").fetchone()[0]=='CHAMPION'
        assert c.execute("SELECT role FROM model_artifacts WHERE artifact_id='old'").fetchone()[0]=='RETIRED'

def test_auto_promotion_flag_cannot_bypass_confirmation(tmp_path):
    db=tmp_path/'n.db'; Journal(db); _artifact(db,'CHALLENGER','new')
    m=metrics_from_r([1]*5); report=validate_challenger(m,None,min_trades=1,max_drawdown=1,min_expectancy_r=0)
    with pytest.raises(ValueError,match='automatic promotion'):
        ModelRegistry(db).promote('new',report,actor='system',explicit_confirmation=True,auto_promotion_enabled=True)
