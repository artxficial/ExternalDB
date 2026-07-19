import os
import sqlite3
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, render_template
from config import DB_DIR, TOKEN, ROOT

import logging 
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


EST = timezone(timedelta(hours=-5))
def get_last_request():
    log_path = os.path.join(LOG_DIR, "access.log")
    if not os.path.exists(log_path):
        return "Never"

    last_ts = None

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if "/externaldb/" not in line:
                continue
            try:
                ts_str = line[1:15]
                ts = datetime.strptime(ts_str, "%m-%d %H:%M:%S").replace(year=datetime.now().year, tzinfo=timezone.utc)
                last_ts = ts
            except ValueError:
                continue

    return last_ts.astimezone(EST).strftime("[%m/%d] %I:%M %p") if last_ts else "Never"

def get_requests_per_minute():
    log_path = os.path.join(LOG_DIR, "access.log")
    if not os.path.exists(log_path):
        return 0

    cutoff = datetime.now() - timedelta(minutes=1)
    count = 0

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if "/externaldb/api" not in line:
                continue
            try:
                ts_str = line[1:15]  # grabs "07-19 21:51:00"
                ts = datetime.strptime(ts_str, "%m-%d %H:%M:%S").replace(year=datetime.now().year)
                if ts >= cutoff:
                    count += 1
            except ValueError:
                continue

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
def execute():
    data = request.get_json() or {}
    action = data.get("action")

    # --- Action validation ---
    if not action:
        return jsonify({"error": "missing action"}), 400
    if action not in ACTION_MAP:
        return jsonify({"error": f"unknown action '{action}'"}), 400

    action_spec = ACTION_MAP[action]

    # --- Field validation ---
    DEFAULT_REQUIRES = ["token", "place_id", "datastore_name"]
    required_fields = action_spec.get("requires", DEFAULT_REQUIRES)
    missing_fields = [f for f in required_fields if not data.get(f)]
    if missing_fields:
        return jsonify({"error": f"missing fields: {missing_fields}"}), 400

    # --- Auth ---
    if data.get("token") != TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    # --- Arg validation ---
    for arg, default in action_spec.get("defaults", {}).items():
        data.setdefault(arg, default)

    missing_args = [arg for arg in action_spec["args"] if arg not in data]
    if missing_args:
        return jsonify({"error": f"missing args: {missing_args}"}), 400

    # --- Execute ---
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


@externaldb_bp.route("/api/logs/stream", methods=["POST"])
def stream_logs():
    data = request.get_json() or {}

    # Auth check
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = auth_header or data.get("token")

    if not token or token != TOKEN:
        return jsonify({"valid": False, "error": "Unauthorized"}), 401

    log_type = data.get("type", "activity")

    if log_type not in LOG_REGISTRY:
        return f"[SYSTEM ERROR] Invalid or unauthorized log stream type: '{log_type}'", 400

    file_path = LOG_REGISTRY[log_type]

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return "".join(lines[-40:])
        except Exception as e:
            return f"[SYSTEM ERROR] Failed to read log file: {str(e)}", 500

    return f"[SYSTEM] Live stream channel '{log_type}' initialized. Waiting for entries..."