import logging
from flask import Blueprint, jsonify
from core.auth import extract_token, is_valid_token

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/verify_token", methods=["POST"])
def verify_token():
    token = extract_token()
    if not token:
        logger.warning("[AUTH FAILED] No token in payload.")
        return jsonify({"valid": False, "error": "No token provided"}), 400
    if not is_valid_token(token):
        logger.warning("[AUTH FAILED] Token did not match.")
        return jsonify({"valid": False, "error": "Invalid token"}), 401
    logger.info("[AUTH SUCCESS] Token accepted.")
    return jsonify({"valid": True}), 200