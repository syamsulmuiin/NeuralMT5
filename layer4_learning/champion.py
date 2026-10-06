from __future__ import annotations
import json,sqlite3,uuid
from datetime import UTC,datetime
from pathlib import Path
from .models import ValidationReport

class ModelRegistry:
    def __init__(self,db_path:str|Path): self.db_path=Path(db_path)
    def promote(self,challenger_id:str,report:ValidationReport,*,actor:str,explicit_confirmation:bool,auto_promotion_enabled:bool=False)->str:
        if auto_promotion_enabled: raise ValueError('automatic promotion is disabled by safety contract')
        if not explicit_confirmation: raise PermissionError('explicit promotion confirmation required')
        if not report.passed: raise ValueError('challenger validation did not pass')
        pid=str(uuid.uuid4()); now=datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as c:
            row=c.execute("SELECT artifact_id FROM model_artifacts WHERE role='CHAMPION' ORDER BY promoted_at_utc DESC LIMIT 1").fetchone(); old=row[0] if row else None
            if old: c.execute("UPDATE model_artifacts SET role='RETIRED' WHERE artifact_id=?",(old,))
            cur=c.execute("UPDATE model_artifacts SET role='CHAMPION',promoted_at_utc=? WHERE artifact_id=? AND role='CHALLENGER'",(now,challenger_id))
            if cur.rowcount!=1: raise ValueError('challenger artifact not found')
            c.execute('INSERT INTO promotion_audit(promotion_id,occurred_at_utc,old_champion_artifact_id,new_champion_artifact_id,validation_report_json,action,actor) VALUES(?,?,?,?,?,?,?)',(pid,now,old,challenger_id,json.dumps({'passed':report.passed,'reasons':report.reasons}), 'PROMOTED',actor))
        return pid
