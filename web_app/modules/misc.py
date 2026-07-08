import requests
from flask import Blueprint, jsonify, Response

theo_bp = Blueprint("theo", __name__)

URL = "https://offsets.imtheo.lol/Offsets.json"

@theo_bp.route("/theo", methods=["GET"])
def theo():
    try:
        response = requests.get(URL, timeout=10)
                
        return Response(
            response.content, 
            status=response.status_code, 
            mimetype="application/json"
        )
        
    except requests.exceptions.RequestException as e:
        # Handle cases where the external site is down or times out
        return jsonify({"error": "Failed to fetch offsets", "details": str(e)}), 502