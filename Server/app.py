import os
import json
import git
import subprocess
import sys
from flask import Flask, request, jsonify, send_file, render_template

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TOKEN, BASE_DIR, GIT_SSH_KEY

import database_functions as DatastoreService

app = Flask(__name__,
    template_folder=os.path.join(_ROOT, "Web", "templates"),
    static_folder=os.path.join(_ROOT, "Web", "static"),
)
# -----------------------------
# Action Registry
# -----------------------------

ACTION_MAP = {
    # Single key operations
    "GetAsync":                     {"args": {"key": int}},
    "GetRankAsync":                 {"args": {"key": int}},
    "RemoveAsync":                  {"args": {"key": int}},
    "SetAsync":                     {"args": {"key": int, "value": (int, float)}},
    "IncrementAsync":               {"args": {"key": int, "value": (int, float)}},
    "GetValueAtPercentile":         {"args": {"percentile": float}},
    "GetKeysNearRankAsync":         {"args": {"rank": int, "spread": int}},
    "ListOrderedKeysAsync":         {"args": {"limit": int, "start_index": int}},
    "CompareToSnapshotAsync":       {"args": {"key": int}},
    "GetLastSnapshotTime":          {"args": {}},
    "GetSumOfValues":               {"args": {}},

    # Bulk operations
    "BulkSetAsync":                 {"args": {"dictionary": dict}},
    "BulkIncrementAsync":           {"args": {"dictionary": dict}},
    "BulkGetAsync":                 {"args": {"list": list}},
    "BulkRemoveAsync":              {"args": {"list": list}},
    "BulkGetRankAsync":             {"args": {"list": list}},
    "BulkGetValueAtPercentile":     {"args": {"list": list}},
    "BulkCompareToSnapshotAsync":   {"args": {"list": list}},
    "BulkGetKeysNearRankAsync":     {"args": {"list": list, "spread": int}},

    # Admin (not part of Datastore class)
    "ListDatastores":               {"args": {"place_id": int}, "admin": True},
    "RemoveDatastore":              {"args": {"key": str, "place_id": int}, "admin": True},
}

OPTIONAL_ARGS = {"start_index"}

# -----------------------------
# Auth
# -----------------------------

def authenticate(data):
    token = data.get("token") if isinstance(data, dict) else None
    if token != TOKEN:
        return False
    return True

# -----------------------------
# Validation
# -----------------------------

def validate_args(data):
    action = data.get("action")
    action_info = ACTION_MAP.get(action)

    if not action_info:
        return None, f"Unknown action: {action}"

    args = []
    for key, expected_type in action_info["args"].items():
        value = data.get(key)

        if key in OPTIONAL_ARGS:
            args.append(value)
            continue

        if value is None:
            return None, f"Missing '{key}'"

        if not isinstance(value, expected_type):
            type_name = (
                ", ".join(t.__name__ for t in expected_type)
                if isinstance(expected_type, tuple)
                else expected_type.__name__
            )
            return None, f"'{key}' must be of type {type_name}"

        args.append(value)

    return tuple(args), None


def validate_request(data):
    if not data:
        return None, ({"error": "No JSON provided"}, 400)

    if not authenticate(data):
        return None, ({"error": "Unauthorized"}, 401)

    action = data.get("action")
    if not action:
        return None, ({"error": "Missing action"}, 400)

    if action not in ACTION_MAP:
        return None, ({"error": f"Unknown action: {action}"}, 400)

    place_id = data.get("place_id")
    if not place_id:
        return None, ({"error": "Missing place_id"}, 400)

    datastore_name = data.get("datastore_name")
    if not datastore_name and not ACTION_MAP[action].get("admin"):
        return None, ({"error": "Missing datastore_name"}, 400)

    args, err = validate_args(data)
    if err:
        return None, ({"error": err}, 400)

    return {"datastore_name": datastore_name, "action": action, "args": args, "place_id": place_id}, None

# -----------------------------
# Request Processing
# -----------------------------

def process_action(datastore_name, action, args, place_id):
    if ACTION_MAP[action].get("admin"):
        func = getattr(DatastoreService, action, None)
        if not func:
            raise AttributeError(f"Admin function '{action}' not found")
        return func(*args)

    datastore = DatastoreService.GetDatastore(datastore_name, place_id)
    try:
        func = getattr(datastore, action)
        return func(*args)
    finally:
        datastore.Disconnect()

# -----------------------------
# Routes
# -----------------------------

@app.route("/", methods=["POST", "GET"])
def main_endpoint():
    if request.method == "GET" and not request.is_json:
        return render_template("home.html")

    data = request.get_json()
    validated, error = validate_request(data)

    if error:
        return jsonify(error[0]), error[1]

    try:
        result = process_action(**validated)
        return jsonify({"status": "success", "results": result}), 200
    except AttributeError:
        return jsonify({"error": f"Action '{validated['action']}' not found"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------
# Race Logging
# -----------------------------

def get_log_path(log_id="default"):
    return os.path.join(BASE_DIR, f"race_log_{log_id}.json")


def load_log(path):
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_log(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


@app.route("/log", methods=["POST"])
def log_data():
    data = request.get_json()

    if not authenticate(data):
        return jsonify({"error": "Unauthorized"}), 401

    snapshots = data.get("snapshots")
    if not snapshots:
        return jsonify({"error": "No snapshots provided"}), 400

    log_id = data.get("id") or "default"
    log_path = get_log_path(log_id)
    log = load_log(log_path)

    for i, snap in enumerate(snapshots):
        snap["frame_index"] = i
        log.append(snap)

    save_log(log_path, log)
    return jsonify({"status": "success", "run_id": log_id, "total_snapshots": len(log)}), 200


@app.route("/download_log", methods=["GET"])
def download_log():
    token = request.args.get("token")
    if token != TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    default_log = get_log_path()
    if not os.path.exists(default_log):
        return jsonify({"error": "No log file found"}), 404

    return send_file(default_log, as_attachment=True, download_name="race_log.json")

# -----------------------------
# Deployment
# -----------------------------

@app.route("/git_update", methods=["POST"])
def git_update():
    try:
        repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        repo = git.Repo(repo_path)
        origin = repo.remotes.origin

        os.environ["GIT_SSH_COMMAND"] = f"ssh -i {GIT_SSH_KEY} -o StrictHostKeyChecking=no"

        repo.git.checkout("main")
        origin.pull()

        subprocess.Popen(["sudo", "systemctl", "restart", "webhook"])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print("Git update failed:", e)
        return jsonify({"error": str(e)}), 500
    
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

app.config['TEMPLATES_AUTO_RELOAD'] = True

if __name__ == "__main__":
    from livereload import Server
    server = Server(app.wsgi_app)
    server.watch("Web/templates/")
    server.watch("Web/static/")
    server.serve(port=5000)