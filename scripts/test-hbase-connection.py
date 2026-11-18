"""
Connection and Health Verification Script for HBase REST and Standalone Cluster.
"""
import requests
import json
import base64
import sys

BASE_URL = "http://localhost:8085"

def test_cluster_health():
    print("Testing HBase REST Cluster Version...")
    try:
        res = requests.get(f"{BASE_URL}/version/cluster", headers={"Accept": "application/json"}, timeout=5)
        if res.status_code == 200:
            print(f"SUCCESS: Cluster Version is {res.json().get('Version')}")
            return True
        else:
            print(f"FAILED: Status {res.status_code}")
            return False
    except Exception as e:
        print(f"ERROR connecting to HBase REST at {BASE_URL}: {e}")
        return False

def test_read_row(table="rest_microclimate_test", row_key="station_001_20261117_230000"):
    print(f"Reading row '{row_key}' from table '{table}'...")
    try:
        res = requests.get(f"{BASE_URL}/{table}/{row_key}", headers={"Accept": "application/json"}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            for r in data.get("Row", []):
                k = base64.b64decode(r["key"]).decode("utf-8")
                print(f"Row Key: {k}")
                for cell in r.get("Cell", []):
                    col = base64.b64decode(cell["column"]).decode("utf-8")
                    val = base64.b64decode(cell["$"]).decode("utf-8")
                    print(f"  {col} = {val}")
            return True
        else:
            print(f"Failed to read row. Status: {res.status_code}")
            return False
    except Exception as e:
        print(f"ERROR reading row: {e}")
        return False

if __name__ == "__main__":
    ok1 = test_cluster_health()
    ok2 = test_read_row()
    if ok1 and ok2:
        print("\nHBase environment is fully operational!")
        sys.exit(0)
    else:
        print("\nHBase health check failed.")
        sys.exit(1)
