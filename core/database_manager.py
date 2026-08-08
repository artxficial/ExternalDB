from multiprocessing import context
import os
import sqlite3
from typing import Any
from config import DB_DIR
from core.database_class import ACTION_MAP


class DatabaseManager:

    # ------------------------------------------------------------------
    # CONNECTION
    # ------------------------------------------------------------------

    def _get_connection(self, place_id: int) -> sqlite3.Connection:
        """Opens (or creates) the .db file for this place_id."""
        os.makedirs(DB_DIR, exist_ok=True)
        db_path = os.path.join(DB_DIR, f"datastore_{place_id}.db")

        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row      # Makes rows return as dicts instead of tuples
        conn.execute("PRAGMA journal_mode=WAL")  # Allows concurrent reads while writing
        return conn


    # ------------------------------------------------------------------
    # DATASTORE MANAGEMENT
    # ------------------------------------------------------------------

    def list_datastores(self, place_id: int) -> list:
        """Returns all datastore names that belong to this place_id."""
        conn = self._get_connection(place_id)
        try:
            prefix = f"ds_{place_id}_"
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?",
                (prefix + "%",)
            ).fetchall()

            # Strip the prefix so we return just the clean datastore name
            # e.g. "ds_123_PlayerData" -> "PlayerData"
            return [r["name"].replace(prefix, "") for r in rows]
        finally:
            conn.close()

    def remove_datastore(self, place_id: int, datastore_name: str) -> bool:
        """Permanently deletes a datastore table and its index."""
        table = f"ds_{place_id}_{datastore_name}"
        conn = self._get_connection(place_id)
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(f"DROP INDEX IF EXISTS idx_{table}_value")
            conn.commit()
            return True
        finally:
            conn.close()


    # ------------------------------------------------------------------
    # MAIN ROUTER
    # Called by externaldb.py — decides which execute method to use
    # based on the action's op_type ("single", "bulk", or "function")
    # ------------------------------------------------------------------

    def execute(self, action_spec: dict, context: dict, data: dict) -> Any:
        op_type = action_spec["op_type"]
        context = {**context, "ascending": data.get("ascending", False)}

        if op_type == "single":
            # Build the SQL params list, either via a custom lambda or
            # by just pulling the named args in order from the request data
            build_params = action_spec.get("build_params")
            params = build_params(data) if build_params else [data[arg] for arg in action_spec["args"]]
            return self.execute_single(context, params)

        elif op_type == "bulk":
            # The payload is always the first (and only) arg for bulk actions
            # e.g. BulkSetAsync sends a "dictionary", BulkRemoveAsync sends a "list"
            payload = data[action_spec["args"][0]]

            if action_spec.get("multi"):
                # "multi" bulk = fetch one row per key, return a dict of results
                return self.execute_bulk_read(context, payload, data)
            else:
                # Standard bulk = write many rows in one shot via executemany
                return self.execute_bulk(context, payload)

        elif op_type == "function":
            # Escape hatch for actions too complex for a SQL template
            return action_spec["handler"](self, context, data)

        raise ValueError(f"Unknown op_type: '{op_type}'")


    # ------------------------------------------------------------------
    # SINGLE QUERY  (one SQL statement, one result)
    # ------------------------------------------------------------------

    def execute_single(self, context: dict, params: list) -> Any:
        """
        Runs one SQL query against the table.
        - SELECT queries return a single row (dict) or a list of rows if multi=True
        - INSERT/UPDATE/DELETE queries commit and return True
        """
        place_id       = context["place_id"]
        datastore_name = context["datastore_name"]
        query_template = context["query_template"]
        is_multi       = context.get("multi", False)  # True = fetchall, False = fetchone

        table = f"ds_{place_id}_{datastore_name}"

        conn = self._get_connection(place_id)
        cursor = conn.cursor()

        try:
            # Ensure the table and index exist before querying
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table} (key INTEGER PRIMARY KEY, value INTEGER DEFAULT 0)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_value ON {table}(value DESC)")

            direction = "ASC" if context.get("ascending") else "DESC"
            query = query_template.format(table=table, direction=direction)
            cursor.execute(query, params)

            if query.strip().upper().startswith("SELECT"):
                if is_multi:
                    rows = cursor.fetchall()
                    return [dict(r) for r in rows] if rows else []
                else:
                    row = cursor.fetchone()
                    return dict(row) if row else None

            # Non-SELECT (write) queries just need a commit
            conn.commit()
            return True

        finally:
            conn.close()


    # ------------------------------------------------------------------
    # BULK READ  (loops a list of keys, returns {key: result} dict)
    # ------------------------------------------------------------------

    def execute_bulk_read(self, context: dict, payload: Any, data: dict = {}) -> Any:
        """
        Fetches rows per item in payload and returns a combined dict.
        e.g. [123, 456] -> {123: {"key":123,"value":50}, 456: {"key":456,"value":30}}
        """
        results = {}
        items = payload if isinstance(payload, list) else list(payload.items())
        build_params = context.get("build_params")

        # Safely determine if query returns multiple rows per item
        query_str = context.get("query_template", "") or ""
        is_near_rank = "NearRank" in query_str

        for item in items:
            if isinstance(item, dict):
                item_data = {**data, **item}
                key_identifier = item.get("key", item.get("rank", str(item)))
            else:
                item_data = {**data, "rank": item, "key": item}
                key_identifier = item

            params = build_params(item_data) if build_params else [item]

            # Force multi=is_near_rank for execute_single call
            single_context = {**context, "multi": is_near_rank}

            results[str(key_identifier)] = self.execute_single(single_context, params)

        return results

    # ------------------------------------------------------------------
    # BULK WRITE  (executemany — inserts/updates/deletes many rows at once)
    # ------------------------------------------------------------------

    def execute_bulk(self, context: dict, payload: Any) -> Any:
        """
        Writes many rows in a single database trip using executemany.
        - dict payload  {"key": value, ...}  -> [(key, value), ...]
        - list payload  ["key1", "key2", ...]  -> [("key1",), ("key2",), ...]
        """
        place_id       = context["place_id"]
        datastore_name = context["datastore_name"]
        query_template = context["query_template"]

        table = f"ds_{place_id}_{datastore_name}"

        conn = self._get_connection(place_id)
        cursor = conn.cursor()

        direction = "ASC" if context.get("ascending") else "DESC"
        query = query_template.format(table=table, direction=direction)

        try:
            if isinstance(payload, dict):
                params = list(payload.items())       # {A: 1, B: 2} -> [(A,1), (B,2)]
            elif isinstance(payload, list):
                params = [(key,) for key in payload] # [A, B] -> [(A,), (B,)]
            else:
                params = []

            cursor.executemany(query, params)
            conn.commit()
            return True
        finally:
            conn.close()


db_manager = DatabaseManager()