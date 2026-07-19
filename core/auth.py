import logging
from functools import wraps
from flask import request, jsonify
from config import TOKEN

logger = logging.getLogger(__name__)


def extract_token():
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ")[1]
    return auth_header or (request.get_json() or {}).get("token")

def is_valid_token(token):
    return token and token == TOKEN

def check_token():
    token = extract_token()
    if not is_valid_token(token):
        return jsonify({"valid": False, "error": "Unauthorized"}), 401
    return None

def require_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        error = check_token()
        if error:
            return error
        return f(*args, **kwargs)
    return decorated_function