from flask import Blueprint, render_template
import psutil
import subprocess
import time
from datetime import datetime, timezone, timedelta

frontend_bp = Blueprint("frontend", __name__)

EST = timezone(timedelta(hours=-5))

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