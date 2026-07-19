import logging
from flask import Blueprint, jsonify
from core.auth import extract_token, is_valid_token, log_auth_result

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/verify_token", methods=["POST"])
def verify_token():
    from flask import request
    token = extract_token()
    log_auth_result(token, ip=request.remote_addr)
    if not token:
        return jsonify({"valid": False, "error": "No token provided"}), 400
    if not is_valid_token(token):
        return jsonify({"valid": False, "error": "Invalid token"}), 401
    return jsonify({"valid": True}), 200