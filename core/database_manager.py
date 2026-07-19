import os
import sqlite3
import time
from typing import Any, Dict, List
from config import DB_DIR
from core.database_class import ACTION_MAP

class DatabaseManager:
    
    def _get_connection(self, place_id: int) -> sqlite3.Connection:
        os.makedirs(DB_DIR, exist_ok=True)
        db_path = os.path.join(DB_DIR, f"datastore_{place_id}.db")
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def list_datastores(self, place_id: int) -> list:
        conn = self._get_connection(place_id)
        try:
            prefix = f"ds_{place_id}_"
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?",
                (prefix + "%",)
            ).fetchall()
            return [r["name"].replace(prefix, "") for r in rows]
        finally:
            conn.close()

    def remove_datastore(self, place_id: int, datastore_name: str) -> bool:
        table = f"ds_{place_id}_{datastore_name}"
        conn = self._get_connection(place_id)
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(f"DROP INDEX IF EXISTS idx_{table}_value")
            conn.commit()
            return True
        finally:
            conn.close()

    def execute(self, action_spec: dict, context: dict, data: dict) -> Any:
        op_type = action_spec["op_type"]

        if op_type == "single":
            build_params = action_spec.get("build_params")
            params = build_params(data) if build_params else [data[arg] for arg in action_spec["args"]]
            return self.execute_single(context, params)
        elif op_type == "bulk":
            payload = data[action_spec["args"][0]]
            if action_spec.get("multi"):
                return self.execute_bulk_read(context, payload, data)
            return self.execute_bulk(context, payload)

        elif op_type == "function":
            return action_spec["handler"](self, context, data)

        raise ValueError(f"unknown op_type: {op_type}")

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

    def execute_bulk_read(self, context: dict, payload: Any, data: dict = {}) -> Any:
        results = {}
        keys = list(payload) if isinstance(payload, list) else list(payload.keys())
        for key in keys:
            build_params = context.get("build_params")
            if build_params:
                params = build_params({**data, "rank": key})
            else:
                params = [key]
            results[key] = self.execute_single(context, params)
        return results

    def execute_bulk(self, context: dict, payload: Any) -> Any:
        place_id = context["place_id"]
        table = f"ds_{place_id}_{context['datastore_name']}"
        query_template = context["query_template"]

        conn = self._get_connection(place_id)
        cursor = conn.cursor()
        query = query_template.format(table=table)

        try:
            if isinstance(payload, dict):
                params = list(payload.items())
            elif isinstance(payload, list):
                params = [(key,) for key in payload]
            else:
                params = []

            cursor.executemany(query, params)
            conn.commit()
            return True
        finally:
            conn.close()

db_manager = DatabaseManager()