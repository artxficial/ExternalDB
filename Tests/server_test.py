import requests
import sys, os 

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TOKEN, SERVER_URL

# Basic connection test
print('ok')
print("Testing connection...")
r = requests.get(SERVER_URL)
print(f"GET: {r.status_code} - {r.text.strip()}\n")

# Auth test
print("Testing auth...")
r = requests.post(SERVER_URL, json={"token": "wrong", "action": "GetAsync", "datastore_name": "Test", "place_id": 99999, "key": 1})
print(f"Bad token: {r.status_code} - {r.json()}")

r = requests.post(SERVER_URL, json={"token": TOKEN, "action": "GetAsync", "datastore_name": "Test", "place_id": 99999, "key": 1})
print(f"Good token: {r.status_code} - {r.json()}\n")

# Write + Read test
print("Testing write/read...")
r = requests.post(SERVER_URL, json={"token": TOKEN, "action": "SetAsync", "datastore_name": "Test", "place_id": 99999, "key": 1, "value": 42})
print(f"SetAsync: {r.json()}")

r = requests.post(SERVER_URL, json={"token": TOKEN, "action": "GetAsync", "datastore_name": "Test", "place_id": 99999, "key": 1})
print(f"GetAsync: {r.json()}")

# Cleanup
requests.post(SERVER_URL, json={"token": TOKEN, "action": "RemoveDatastore", "place_id": 99999, "key": "Test"})
print("\nDone. Server is working.")