import sqlite3
import time
import os

from config import BASE_DIR

# -----------------------------
# Database Connection
# -----------------------------

def get_database_path(place_id: int) -> str:
    return os.path.join(BASE_DIR, f"datastore_{place_id}.db")


def DB_Connect(place_id):
    os.makedirs(BASE_DIR, exist_ok=True)
    conn = sqlite3.connect(get_database_path(place_id), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# -----------------------------
# Datastore Management
# -----------------------------

def DatastoreExists(conn, table_name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def ListDatastores(place_id) -> list:
    conn = DB_Connect(place_id)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row["name"] for row in cur.fetchall()]
    conn.close()
    return tables


def CreateOrderedDatastore(name: str, place_id):
    conn = DB_Connect(place_id)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {name} (
            key   INTEGER PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{name}_value
        ON {name}(value DESC)
    """)
    conn.commit()
    conn.close()
    print(f"Ordered datastore '{name}' initialized")


def RemoveDatastore(name: str, place_id):
    conn = DB_Connect(place_id)
    conn.execute(f"DROP TABLE IF EXISTS {name}")
    conn.execute(f"DROP TABLE IF EXISTS {name}_snapshot")
    conn.execute("DELETE FROM datastore_snapshots WHERE datastore_name = ?", (name,))
    conn.commit()
    conn.close()


# -----------------------------
# Snapshot Configuration
# -----------------------------

SNAPSHOT_INTERVAL = 300   # seconds between snapshots
LOCK_EXPIRY = 600        # seconds before stale lock is removed

# -----------------------------
# Datastore Class
# -----------------------------

class GetDatastore:
    def __init__(self, name: str, place_id):
        self.name = name
        self.table = name
        self.conn = DB_Connect(place_id)

        if not DatastoreExists(self.conn, name):
            print(f"Datastore '{name}' does not exist, creating...")
            CreateOrderedDatastore(name, place_id)

        self._check_and_update_snapshot()

    def Disconnect(self):
        self.conn.commit()
        self.conn.close()

    # -------------------------
    # Snapshots
    # -------------------------

    def _clear_snapshot(self):
        self.conn.execute(
            "DELETE FROM datastore_snapshots WHERE datastore_name = ?",
            (self.name,),
        )
        self.conn.execute(f"DROP TABLE IF EXISTS {self.table}_snapshot")
        self.conn.commit()

    def _ensure_snapshot_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS datastore_snapshots (
                datastore_name TEXT PRIMARY KEY,
                last_snapshot_time INTEGER NOT NULL
            )
        """)
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table}_snapshot (
                key INTEGER PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def _get_last_snapshot_time(self) -> int:
        cur = self.conn.execute(
            "SELECT last_snapshot_time FROM datastore_snapshots WHERE datastore_name = ?",
            (self.name,),
        )
        row = cur.fetchone()
        if not row:
            now = int(time.time())
            self.conn.execute(
                "INSERT INTO datastore_snapshots (datastore_name, last_snapshot_time) VALUES (?, ?)",
                (self.name, now),
            )
            self.conn.commit()
            return now
        return row["last_snapshot_time"]

    def _check_and_update_snapshot(self):
        # Don't snapshot snapshot tables
        if self.table.endswith("_snapshot") or self.table == "datastore_snapshots":
            return

        lock_file = os.path.join(BASE_DIR, f"{self.name}_snapshot.lock")

        # Check for stale lock
        if os.path.exists(lock_file):
            if (time.time() - os.path.getmtime(lock_file)) > LOCK_EXPIRY:
                try:
                    os.remove(lock_file)
                except:
                    pass
            else:
                return

        self._ensure_snapshot_table()
        now = int(time.time())
        last = self._get_last_snapshot_time()

        if (now - last) < SNAPSHOT_INTERVAL:
            return

        try:
            with open(lock_file, "w") as f:
                f.write(str(os.getpid()))

            self._take_snapshot()
        except Exception as e:
            print(f"Snapshot failed for '{self.name}': {e}")
        finally:
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except:
                    pass

    def _take_snapshot(self):
        now = int(time.time())

        # Verify table has standard schema
        cur = self.conn.execute(f"PRAGMA table_info({self.table})")
        columns = {row["name"] for row in cur.fetchall()}

        if "key" not in columns or "value" not in columns:
            print(f"Skipping snapshot for '{self.name}' - non-standard schema")
            return

        try:
            self.conn.execute(f"""
                INSERT OR REPLACE INTO {self.table}_snapshot (key, value)
                SELECT key, value FROM {self.table}
            """)
            self.conn.execute(
                "UPDATE datastore_snapshots SET last_snapshot_time = ? WHERE datastore_name = ?",
                (now, self.name),
            )
            self.conn.commit()

            cur = self.conn.execute(f"SELECT COUNT(*) as count FROM {self.table}_snapshot")
            count = cur.fetchone()["count"]
            print(f"Snapshot taken for '{self.name}': {count} records")
        except Exception as e:
            self.conn.rollback()
            raise

    # -------------------------
    # Read - Single
    # -------------------------

    def GetAsync(self, key: int):
        cur = self.conn.execute(
            f"SELECT value FROM {self.table} WHERE key = ?", (key,)
        )
        row = cur.fetchone()
        return row["value"] if row else None

    def GetRankAsync(self, key: int) -> dict:
        cur = self.conn.execute(f"SELECT COUNT(*) AS total_keys FROM {self.table}")
        total_keys = cur.fetchone()["total_keys"]

        cur = self.conn.execute(f"""
            SELECT rank, percentile, value
            FROM (
                SELECT key, value,
                    RANK() OVER (ORDER BY value DESC) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value DESC) AS percentile
                FROM {self.table}
            )
            WHERE key = ?
        """, (key,))

        row = cur.fetchone()
        if row is None:
            return {"rank": -1, "percentile": -1.0, "total_keys": total_keys, "value": None}

        return {**dict(row), "total_keys": total_keys}

    def GetValueAtPercentile(self, target: float) -> dict:
        cur = self.conn.execute(f"""
            SELECT value, rank, percentile
            FROM (
                SELECT value,
                    RANK() OVER (ORDER BY value DESC) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value DESC) AS percentile
                FROM {self.table}
            )
            WHERE percentile <= ?
            ORDER BY percentile DESC
            LIMIT 1
        """, (target,))

        row = cur.fetchone()
        if row is None:
            return {"rank": -1, "percentile": -1.0, "value": None}
        return dict(row)

    def GetKeysNearRankAsync(self, rank: int, spread: int) -> list[dict]:
        cur = self.conn.execute(f"""
            SELECT key, value, rank, percentile, total_keys
            FROM (
                SELECT key, value,
                    ROW_NUMBER() OVER (ORDER BY value DESC) AS row_index,
                    RANK() OVER (ORDER BY value DESC) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value DESC) AS percentile,
                    COUNT(*) OVER () AS total_keys
                FROM {self.table}
            )
            WHERE row_index >= ? AND row_index < ?
            ORDER BY value DESC
        """, (rank - spread, rank + spread))

        cols = [col[0] for col in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def ListOrderedKeysAsync(self, limit: int, start_index: int) -> list:
        # Check schema
        cur = self.conn.execute(f"PRAGMA table_info({self.table})")
        columns_info = cur.fetchall()
        columns = {row["name"] for row in columns_info}

        # Non-standard schema fallback
        if "key" not in columns or "value" not in columns:
            col_str = ", ".join(row["name"] for row in columns_info)

            if start_index is None:
                cur = self.conn.execute(
                    f"SELECT {col_str} FROM {self.table} LIMIT ?", (limit,)
                )
            else:
                cur = self.conn.execute(
                    f"SELECT {col_str} FROM {self.table} LIMIT ? OFFSET ?",
                    (limit, max(start_index - 1, 0)),
                )
            return [dict(row) for row in cur.fetchall()]

        # Standard schema
        if start_index is None:
            cur = self.conn.execute(f"""
                SELECT key, value,
                    RANK() OVER (ORDER BY value DESC) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value DESC) AS percentile,
                    COUNT(*) OVER () AS total_keys
                FROM {self.table}
                ORDER BY value DESC
                LIMIT ?
            """, (limit,))
        else:
            cur = self.conn.execute(f"""
                SELECT key, value, rank, percentile, total_keys
                FROM (
                    SELECT key, value,
                        ROW_NUMBER() OVER (ORDER BY value DESC) AS row_index,
                        RANK() OVER (ORDER BY value DESC) AS rank,
                        PERCENT_RANK() OVER (ORDER BY value DESC) AS percentile,
                        COUNT(*) OVER () AS total_keys
                    FROM {self.table}
                )
                WHERE row_index >= ? AND row_index < ? + ?
                ORDER BY value DESC
            """, (start_index, start_index, limit))

        return [dict(row) for row in cur.fetchall()]

    def CompareToSnapshotAsync(self, key: int) -> dict:
        cur = self.conn.execute(f"""
            SELECT rank, percentile, value
            FROM (
                SELECT key, value,
                    RANK() OVER (ORDER BY value DESC) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value DESC) AS percentile
                FROM {self.table}
            )
            WHERE key = ?
        """, (key,))
        current = cur.fetchone()

        if not current:
            return {"value_delta": None, "rank_delta": None, "percentile_delta": None}

        cur = self.conn.execute(f"""
            SELECT rank, percentile, value
            FROM (
                SELECT key, value,
                    RANK() OVER (ORDER BY value DESC) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value DESC) AS percentile
                FROM {self.table}_snapshot
            )
            WHERE key = ?
        """, (key,))
        snapshot = cur.fetchone()

        if not snapshot:
            return {**dict(current), "value_delta": None, "rank_delta": None, "percentile_delta": None}

        return {
            **dict(current),
            "value_delta": current["value"] - snapshot["value"],
            "rank_delta": snapshot["rank"] - current["rank"],
            "percentile_delta": snapshot["percentile"] - current["percentile"],
        }

    def GetLastSnapshotTime(self) -> int:
        return self._get_last_snapshot_time()

    def GetSumOfValues(self):
        cur = self.conn.execute(f"SELECT SUM(value) AS sum FROM {self.table}")
        row = cur.fetchone()
        return row["sum"] if row else 0

    # -------------------------
    # Read - Bulk
    # -------------------------

    def BulkGetAsync(self, keys: list) -> dict:
        return {key: self.GetAsync(key) for key in keys}

    def BulkGetRankAsync(self, keys: list) -> dict:
        return {key: self.GetRankAsync(key) for key in keys}

    def BulkGetValueAtPercentile(self, values: list) -> dict:
        return {v: self.GetValueAtPercentile(v) for v in values}

    def BulkGetKeysNearRankAsync(self, ranks: list, spread: int) -> dict:
        return {rank: self.GetKeysNearRankAsync(rank, spread) for rank in ranks}

    def BulkCompareToSnapshotAsync(self, keys: list) -> dict:
        return {key: self.CompareToSnapshotAsync(key) for key in keys}

    # -------------------------
    # Write - Single
    # -------------------------

    def SetAsync(self, key: int, value) -> dict:
        self.conn.execute(f"""
            INSERT OR REPLACE INTO {self.table} (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        self.conn.commit()
        return self.GetRankAsync(key)

    def IncrementAsync(self, key: int, delta: int = 1) -> int:
        self.conn.execute(f"""
            INSERT INTO {self.table} (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = value + excluded.value
        """, (key, delta))
        self.conn.commit()

        cur = self.conn.execute(
            f"SELECT value FROM {self.table} WHERE key = ?", (key,)
        )
        return cur.fetchone()["value"]

    def RemoveAsync(self, key: int):
        self.conn.execute(f"DELETE FROM {self.table} WHERE key = ?", (key,))
        self.conn.commit()

    # -------------------------
    # Write - Bulk
    # -------------------------

    def BulkSetAsync(self, keys_values: dict) -> dict:
        for key, value in keys_values.items():
            self.SetAsync(key, value)
        return self.BulkGetRankAsync(list(keys_values.keys()))

    def BulkIncrementAsync(self, keys_values: dict):
        for key, value in keys_values.items():
            self.IncrementAsync(key, value)

    def BulkRemoveAsync(self, keys: list):
        for key in keys:
            self.RemoveAsync(key)