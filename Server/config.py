import os

_ROOT = os.path.dirname(os.path.abspath(__file__))

TOKEN = "test-token"
BASE_DIR = os.path.join(_ROOT, "Databases")
SERVER_DIR = os.path.join(_ROOT, "Server")
GIT_SSH_KEY = "/home/ubuntu/.ssh/github_deploy"
SERVER_URL = "http://127.0.0.1:5000"  # change to https://yourdomain.com on VPS