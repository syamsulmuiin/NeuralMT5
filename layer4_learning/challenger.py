from __future__ import annotations
import sqlite3,uuid,json
from datetime import UTC,datetime

def register_challenger(db_path,*,network_version,feature_version,scaler_version,dataset_version,weights_hash,scaler_hash,dataset_hash,config_hash,random_seed,metrics)->str:
    aid=str(uuid.uuid4())
    with sqlite3.connect(db_path) as c:
        c.execute('''INSERT INTO model_artifacts(artifact_id,role,network_version,feature_version,scaler_version,dataset_version,weights_hash,scaler_hash,dataset_hash,config_hash,random_seed,metrics_json,created_at_utc,promoted_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)''',(aid,'CHALLENGER',network_version,feature_version,scaler_version,dataset_version,weights_hash,scaler_hash,dataset_hash,config_hash,random_seed,json.dumps(metrics,sort_keys=True),datetime.now(UTC).isoformat()))
    return aid
