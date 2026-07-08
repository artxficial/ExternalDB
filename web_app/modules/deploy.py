# FlaskModules/deploy.py
import os
import subprocess
import git
from flask import Blueprint, jsonify
from config import GIT_SSH_KEY, DB_DIR  


deploy_bp = Blueprint("deploy", __name__)

@deploy_bp.route("/git_update", methods=["POST"])
def git_update():
    try:
        repo = git.Repo(DB_DIR)
        origin = repo.remotes.origin

        os.environ["GIT_SSH_COMMAND"] = f"ssh -i {GIT_SSH_KEY} -o StrictHostKeyChecking=no"

        repo.git.checkout("main")
        origin.pull()

        subprocess.Popen(["sudo", "systemctl", "restart", "webhook"])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print("Git update failed:", e)
        return jsonify({"error": str(e)}), 500


@deploy_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200