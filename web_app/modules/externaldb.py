import os
import sqlite3
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, render_template
from config import DB_DIR, TOKEN, ROOT
from core.auth import check_token, require_token


import logging 
from collections import deque

logger = logging.getLogger(__name__)


externaldb_bp = Blueprint("externaldb", __name__)

# =========================================================
# PATHS
# =========================================================

LOG_DIR = os.path.join(ROOT, "logs")
DB_DIR = os.path.join(ROOT, "databases")

# =========================================================
# HELPERS
# =========================================================

def db_log_path(db_id):
    return os.path.join(LOG_DIR, f"{db_id}.log")


def write_db_log(db_id, line):
    with open(db_log_path(db_id), "a", encoding="utf-8") as f:
        f.write(line + "\n")

def get_db_path(db_id):
    return os.path.join(DB_DIR, f"{db_id}.db")

# =========================================================
# DASHBOARD INFO
# =========================================================

def get_storage_used():
    if not os.path.exists(DB_DIR):
        return "0.00 MB / 10 GB"
    total = sum(
        os.path.getsize(os.path.join(DB_DIR, f))
        for f in os.listdir(DB_DIR)
        if f.endswith(".db")
    )
    gb = total / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.2f} GB / 10 GB"
    mb = total / (1024 * 1024)
    return f"{mb:.2f} MB / 10 GB"


