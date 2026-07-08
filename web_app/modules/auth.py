from flask import Blueprint, jsonify, request
from functools import wraps
from config import TOKEN  # Single token imported from config.py

# --- INITIALIZE BLUEPRINT ---
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# --- THE SECURITY DECORATOR ---
def require_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Look for the token in headers or the JSON body
        auth_header = request.headers.get("Authorization")
        
        # Clean up 'Bearer <token>' if present, otherwise take raw header
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = auth_header or (request.get_json() or {}).get("token")
        
        # Validate against the single configuration TOKEN
        if not token or token != TOKEN:
            print(f"[AUTH FAILED] Unauthorized access attempt blocked from IP: {request.remote_addr}")
            return jsonify({"valid": False, "error": "Unauthorized: Invalid or missing security token."}), 401
            
        return f(*args, **kwargs)
    return decorated_function


# --- THE PUBLIC VERIFICATION ROUTE ---
@auth_bp.route("/verify_token", methods=["POST"])
def verify_token():
    #print("--- [DEBUG] INCOMING AUTHENTICATION REQUEST RECEIVED ---")
    
    data = request.get_json() or {}
    user_token = data.get("token")
    print(f"[DEBUG] User submitted token: {user_token}")

    if not user_token:
        print("[DEBUG] Failed: No token was found in payload.")
        return jsonify({"valid": False, "error": "No token provided"}), 400
    # Validate against the single configuration TOKEN
    if user_token == TOKEN:
        print("[AUTH SUCCESS] Token accepted via config file verification.\n")
        return jsonify({"valid": True}), 200
        
    print("[AUTH FAILED] Submitted token did not match configuration entries.")
    return jsonify({"valid": False, "error": "Invalid token"}), 401