"""
Live integration verification script for Flask REST API endpoints and contracts.
Runs non-destructive queries against http://localhost:5000.
"""
import requests
import json

BASE = "http://localhost:5000/api/v1"

endpoints = [
    ("GET", "/health", 200),
    ("GET", "/stations", 200),
    ("GET", "/stations/ST001", 200),
    ("GET", "/stations/UNKNOWN_999", 404),
    ("GET", "/telemetry/latest?limit=5", 200),
    ("GET", "/telemetry/latest?limit=0", 400),
    ("GET", "/telemetry/ST001?limit=5", 200),
    ("GET", "/telemetry/ST001?order=invalid", 400),
    ("GET", "/alerts?limit=5", 200),
    ("GET", "/alerts?severity=INVALID", 400),
    ("POST", "/alerts/UNKNOWN_ALERT/acknowledge", 404),
    ("GET", "/analytics/temperature?days=1", 200),
    ("GET", "/analytics/air-quality?days=1", 200),
    ("GET", "/analytics/station-comparison", 200),
    ("GET", "/simulator/status", 200),
    ("POST", "/simulator/control", 400),  # Missing action
]

print("=== TESTING FLASK REST API ENDPOINTS ===")
all_passed = True
for method, ep, exp_code in endpoints:
    url = f"{BASE}{ep}"
    if method == "GET":
        r = requests.get(url, timeout=10)
    else:
        r = requests.post(url, json={}, timeout=10)
    passed = (r.status_code == exp_code)
    if not passed:
        all_passed = False
    status_label = "PASS" if passed else "FAIL"
    print(f"{method} {ep} -> Status: {r.status_code} (Expected {exp_code}) -> {status_label}")
    if not passed:
        print("  Response:", r.text[:200])

print("ALL LIVE ENDPOINT CONTRACTS PASSED:", all_passed)
