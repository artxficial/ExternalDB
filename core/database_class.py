import sqlite3  # or sqlite3 / psycopg2 depending on your backend
from typing import Dict, List, Tuple, Any, Optional, Union

ACTION_MAP = {
     # ----------------------------------------------------------------------------
    # FUNCTIONS
    # ----------------------------------------------------------------------------
    "ListDatastores": {
        "args": [],
        "op_type": "function",
        "requires": ["place_id"],  # no datastore_name
        "handler": lambda db, context, data: db.list_datastores(context["place_id"])
    },

    "RemoveDatastore": {
        "args": [],
        "requires": ["place_id", "key"],
        "op_type": "function",
        "handler": lambda db, context, data: db.remove_datastore(context["place_id"], data["key"])
    },

    # ----------------------------------------------------------------------------
    # SINGLE KEY OPERATIONS: (operation_type="single")
    # ----------------------------------------------------------------------------
    "GetAsync": {
        "args": ["key"],
        "op_type": "single",
        "query": "SELECT value FROM {table} WHERE key = ?"
    },

    "GetRankDataAsync": {
        "args": ["key"],
        "op_type": "single",
        "query": """
            SELECT key, value, rank, percentile, total_keys FROM (
                SELECT key, value,
                    RANK() OVER (ORDER BY value {direction}) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value {direction}) AS percentile,
                    COUNT(*) OVER () AS total_keys
                FROM {table}
            ) WHERE key = ?
        """
    },

    "BulkGetRankDataAsync": {
        "args": ["list"],
        "op_type": "bulk",
        "multi": True,
        "query": """
            SELECT key, value, rank, percentile, total_keys FROM (
                SELECT key, value,
                    RANK() OVER (ORDER BY value {direction}) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value {direction}) AS percentile,
                    COUNT(*) OVER () AS total_keys
                FROM {table}
            ) WHERE key = ?
        """
    },

    "RemoveAsync": {
        "args": ["key"],
        "op_type": "single",
        "query": "DELETE FROM {table} WHERE key = ?"
    },
    "SetAsync": {
        "args": ["key", "value"],
        "op_type": "single",
        "query": "INSERT INTO {table} (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    },
    "IncrementAsync": {
        "args": ["key", "value"],
        "op_type": "single",
        "query": "INSERT INTO {table} (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + excluded.value"
    },

    # ----------------------------------------------------------------------------
    # BULK OPERATIONS: (op_type="bulk" uses executemany)
    # ----------------------------------------------------------------------------
    "BulkSetAsync": {
        "args": ["dictionary"],
        "op_type": "bulk",
        "query": "INSERT INTO {table} (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    },
    "BulkIncrementAsync": {
        "args": ["dictionary"],
        "op_type": "bulk",
        "query": "INSERT INTO {table} (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = value + excluded.value"
    },

    "BulkRemoveAsync": {
        "args": ["list"],
        "op_type": "bulk",
        "query": "DELETE FROM {table} WHERE key = ?"
    },

    # ----------------------------------------------------------------------------
    # MULTI OPS: (op_type="bulk" uses executemany)
    # ----------------------------------------------------------------------------

    "GetValueAtPercentile": {
        "args": ["percentile"],
        "op_type": "single",
        "multi": False,
        "query": """
            SELECT value, rank, percentile FROM (
                SELECT value,
                    RANK() OVER (ORDER BY value {direction}) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value {direction}) AS percentile
                FROM {table}
            ) WHERE percentile <= ? ORDER BY percentile ASC LIMIT 1
        """
    },
 
    "GetKeysNearRankAsync": {
        "args": ["rank", "spread"],
        "op_type": "single",
        "multi": True,
        "defaults": {},
        "build_params": lambda data: [data["rank"] - data["spread"], data["rank"] + data["spread"]],
        "query": """
            SELECT key, value, rank, percentile, total_keys FROM (
                SELECT key, value,
                    ROW_NUMBER() OVER (ORDER BY value {direction}) AS row_index,
                    RANK() OVER (ORDER BY value {direction}) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value {direction}) AS percentile,
                    COUNT(*) OVER () AS total_keys
                FROM {table}
            ) WHERE row_index >= ? AND row_index < ?
            ORDER BY value {direction}
        """
    },
 
    "ListOrderedKeysAsync": {
        "args": ["start_index", "limit"],
        "op_type": "single",
        "multi": True,
        "defaults": {"start_index": 1},
        "build_params": lambda data: [data["start_index"], data["start_index"], data["limit"]],
        "query": """
            SELECT key, value, rank, percentile, total_keys FROM (
                SELECT key, value,
                    ROW_NUMBER() OVER (ORDER BY value {direction}) AS row_index,
                    RANK() OVER (ORDER BY value {direction}) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value {direction}) AS percentile,
                    COUNT(*) OVER () AS total_keys
                FROM {table}
            ) WHERE row_index >= ? AND row_index < ? + ?
            ORDER BY value {direction}
        """
    },

    "BulkGetAsync": {
    "args": ["list"],
    "op_type": "bulk",
    "multi": True,
    "query": "SELECT key, value FROM {table} WHERE key = ?"
    },


    "BulkGetValueAtPercentile": {
        "args": ["list"],
        "op_type": "bulk",
        "multi": True,
        "query": """
            SELECT value, rank, percentile FROM (
                SELECT value,
                    RANK() OVER (ORDER BY value {direction}) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value {direction}) AS percentile
                FROM {table}
            ) WHERE percentile >= ? ORDER BY percentile ASC LIMIT 1
        """
    },

    "BulkGetKeysNearRankAsync": {
        "args": ["list"],
        "op_type": "bulk",
        "multi": True,
        "defaults": {"spread": 0},
        "build_params": lambda data: [
            max(1, (data["rank"] if isinstance(data, dict) else data) - data.get("spread", 0)), 
            (data["rank"] if isinstance(data, dict) else data) + data.get("spread", 0)
        ],
        "query": """
            SELECT key, value, rank, percentile, total_keys FROM (
                SELECT key, value,
                    ROW_NUMBER() OVER (ORDER BY value {direction}) AS row_index,
                    RANK() OVER (ORDER BY value {direction}) AS rank,
                    PERCENT_RANK() OVER (ORDER BY value {direction}) AS percentile,
                    COUNT(*) OVER () AS total_keys
                FROM {table}
            ) WHERE row_index >= ? AND row_index <= ?
            ORDER BY value {direction}
        """
    }
}

DEFAULT_CONFIGURATIONS = {
    "enable_snapshots": False,
    "descending_order": True,
    "max_page_size": 50,
    "spread_default": 2,
}

class GetDatastore:
    def __init__(self, name: str, place_id: int, config: Optional[dict] = None):
        self.name = name
        self.table = name
        self.place_id = place_id
        
        # Merge configurations
        self.config = DEFAULT_CONFIGURATIONS.copy()
        if config:
            self.config.update(config)
            
        # Initialize your DB connection pool or cursor here
        # self.conn = DB_Connect(place_id)

        if self.config["enable_snapshots"]:
            self._check_and_update_snapshot()

    def _check_and_update_snapshot(self):
        # Your snapshot startup logic
        pass

    def _dispatch_request(self, action_name: str, *args, **kwargs) -> Any:
        """
        The central execution brain. All dynamic method hooks resolve here.
        """
        param_names = ACTION_MAP[action_name]["args"]
        payload = {}
        
        # 1. Error Handling: Prevent passing too many positional arguments
        if len(args) > len(param_names):
            raise TypeError(f"{action_name}() takes {len(param_names)} positional arguments but {len(args)} were given")

        # 2. Map positional arguments to their keys
        for i, val in enumerate(args):
            payload[param_names[i]] = val
            
        # 3. Merge explicit keyword arguments
        payload.update(kwargs)

        # 4. Inject fallback defaults if parameters are missing
        if "spread" in param_names and "spread" not in payload:
            payload["spread"] = self.config["spread_default"]
        if action_name == "ListOrderedKeysAsync":
            if "limit" not in payload or payload["limit"] is None:
                payload["limit"] = self.config["max_page_size"]

        # 5. Route payload directly to your database processing logic
        return self._execute_database_query(action_name, payload)

    def _execute_database_query(self, action: str, payload: dict) -> Any:
        """
        This is where your actual SQL strings or external requests fire.
        """
        print(f"[DB LOG] Table: {self.table} | Executing: {action} | Params: {payload}")
        # Your SQL matching table logic here...
        pass


    # ----------------------------------------------------------------------------
    # TYPE HINTING STUBS (Crucial for IDE Autocomplete & Linting)
    # ----------------------------------------------------------------------------
    
    def GetAsync(self, key: int) -> Any: ...
    def GetRankDataAsync(self, key: int) -> dict: ...
    def RemoveAsync(self, key: int) -> None: ...
    def SetAsync(self, key: int, value: Union[int, float]) -> dict: ...
    def IncrementAsync(self, key: int, value: Union[int, float]) -> Union[int, float]: ...
    def GetValueAtPercentile(self, percentile: float) -> Union[int, float]: ...
    def GetKeysNearRankAsync(self, rank: int, spread: Optional[int] = None) -> List: ...
    def ListOrderedKeysAsync(self, limit: Optional[int] = None, start_index: Optional[int] = None) -> List: ...
    def CompareToSnapshotAsync(self, key: int) -> dict: ...
    def GetLastSnapshotTime(self) -> int: ...
    def GetSumOfValues(self) -> Union[int, float]: ...
    def BulkSetAsync(self, dictionary: dict) -> dict: ...
    def BulkIncrementAsync(self, dictionary: dict) -> None: ...
    def BulkGetAsync(self, list: list) -> dict: ...
    def BulkRemoveAsync(self, list: list) -> None: ...
    def BulkGetRankDataAsync(self, list: list) -> dict: ...
    def BulkGetValueAtPercentile(self, list: list) -> dict: ...
    def BulkCompareToSnapshotAsync(self, list: list) -> dict: ...
    def BulkGetKeysNearRankAsync(self, list: list, spread: Optional[int] = None) -> dict: ...

# ----------------------------------------------------------------------------
# METAPROGRAMMING COMPILER (Runs exactly once when the file is loaded)
# ----------------------------------------------------------------------------
def _create_dynamic_method(action_name: str):
    def method(self, *args, **kwargs):
        return self._dispatch_request(action_name, *args, **kwargs)
    method.__name__ = action_name
    return method

# Intercept and attach the real routing functions onto the class blueprint
for action in ACTION_MAP.keys():
    setattr(GetDatastore, action, _create_dynamic_method(action))