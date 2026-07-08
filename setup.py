import os
import sys

# =========================================================
# PROJECT ROOT (THIS FIXES YOUR ISSUE)
# This assumes setup.py is located in the PROJECT ROOT
# =========================================================
ROOT = os.path.abspath(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.py")

def setup():
    if os.path.exists(CONFIG_PATH):
        response = input("config.py already exists. Overwrite? (y/n): ").strip().lower()
        if response != "y":
            print("Setup cancelled.")
            return

    print("\n=== ExternalDB Setup ===\n")

    token = input("Secret token: ").strip()
    while not token:
        token = input("Secret token cannot be empty: ").strip()

    server_url = input("Server URL: ").strip()
    while not server_url:
        server_url = input("Server URL cannot be empty: ").strip()

    git_ssh_key = input("Git SSH key path (optional): ").strip()

    config_content = f"""import os

ROOT = os.path.abspath(os.path.dirname(__file__))

TOKEN = "{token}"
SERVER_URL = "{server_url}"
GIT_SSH_KEY = "{git_ssh_key}"

DB_DIR = os.path.join(ROOT, "databases")
LOG_DIR = os.path.join(ROOT, "logs")
CORE_DIR = os.path.join(ROOT, "core")

LOCAL_URL = "http://127.0.0.1:5000"
"""

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(config_content)

    # ALWAYS create folders in PROJECT ROOT
    os.makedirs(os.path.join(ROOT, "databases"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "core"), exist_ok=True)

    print("\n✔ config.py created at ROOT")
    print("✔ databases/ created at ROOT")
    print("✔ logs/ created at ROOT")
    print("✔ core/ created at ROOT")
    print("✔ setup complete\n")


if __name__ == "__main__":
    setup()

    if input("Run tests? (y/n): ").strip().lower() == "y":
        import subprocess
        test_path = os.path.join(ROOT, "Tests", "local_test.py")
        subprocess.run([sys.executable, test_path])