EST = timezone(timedelta(hours=-4))
def get_last_request():
    log_path = os.path.join(LOG_DIR, "access.log")
    if not os.path.exists(log_path):
        return "Never"

    with open(log_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        block_size = 8192
        buffer = b""
        pos = file_size

        while pos > 0:
            read_size = min(block_size, pos)
            pos -= read_size
            f.seek(pos)
            buffer = f.read(read_size) + buffer

            lines = buffer.split(b"\n")
            # keep scanning backwards through lines we have so far
            for raw_line in reversed(lines[1:] if pos > 0 else lines):
                line = raw_line.decode("utf-8", errors="ignore")
                if "/externaldb/" not in line:
                    continue
                try:
                    ts_str = line[1:15]
                    ts = datetime.strptime(ts_str, "%m-%d %H:%M:%S").replace(
                        year=datetime.now().year, tzinfo=timezone.utc
                    )
                    return ts.astimezone(EST).strftime("[%m/%d] %I:%M %p")
                except ValueError:
                    continue

            buffer = lines[0]  # leftover partial line, prepend on next loop

    return "Never"

def get_requests_per_minute():
    log_path = os.path.join(LOG_DIR, "access.log")
    if not os.path.exists(log_path):
        return 0

    cutoff = datetime.now() - timedelta(minutes=1)
    count = 0

    with open(log_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        block_size = 8192
        buffer = b""
        pos = file_size
        stop = False

        while pos > 0 and not stop:
            read_size = min(block_size, pos)
            pos -= read_size
            f.seek(pos)
            buffer = f.read(read_size) + buffer

            lines = buffer.split(b"\n")
            buffer = lines[0]  # partial line, carried to next chunk
            complete_lines = lines[1:] if pos > 0 else lines

            for raw_line in reversed(complete_lines):
                line = raw_line.decode("utf-8", errors="ignore")
                if "/externaldb/api" not in line:
                    continue
                try:
                    ts_str = line[1:15]
                    ts = datetime.strptime(ts_str, "%m-%d %H:%M:%S").replace(year=datetime.now().year)
                except ValueError:
                    continue

                if ts >= cutoff:
                    count += 1
                else:
                    stop = True
                    break

    return count
# =========================================================
# DASHBOARD
# =========================================================

@externaldb_bp.route("/", methods=["GET"])
def dashboard():
    db_count = len([f for f in os.listdir(DB_DIR) if f.endswith(".db")])
    req_per_minute = get_requests_per_minute()
    storage_used = get_storage_used()
    last_request = get_last_request()
    return render_template("ExternalDB.html", db_count=db_count, req_per_minute=req_per_minute, storage_used=storage_used, last_request=last_request)

# =========================================================
# EXECUTE API (ROBLOX)
# =========================================================

@externaldb_bp.route("/api/execute", methods=["GET"])
def status():
    return jsonify({"status": "Use post method to execute actions"}), 200 

from core.database_manager import db_manager
from core.database_class import ACTION_MAP

@externaldb_bp.route("/api/execute", methods=["POST"])
@require_token
def execute():
    data = request.get_json() or {}
    action = data.get("action")

    if not action:
        return jsonify({"error": "missing action"}), 400
    if action not in ACTION_MAP:
        return jsonify({"error": f"unknown action '{action}'"}), 400

    action_spec = ACTION_MAP[action]

    DEFAULT_REQUIRES = ["place_id", "datastore_name"]
    required_fields = action_spec.get("requires", DEFAULT_REQUIRES)
    missing_fields = [f for f in required_fields if not data.get(f)]
    if missing_fields:
        return jsonify({"error": f"missing fields: {missing_fields}"}), 400

    for arg, default in action_spec.get("defaults", {}).items():
        data.setdefault(arg, default)

    missing_args = [arg for arg in action_spec["args"] if arg not in data]
    if missing_args:
        return jsonify({"error": f"missing args: {missing_args}"}), 400

    db_id = data.get("datastore_name")
    place_id = data.get("place_id")

    context = {
        "place_id": place_id,
        "datastore_name": db_id,
        "query_template": action_spec.get("query"),
        "multi": action_spec.get("multi", False),
        "build_params": action_spec.get("build_params"),
    }

    try:
        result = db_manager.execute(action_spec, context, data)
        write_db_log(db_id, f"[{datetime.utcnow()}] ACTION={action}")
        return jsonify({"status": "success", "db": db_id, "action": action, "result": result})

    except Exception as e:
        write_db_log(db_id, f"[ERROR] {str(e)}")
        return jsonify({"error": str(e)}), 500
    
# =========================================================
# STREAM RAW LOGS
# =========================================================

# Define your log map in a secure dictionary
LOG_REGISTRY = {
    "activity": "logs/app.log",
    "access": "logs/access.log"
}


# =========================================================
# STREAM RAW LOGS
# =========================================================


@externaldb_bp.before_request
def log_incoming_payloads():
    # Only try to log if it's a POST/PUT request and contains JSON data
    if request.method in ["POST", "PUT"] and request.is_json:
        # Don't log the log-streaming endpoint itself (otherwise you'll spam your logs!)
        if "api/logs/stream" in request.path:
            return

        try:
            # .get_json() extracts the payload dictionary safely
            payload = request.get_json(silent=True)
            if payload:
                # This print statement will be caught by your LogStreamSplitter!
                logger.info(f"[PAYLOAD LOGGER] {request.method} {request.path} -> Data: {payload}")
        except Exception as e:
            logger.error(f"[PAYLOAD LOGGER ERROR] Failed to parse payload: {e}")


def tail(file_path, n=40, chunk_size=8192):
    """Read the last n lines of a file efficiently, without scanning the whole file."""
    with open(file_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        blocks = []
        lines_found = 0
        pos = file_size

        while pos > 0 and lines_found <= n:
            read_size = min(chunk_size, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)
            blocks.append(chunk)
            lines_found += chunk.count(b"\n")

        data = b"".join(reversed(blocks))
        lines = data.splitlines()
        last_n = lines[-n:] if len(lines) >= n else lines
        return b"\n".join(last_n).decode("utf-8", errors="replace") + "\n"


@externaldb_bp.route("/api/logs/stream", methods=["POST"])
@require_token
def stream_logs():
    data = request.get_json() or {}
    log_type = data.get("type", "activity")

    if log_type not in LOG_REGISTRY:
        return f"[SYSTEM ERROR] Invalid or unauthorized log stream type: '{log_type}'", 400

    file_path = LOG_REGISTRY[log_type]

    if os.path.exists(file_path):
        try:
            return tail(file_path, n=40)
        except Exception as e:
            return f"[SYSTEM ERROR] Failed to read log file: {str(e)}", 500

    return f"[SYSTEM] Live stream channel '{log_type}' initialized. Waiting for entries..."


@externaldb_bp.route("/api/logs/clear", methods=["POST"])
@require_token
def clear_logs():
    try:
        for file_path in LOG_REGISTRY.values():
            if os.path.exists(file_path):
                open(file_path, "w").close()
        
        timestamp = datetime.now(EST).strftime("[%m/%d] %I:%M %p")
        for file_path in LOG_REGISTRY.values():
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"[SYSTEM] Logs cleared at {timestamp}\n")

        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500