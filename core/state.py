# pulsecheck/core/state.py
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional

class LoopStateRepository:
    def __init__(self, db_path="pulsecheck_state.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute('pragma journal_mode=wal')
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS loop_execution_state (
                    incident_id TEXT,
                    loop_identifier TEXT,
                    execution_status TEXT,
                    context_data TEXT,
                    last_modified TIMESTAMP,
                    PRIMARY KEY (incident_id, loop_identifier)
                )
            """)
            conn.commit()

    def persist_state(self, incident_id: str, loop_identifier: str, status: str, context_data: dict):
        """Writes the current loop state to the durable storage."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO loop_execution_state (incident_id, loop_identifier, execution_status, context_data, last_modified)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(incident_id, loop_identifier) 
                DO UPDATE SET 
                    execution_status=excluded.execution_status,
                    context_data=excluded.context_data,
                    last_modified=excluded.last_modified
            """, (incident_id, loop_identifier, status, json.dumps(context_data), datetime.utcnow().isoformat()))
            conn.commit()

    def retrieve_state(self, incident_id: str, loop_identifier: str) -> Optional[Dict[str, Any]]:
        """Rehydrates the loop state from durable storage."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT execution_status, context_data FROM loop_execution_state WHERE incident_id=? AND loop_identifier=?", 
                (incident_id, loop_identifier)
            )
            row = cursor.fetchone()
            if row:
                return {"status": row[0], "data": json.loads(row[1])}
            return None