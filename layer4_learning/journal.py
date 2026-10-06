from __future__ import annotations
import json, sqlite3
from pathlib import Path
from datetime import UTC, datetime
from .models import ObservationRecord, OutcomeLabel

class Journal:
    def __init__(self, db_path:str|Path):
        self.db_path=Path(db_path); self.db_path.parent.mkdir(parents=True,exist_ok=True)
        schema=Path(__file__).parents[1]/'storage/database/schema.sql'
        with sqlite3.connect(self.db_path) as c: c.executescript(schema.read_text(encoding='utf-8'))
    def append_observation(self,r:ObservationRecord,broker_symbol:str,htf:str,mtf:str,ltf:str)->None:
        now=datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as c:
            c.execute('''INSERT INTO observations(observation_id,symbol,broker_symbol,observed_at_utc,timeframe_htf,timeframe_mtf,timeframe_ltf,feature_version,dataset_version,feature_payload_json,label_payload_json,created_at_utc) VALUES(?,?,?,?,?,?,?,?,?,?,NULL,?)''',(r.observation_id,r.symbol,broker_symbol,r.observed_at_utc.isoformat(),htf,mtf,ltf,r.feature_version,r.dataset_version,json.dumps(r.features,sort_keys=True),now))
    def attach_label_once(self,observation_id:str,label:OutcomeLabel)->None:
        payload=json.dumps({**label.__dict__,'horizon_end_utc':label.horizon_end_utc.isoformat()},sort_keys=True)
        with sqlite3.connect(self.db_path) as c:
            cur=c.execute('UPDATE observations SET label_payload_json=? WHERE observation_id=? AND label_payload_json IS NULL',(payload,observation_id))
            if cur.rowcount!=1: raise ValueError('observation missing or already labeled')

    def has_observation(self, observation_id:str)->bool:
        with sqlite3.connect(self.db_path) as c:
            return c.execute("SELECT 1 FROM observations WHERE observation_id=?",(observation_id,)).fetchone() is not None
