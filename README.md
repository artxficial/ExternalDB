# Uma Derby Legends - External Database API

A lightweight SQLite-based datastore API designed for Roblox games. It provides ordered datastores with ranking, percentile calculations, snapshots for delta tracking, and bulk operations — all accessible via HTTP webhook.

## Features

- **Ordered Datastores** with automatic indexing for fast leaderboard queries
- **Rank and Percentile** calculations using SQL window functions
- **Snapshot System** that periodically copies datastore state for delta comparisons (value gained, rank change, percentile shift)
- **Bulk Operations** for batching reads and writes in a single request
- **Multi-Place Support** with separate database files per Roblox Place ID
- **WAL Mode** enabled for concurrent read/write performance

## How It Works

Roblox sends HTTP POST requests to a Flask webhook. The webhook routes each request to the appropriate datastore action and returns JSON results. Each Roblox Place ID gets its own SQLite database file.

```
Roblox Game → HTTP POST → Flask Webhook → SQLite Database
```

## API Reference

### Datastore Management

| Action | Description |
|---|---|
| `ListDatastores` | List all tables in a place's database |
| `CreateOrderedDatastore` | Create a new ordered datastore with value-descending index |
| `RemoveDatastore` | Drop a datastore table |

### Read Operations

| Action | Parameters | Description |
|---|---|---|
| `GetAsync` | `key` | Get value for a single key |
| `BulkGetAsync` | `keys[]` | Get values for multiple keys |
| `GetRankAsync` | `key` | Get rank, percentile, and value for a key |
| `BulkGetRankAsync` | `keys[]` | Get rank data for multiple keys |
| `ListOrderedKeysAsync` | `limit`, `start_index` | Get top entries with rank and percentile |
| `GetKeysNearRankAsync` | `rank`, `spread` | Get entries surrounding a specific rank |
| `GetValueAtPercentile` | `target` | Get the value at a given percentile (0.0 - 1.0) |
| `BulkGetValueAtPercentile` | `values[]` | Get values at multiple percentiles |
| `CompareToSnapshotAsync` | `key` | Get deltas (value, rank, percentile) since last snapshot |
| `BulkCompareToSnapshotAsync` | `keys[]` | Compare multiple keys to their snapshots |
| `GetLastSnapshotTime` | — | Get Unix timestamp of last snapshot |
| `GetSumOfValues` | — | Get sum of all values in the datastore |

### Write Operations

| Action | Parameters | Description |
|---|---|---|
| `SetAsync` | `key`, `value` | Set value for a key (returns updated rank) |
| `BulkSetAsync` | `keys_values{}` | Set multiple key-value pairs (returns ranks) |
| `IncrementAsync` | `key`, `delta` | Increment a key's value by delta (default 1) |
| `BulkIncrementAsync` | `keys_values{}` | Increment multiple keys |
| `RemoveAsync` | `key` | Delete a key |
| `BulkRemoveAsync` | `keys[]` | Delete multiple keys |

## Snapshot System

Snapshots automatically copy the current datastore state every 5 minutes. This enables tracking changes over time.

- Snapshots are stored in a `{table}_snapshot` table
- Metadata is tracked in `datastore_snapshots` with timestamps
- File-based locking prevents concurrent snapshot writes
- Snapshot tables and metadata tables are excluded from being snapshotted

Use `CompareToSnapshotAsync` to get deltas:

```python
# Returns:
{
    "value": 1500,
    "rank": 12,
    "percentile": 0.95,
    "value_delta": 200,    # gained 200 since snapshot
    "rank_delta": 3,       # climbed 3 ranks
    "percentile_delta": 0.02
}
```

## Database Structure

Each Place ID gets a separate SQLite file at `databases/datastore_{place_id}.db`.

Each ordered datastore table:

```sql
CREATE TABLE {name} (
    key   INTEGER PRIMARY KEY,
    value INTEGER DEFAULT 0
);
CREATE INDEX idx_{name}_value ON {name}(value DESC);
```

## Configuration

Set your authentication token in the Flask app to validate incoming requests from Roblox:

```python
TOKEN = "your-secret-token-here"
```

On the Roblox side, set the matching token and server URL:

```lua
local URL = "https://yourdomain.com"
local token = "your-secret-token-here"
```
- Snapshots trigger every 300 seconds (5 minutes)

## Setup

```bash
pip install flask
python app.py
```

Requires Python 3.8+ and Flask. SQLite is included in Python's standard library.
