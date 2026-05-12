import requests
import json
import sys
import os
import subprocess
import time
import atexit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TOKEN, LOCAL_URL

# ===== CONFIG =====
PLACE_ID = 99999
DATASTORE = "TestStore"
TEST_KEY = 123456
# ==================

passed = 0
failed = 0

def test(name, payload, expect_success=True):
    global passed, failed
    try:
        start = time.time()
        r = requests.post(LOCAL_URL, json=payload, timeout=10)
        elapsed = (time.time() - start) * 1000
        data = r.json()

        if expect_success and data.get("status") == "success":
            print(f"  PASS  {name} ({elapsed:.0f}ms)")
            passed += 1
            return data.get("results")
        elif not expect_success and r.status_code != 200:
            print(f"  PASS  {name} ({elapsed:.0f}ms) (expected failure: {data.get('error')})")
            passed += 1
            return None
        else:
            print(f"  FAIL  {name} ({elapsed:.0f}ms) -> {data}")
            failed += 1
            return None
    except Exception as e:
        print(f"  FAIL  {name} -> {e}")
        failed += 1
        return None


def bp(action, **kwargs):
    return {
        "token": TOKEN,
        "action": action,
        "datastore_name": DATASTORE,
        "place_id": PLACE_ID,
        **kwargs,
    }


# -----------------------------
# Test Groups
# -----------------------------

def test_auth():
    global failed
    test("Bad token rejected", {
        "token": "wrong", "action": "GetAsync",
        "datastore_name": DATASTORE, "place_id": PLACE_ID, "key": TEST_KEY,
    }, expect_success=False)

    test("Missing token rejected", {
        "action": "GetAsync",
        "datastore_name": DATASTORE, "place_id": PLACE_ID, "key": TEST_KEY,
    }, expect_success=False)

    test("Valid token accepted", bp("GetAsync", key=TEST_KEY))

    if failed > 0:
        print("\n  Auth failed. Stopping.")
        sys.exit(1)


def test_write():
    test("SetAsync", bp("SetAsync", key=TEST_KEY, value=100))
    test("SetAsync (second key)", bp("SetAsync", key=TEST_KEY + 1, value=200))
    test("SetAsync (third key)", bp("SetAsync", key=TEST_KEY + 2, value=50))
    test("IncrementAsync", bp("IncrementAsync", key=TEST_KEY, value=10))
    test("BulkSetAsync", bp("BulkSetAsync", dictionary={
        str(TEST_KEY + 10): 500,
        str(TEST_KEY + 11): 600,
        str(TEST_KEY + 12): 700,
    }))
    test("BulkIncrementAsync", bp("BulkIncrementAsync", dictionary={
        str(TEST_KEY): 5,
        str(TEST_KEY + 1): 10,
    }))


def test_read():
    result = test("GetAsync", bp("GetAsync", key=TEST_KEY))
    if result is not None:
        expected = 115
        status = "correct" if result == expected else f"WRONG (expected {expected})"
        print(f"         Value: {result} - {status}")

    test("GetRankAsync", bp("GetRankAsync", key=TEST_KEY))
    test("GetValueAtPercentile", bp("GetValueAtPercentile", percentile=0.5))
    test("GetKeysNearRankAsync", bp("GetKeysNearRankAsync", rank=1, spread=3))
    test("ListOrderedKeysAsync (no offset)", bp("ListOrderedKeysAsync", limit=10, start_index=None))
    test("ListOrderedKeysAsync (with offset)", bp("ListOrderedKeysAsync", limit=5, start_index=1))
    test("GetSumOfValues", bp("GetSumOfValues"))
    test("GetAsync (missing key)", bp("GetAsync", key=999999999))
    test("GetRankAsync (missing key)", bp("GetRankAsync", key=999999999))


