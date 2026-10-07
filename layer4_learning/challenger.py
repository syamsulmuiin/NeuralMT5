from __future__ import annotations
import json, sqlite3, uuid
from datetime import UTC, datetime


def register_challenger(db_path, *, network_version, feature_version, scaler_version, dataset_version, weights_hash, scaler_hash, dataset_hash, config_hash, random_seed, metrics) -> str:
    aid = str(uuid.uuid4())
    try:
        payload = json.dumps(metrics, sort_keys=True)
        with sqlite3.connect(db_path, timeout=10.0) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 10000")
            conn.execute('''INSERT INTO model_artifacts(artifact_id,role,network_version,feature_version,scaler_version,dataset_version,weights_hash,scaler_hash,dataset_hash,config_hash,random_seed,metrics_json,created_at_utc,promoted_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)''',(aid,'CHALLENGER',network_version,feature_version,scaler_version,dataset_version,weights_hash,scaler_hash,dataset_hash,config_hash,random_seed,payload,datetime.now(UTC).isoformat()))
        return aid
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise RuntimeError(f"failed to register Challenger artifact: {exc}") from exc
