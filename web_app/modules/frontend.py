from flask import Blueprint, render_template, jsonify
import psutil
import subprocess
import time
from datetime import datetime, timezone, timedelta
from config import LASTFM_API_KEY
import requests


frontend_bp = Blueprint("frontend", __name__)

EST = timezone(timedelta(hours=-4))

def get_last_deploy():
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=iso"],
            capture_output=True, text=True
        )
        raw = result.stdout.strip()
        if not raw:
            return "Unknown"
        dt = datetime.fromisoformat(raw).astimezone(EST)
        return dt.strftime("[%m/%d] %I:%M %p")
    except Exception:
        return "Unknown"
    
@frontend_bp.route("/", methods=["GET"])
def home():
    mem = psutil.virtual_memory()
    ram = f"{mem.used / (1024**2):.0f} MB / {mem.total / (1024**2):.0f} MB"
    cpu = f"{psutil.cpu_percent(interval=0.1):.1f}%"
    last_deploy = get_last_deploy()

    return render_template("home.html", ram=ram, cpu=cpu, last_deploy=last_deploy)


@frontend_bp.route("/lastfm")
def lastfm():
    base = {
        "method": None,
        "user": "real_artxficial",
        "api_key": LASTFM_API_KEY,
        "format": "json"
    }

    def lfm(method, **kwargs):
        return requests.get("https://ws.audioscrobbler.com/2.0/", params={**base, "method": method, **kwargs}).json()

    albums = lfm("user.gettopalbums", period="7day", limit=9)
    recent = lfm("user.getrecenttracks", limit=1)
    info = lfm("user.getinfo")

    track = recent["recenttracks"]["track"][0]

    return jsonify({
        "albums": [{"name": a["name"], "artist": a["artist"]["name"], "image": a["image"][3]["#text"]} for a in albums["topalbums"]["album"]],
        "nowplaying": {
            "track": track["name"],
            "artist": track["artist"]["#text"],
            "image": track["image"][2]["#text"],
            "live": track.get("@attr", {}).get("nowplaying", False)
        },
        "scrobbles": info["user"]["playcount"]
    })