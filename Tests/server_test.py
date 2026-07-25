import requests
import sys, os 

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import TOKEN, SERVER_URL

#SERVER_URL = SERVER_URL + "/externaldb/api/execute" 

SERVER_URL = "https://artxficial.dev/externaldb/api/execute"

print(f"Using SERVER_URL: {SERVER_URL}")

# Basic connection test
print("Testing connection...")
r = requests.get(SERVER_URL)
print(f"Connection test: {r.status_code} - {r.json()}\n")

# Auth test
print("Testing auth...")

# 1. Test with a bad token in the header
bad_headers = {"Authorization": "Bearer wrong"}

r = requests.post(
    SERVER_URL, 
    headers=bad_headers, 
    json={"action": "GetAsync", "datastore_name": "Test", "place_id": 99999, "key": 1}
)
print(f"Bad token: {r.status_code} - {r.json()}")

# 2. Test with the correct token in the header
good_headers = {"Authorization": f"Bearer {TOKEN}"}

r = requests.post(
    SERVER_URL, 
    headers=good_headers, 
    json={"action": "GetAsync", "datastore_name": "Test", "place_id": 99999, "key": 1}
)
print(f"Good token: {r.status_code} - {r.json()}\n")

# Write + Read test
print("Testing write/read...")
r = requests.post(
    SERVER_URL, 
    headers=good_headers, 
    json={"action": "SetAsync", "datastore_name": "Test", "place_id": 99999, "key": 1, "value": 42}
)
print(f"SetAsync: {r.json()}")

r = requests.post(
    SERVER_URL, 
    headers=good_headers, 
    json={"action": "GetAsync", "datastore_name": "Test", "place_id": 99999, "key": 1}
)
print(f"GetAsync: {r.json()}")

# Cleanup
requests.post(
    SERVER_URL, 
    headers=good_headers, 
    json={"action": "RemoveDatastore", "place_id": 99999, "key": "Test"}
)
print("\nDone. Server is working.")