def test_bulk_read():
    test("BulkGetAsync", bp("BulkGetAsync", list=[TEST_KEY, TEST_KEY + 1, TEST_KEY + 2]))
    test("BulkGetRankAsync", bp("BulkGetRankAsync", list=[TEST_KEY, TEST_KEY + 1]))
    test("BulkGetValueAtPercentile", bp("BulkGetValueAtPercentile", list=[0.25, 0.5, 0.75]))
    test("BulkGetKeysNearRankAsync", bp("BulkGetKeysNearRankAsync", list=[1, 2, 3], spread=2))


def test_snapshots():
    test("GetLastSnapshotTime", bp("GetLastSnapshotTime"))
    test("CompareToSnapshotAsync", bp("CompareToSnapshotAsync", key=TEST_KEY))
    test("BulkCompareToSnapshotAsync", bp("BulkCompareToSnapshotAsync", list=[TEST_KEY, TEST_KEY + 1]))


def test_delete():
    test("RemoveAsync", bp("RemoveAsync", key=TEST_KEY + 2))
    test("BulkRemoveAsync", bp("BulkRemoveAsync", list=[TEST_KEY + 10, TEST_KEY + 11, TEST_KEY + 12]))

    result = test("GetAsync (verify delete)", bp("GetAsync", key=TEST_KEY + 2))
    if result is None:
        print("         Deletion confirmed")


def test_admin():
    test("ListDatastores", {
        "token": TOKEN, "action": "ListDatastores", "place_id": PLACE_ID,
    })


def test_cleanup():
    test("RemoveDatastore", {
        "token": TOKEN, "action": "RemoveDatastore",
        "key": DATASTORE, "place_id": PLACE_ID,
    })
    test("ListDatastores (verify cleanup)", {
        "token": TOKEN, "action": "ListDatastores", "place_id": PLACE_ID,
    })


def test_health():
    global passed, failed
    try:
        r = requests.get(f"{LOCAL_URL}/health", timeout=5)
        if r.status_code == 200:
            print("  PASS  Health endpoint")
            passed += 1
        else:
            print(f"  FAIL  Health endpoint -> {r.status_code}")
            failed += 1
    except:
        print("  SKIP  Health endpoint (not implemented)")


# -----------------------------
# Test Registry
# -----------------------------

TESTS = {
    "auth":      test_auth,
    "write":     test_write,
    "read":      test_read,
    "bulk_read": test_bulk_read,
    "snapshots": test_snapshots,
    "delete":    test_delete,
    "admin":     test_admin,
    "cleanup":   test_cleanup,
    "health":    test_health,
}

# -----------------------------
# Server Startup
# -----------------------------

def start_server():
    print("Starting local server...")
    server = subprocess.Popen(
        [sys.executable, "Server/app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if server.poll() is not None:
        print("Server crashed.")
        print("STDOUT:", server.stdout.read().decode())
        print("STDERR:", server.stderr.read().decode())
        sys.exit(1)

    atexit.register(server.terminate)

    for i in range(3): 
        try:
            requests.get(LOCAL_URL, timeout=1)
            print("Server is up.\n")
            return server
        except:
            print("Trying to start server...")
            time.sleep(0.5)

    print("Server failed to respond.")
    print("STDOUT:", server.stdout.read().decode())
    print("STDERR:", server.stderr.read().decode())
    server.terminate()
    sys.exit(1)

# -----------------------------
# Main
# -----------------------------

if __name__ == "__main__":
    server = start_server()

    # Usage:
    #   python full_test.py              -> run all tests
    #   python full_test.py auth         -> run only auth
    #   python full_test.py write read   -> run write and read
    #   python full_test.py list         -> show available groups

    args = sys.argv[1:]

    if "list" in args:
        print("Available test groups:")
        for name in TESTS:
            print(f"  {name}")
        sys.exit(0)

    groups = args if args else TESTS.keys()

    print("=" * 50)
    print("  Server Test Suite")
    print("=" * 50)

    for group in groups:
        if group not in TESTS:
            print(f"\n  Unknown group: '{group}'")
            print(f"  Available: {', '.join(TESTS.keys())}")
            sys.exit(1)

        print(f"\n--- {group} ---")
        TESTS[group]()

    print("\n" + "=" * 50)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 50)

    if failed > 0:
        sys.exit(1)