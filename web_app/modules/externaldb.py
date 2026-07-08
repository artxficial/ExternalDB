import os
import sqlite3
from datetime import datetime
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
# DASHBOARD
# =========================================================

@externaldb_bp.route("/", methods=["GET"])
def dashboard():
    return render_template("ExternalDB.html")


# =========================================================
# EXECUTE API (ROBLOX)
# =========================================================

@externaldb_bp.route("/api/execute", methods=["GET"])
def status():
    return jsonify({"status": "Use post method to execute actions"}), 200 

from core.database_manager import db_manager
from core.database_class import ACTION_MAP

@externaldb_bp.route("/api/execute", methods=["POST"])
@externaldb_bp.route("/api/execute", methods=["POST"])
def execute():
    data = request.get_json() or {}
 
    token = data.get("token")
    db_id = data.get("datastore_name")
    place_id = data.get("place_id")
    action = data.get("action")
 
    if not token or not db_id or not place_id or not action:
        return jsonify({"error": "missing auth/db/place_id/action"}), 400
 
    if token != TOKEN:
        return jsonify({"error": "unauthorized"}), 401
 
    if action not in ACTION_MAP:
        return jsonify({"error": f"unknown action '{action}'"}), 400
 
    action_spec = ACTION_MAP[action]
    defaults = action_spec.get("defaults", {})
 
    # Apply defaults for any missing args before checking what's still missing.
    for arg, default in defaults.items():
        data.setdefault(arg, default)
 
    missing = [arg for arg in action_spec["args"] if arg not in data]
    if missing:
        return jsonify({"error": f"missing args: {missing}"}), 400
 
    context = {
        "place_id": place_id,
        "datastore_name": db_id,
        "query_template": action_spec.get("query"),
        "multi": action_spec.get("multi", False),
    }

    try:
        if action_spec["op_type"] == "single":
            build_params = action_spec.get("build_params")
            if build_params:
                params = build_params(data)
            else:
                params = [data[arg] for arg in action_spec["args"]]

            result = db_manager.execute_single(context, params)

        elif action_spec["op_type"] == "bulk":
            bulk_arg_name = action_spec["args"][0]
            payload = data[bulk_arg_name]
            result = db_manager.execute_bulk(context, payload)

        # ---> NEW: Handle custom Python functions <---
        elif action_spec["op_type"] == "function":
            handler = action_spec["handler"]
            # Pass everything the handler might need to execute
            result = handler(db_manager, context, data)

        else:
            return jsonify({"error": f"unknown op_type for '{action}'"}), 500

        write_db_log(db_id, f"[{datetime.utcnow()}] ACTION={action}")

        return jsonify({
            "status": "success",
            "db": db_id,
            "action": action,
            "result": result
        })

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
    """Single unified endpoint to fetch tail logs for any registered log type."""
    # Parse the incoming JSON body
    data = request.get_json() or {}
    log_type = data.get("type", "activity")  # Default fallback if not provided
    token = data.get("token")

    # Security check: Ensure they aren't requesting an unregistered file path
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