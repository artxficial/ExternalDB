import os
import sqlite3
import time
from typing import Any, Dict, List
from config import DB_DIR
from core.database_class import ACTION_MAP

class DatabaseManager:
    """
    Unified manager that executes operations entirely based on the ACTION_MAP
    and handles complex query formatting or programmatic loops automatically.
    """
    
    def _get_connection(self, place_id: int) -> sqlite3.Connection:
        os.makedirs(DB_DIR, exist_ok=True)
        db_path = os.path.join(DB_DIR, f"datastore_{place_id}.db")
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def execute_single(self, context: dict, params: list) -> Any:
        place_id = context["place_id"]
        table = f"ds_{place_id}_{context['datastore_name']}"
        query_template = context["query_template"]
        is_multi = context.get("multi", False)
 
        conn = self._get_connection(place_id)
        cursor = conn.cursor()
 
        try:
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table} (key INTEGER PRIMARY KEY, value INTEGER DEFAULT 0)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_value ON {table}(value DESC)")
 
            query = query_template.format(table=table)
            cursor.execute(query, params)
 
            if query.strip().upper().startswith("SELECT"):
                if is_multi:
                    rows = cursor.fetchall()
                    return [dict(r) for r in rows] if rows else []
 
                row = cursor.fetchone()
                return dict(row) if row else None
 
            conn.commit()
            return True
 
        finally:
            conn.close()
 

    def execute_bulk(self, context: dict, payload: Any) -> Any:
        """
        Dynamically unrolls bulk requests into executemany parameters, 
        eliminating the manual write-loops in your functions file.
        """
        place_id = context["place_id"]
        table = f"ds_{place_id}_{context['datastore_name']}"
        query_template = context["query_template"]
        
        conn = self._get_connection(place_id)
        cursor = conn.cursor()
        query = query_template.format(table=table)
        
        try:
            if isinstance(payload, dict):
                # Unrolls {"User_1": 100} -> [("User_1", 100)]
                params = list(payload.items())
            elif isinstance(payload, list):
                # Unrolls ["User_1", "User_2"] -> [("User_1",), ("User_2",)]
                params = [(key,) for key in payload]
            else:
                params = []
                
            cursor.executemany(query, params)
            conn.commit()
            return True
        finally:
            conn.close()

db_manager = DatabaseManager()