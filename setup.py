import os
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")

def setup():
    if os.path.exists(CONFIG_PATH):
        response = input("config.py already exists. Overwrite? (y/n): ").strip().lower()
        if response != "y":
            print("Setup cancelled.")
            return

    print("\n=== ExternalDB Setup ===\n")

    token = input("Secret token: ").strip()
    while not token:
        print("  Token cannot be empty.")
        token = input("Secret token: ").strip()

    server_url = input("Server URL (default: http://127.0.0.1:5000): ").strip()
    if not server_url:
        server_url = "http://127.0.0.1:5000"

    git_ssh_key = input("Git SSH key path (leave blank to skip): ").strip()
    if not git_ssh_key:
        git_ssh_key = ""

    config_content = f'''import os

_ROOT = os.path.dirname(os.path.abspath(__file__))

TOKEN = "{token}"
BASE_DIR = os.path.join(_ROOT, "Databases")
SERVER_DIR = os.path.join(_ROOT, "Server")
GIT_SSH_KEY = "{git_ssh_key}"
SERVER_URL = "{server_url}"
'''

    with open(CONFIG_PATH, "w") as f:
        f.write(config_content)

    # Create directories
    root = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(root, "Databases"), exist_ok=True)
    os.makedirs(os.path.join(root, "Server"), exist_ok=True)

    print(f"\nconfig.py created at {CONFIG_PATH}")
    print("Databases/ directory ready")
    print("Setup complete.\n")


if __name__ == "__main__":
    setup()
    
    response = input("Run tests? (y/n): ").strip().lower()
    if response == "y":
        import subprocess
        test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tests", "full_test.py")
        subprocess.run([sys.executable, test_path])
