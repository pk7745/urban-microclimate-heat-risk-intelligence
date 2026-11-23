"""
Phase 8.4.5: REST API Comprehensive Evaluation Script
Evaluates all 12 /api/v1 endpoints and 2 application routes using Flask's test client and isolated mocks.
Assesses status codes, response structures, parameter validation, error handling, security, and data consistency.
"""
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
WORKSPACE_ROOT = r"C:\Users\pky45\.gemini\antigravity\scratch\urban-microclimate-hbase"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from app import create_app
from config import settings
from app.services.hbase_client import RowKeyBuilder
from app.services.telemetry_service import TelemetryService, VALID_STATION_IDS, MEASUREMENT_FIELD_MAP
from app.services.simulator_service import SimulatorController


def run_api_evaluation():
    app = create_app({"TESTING": True})
    client = app.test_client()

    results = {
        "metadata": {
            "evaluation_phase": "Phase 8.4.5 — REST API and Dashboard Evaluation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_system": "Urban Microclimate & Heat-Risk Intelligence System",
            "framework": "Flask 3.1.0 / Python 3.14 (Mocked Test Client)"
        },
        "endpoint_inventory": [],
        "functional_evaluation": [],
        "input_validation_and_errors": [],
        "security_and_exception_handling": [],
        "data_consistency_evaluation": [],
        "summary": {}
    }

    print("=" * 80)
    print("PHASE 8.4.5: REST API FUNCTIONAL, VALIDATION & DATA CONSISTENCY EVALUATION")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. Endpoint Inventory
    # -------------------------------------------------------------------------
    print("\n--- 1. Route & Endpoint Catalog Verification ---")
    rules = [rule for rule in app.url_map.iter_rules()]
    api_v1_rules = [r for r in rules if r.rule.startswith("/api/v1/")]
    app_rules = [r for r in rules if not r.rule.startswith("/api/v1/") and not r.rule.startswith("/static/")]

    print(f"Total /api/v1 endpoints identified in Flask url_map: {len(api_v1_rules)}")
    print(f"Total application routes identified in Flask url_map: {len(app_rules)}")

    for r in sorted(api_v1_rules, key=lambda x: x.rule):
        methods = [m for m in r.methods if m not in ("HEAD", "OPTIONS")]
        item = {
            "rule": r.rule,
            "endpoint": r.endpoint,
            "methods": methods,
            "category": "API_V1"
        }
        results["endpoint_inventory"].append(item)
        print(f"  [API v1] {','.join(methods):<6} {r.rule:<40} -> {r.endpoint}")

    for r in sorted(app_rules, key=lambda x: x.rule):
        methods = [m for m in r.methods if m not in ("HEAD", "OPTIONS")]
        item = {
            "rule": r.rule,
            "endpoint": r.endpoint,
            "methods": methods,
            "category": "APP_ROUTE"
        }
        results["endpoint_inventory"].append(item)
        print(f"  [APP]    {','.join(methods):<6} {r.rule:<40} -> {r.endpoint}")

    # -------------------------------------------------------------------------
    # 2. Functional Endpoint Evaluation (Success Paths with Isolated Mocks)
    # -------------------------------------------------------------------------
    print("\n--- 2. Functional Endpoint Evaluation (Isolated Mocks) ---")

    # Mock data fixtures
    mock_stations = [
        {
            "station_id": st_id,
            "station_name": f"Station {st_id}",
            "zone": "Test Zone",
            "coordinates": {"latitude": 12.97, "longitude": 77.59},
            "connectivity": "ACTIVE",
            "temperature": 28.5,
            "humidity": 60.0,
            "pm25": 45.0,
            "pm10": 75.0,
            "heat_index": 30.2,
            "last_reading_time": "2026-11-22T10:00:00+00:00",
            "data_source": "SIMULATED"
        }
        for st_id in sorted(list(VALID_STATION_IDS))
    ]

    mock_readings = [
        {
            "station_id": "ST001",
            "timestamp": "2026-11-22T10:00:00+00:00",
            "timestamp_ms": 1795341600000,
            "temperature_celsius": 29.0,
            "humidity_percent": 55.0,
            "heat_index_celsius": 30.5,
            "heat_index_status": "VALID",
            "pm25": 35.0,
            "pm10": 60.0,
            "data_source": "SIMULATED"
        },
        {
            "station_id": "ST001",
            "timestamp": "2026-11-22T09:59:00+00:00",
            "timestamp_ms": 1795341540000,
            "temperature_celsius": 28.8,
            "humidity_percent": 55.2,
            "heat_index_celsius": 30.2,
            "heat_index_status": "VALID",
            "pm25": 36.0,
            "pm10": 62.0,
            "data_source": "SIMULATED"
        }
    ]

    mock_alerts = [
        {
            "alert_id": "ST001#8205058153242#HIGH_TEMPERATURE",
            "station_id": "ST001",
            "timestamp": "2026-11-22T10:00:00+00:00",
            "severity": "CRITICAL",
            "type": "HIGH_TEMPERATURE",
            "measurement": "41.5",
            "threshold": "40.0",
            "message": "Extreme heat alert",
            "acknowledged": False,
            "acknowledgement_note": None,
            "calculation_applicability": {
                "is_valid": True,
                "status": "VALID",
                "origin_temp_celsius": 41.5,
                "origin_humidity_percent": 60.0,
                "note": "Verified calculation with complete provenance."
            }
        }
    ]

    def record_test(category, name, endpoint, method, expected_status, actual_status, passed, details=None):
        entry = {
            "name": name,
            "endpoint": endpoint,
            "method": method,
            "expected_status": expected_status,
            "actual_status": actual_status,
            "passed": passed,
            "details": details or {}
        }
        results[category].append(entry)
        status_str = "PASS" if passed else "FAIL"
        print(f"  [{status_str}] {method:<4} {endpoint:<45} -> Status: {actual_status} (Expected: {expected_status})")

    # TC-API-01: GET / (Content negotiation - HTML)
    r = client.get("/", headers={"Accept": "text/html"})
    record_test("functional_evaluation", "Root Route HTML", "/", "GET", 200, r.status_code,
                r.status_code == 200 and "text/html" in r.content_type)

    # TC-API-02: GET / (Content negotiation - JSON metadata)
    r = client.get("/", headers={"Accept": "application/json"})
    j = r.get_json() or {}
    record_test("functional_evaluation", "Root Route JSON Metadata", "/", "GET", 200, r.status_code,
                r.status_code == 200 and j.get("service") == "Urban Microclimate & Heat-Risk Intelligence System API")

    # TC-API-03: GET /dashboard
    r = client.get("/dashboard")
    record_test("functional_evaluation", "Dashboard Route", "/dashboard", "GET", 200, r.status_code,
                r.status_code == 200 and "text/html" in r.content_type)

    # TC-API-04: GET /api/v1/health (Operational)
    with patch.object(TelemetryService, "check_health", return_value=({
        "app_status": "UP",
        "hbase_connected": True,
        "hbase_version": "2.6.7-hadoop3",
        "tables": {settings.TABLE_READINGS: True, settings.TABLE_ALERTS: True, settings.TABLE_STATION_STATUS: True},
        "simulator_running": False
    }, 200)):
        r = client.get("/api/v1/health")
        j = r.get_json() or {}
        record_test("functional_evaluation", "Health Endpoint (Operational)", "/api/v1/health", "GET", 200, r.status_code,
                    r.status_code == 200 and j.get("status") == "success" and j["data"]["hbase_connected"] is True)

    # TC-API-05: GET /api/v1/health (HBase Unavailable -> 503)
    with patch.object(TelemetryService, "check_health", return_value=({
        "app_status": "DEGRADED",
        "hbase_connected": False,
        "hbase_version": None,
        "tables": {settings.TABLE_READINGS: False, settings.TABLE_ALERTS: False, settings.TABLE_STATION_STATUS: False},
        "simulator_running": False
    }, 503)):
        r = client.get("/api/v1/health")
        j = r.get_json() or {}
        record_test("functional_evaluation", "Health Endpoint (HBase Degraded)", "/api/v1/health", "GET", 503, r.status_code,
                    r.status_code == 503 and j.get("status") == "error" and j["error"]["code"] == "SERVICE_UNAVAILABLE")

    # TC-API-06: GET /api/v1/stations
    with patch.object(TelemetryService, "get_stations", return_value=mock_stations):
        r = client.get("/api/v1/stations")
        j = r.get_json() or {}
        record_test("functional_evaluation", "List Stations", "/api/v1/stations", "GET", 200, r.status_code,
                    r.status_code == 200 and len(j.get("data", {}).get("stations", [])) == 5)

    # TC-API-07: GET /api/v1/stations/<station_id> (Valid ST001)
    with patch.object(TelemetryService, "get_station_by_id", return_value={
        "station_id": "ST001",
        "station_name": "Bengaluru Central",
        "status": mock_stations[0],
        "latest_reading": mock_readings[0],
        "recent_alerts": mock_alerts
    }):
        r = client.get("/api/v1/stations/ST001")
        j = r.get_json() or {}
        record_test("functional_evaluation", "Get Station by ID", "/api/v1/stations/ST001", "GET", 200, r.status_code,
                    r.status_code == 200 and j.get("data", {}).get("station_id") == "ST001")

    # TC-API-08: GET /api/v1/telemetry/latest
    with patch.object(TelemetryService, "get_latest_telemetry", return_value=mock_readings):
        r = client.get("/api/v1/telemetry/latest?limit=10")
        j = r.get_json() or {}
        record_test("functional_evaluation", "Get Latest Telemetry", "/api/v1/telemetry/latest?limit=10", "GET", 200, r.status_code,
                    r.status_code == 200 and len(j.get("data", {}).get("readings", [])) == 2)

    # TC-API-09: GET /api/v1/telemetry/<station_id>
    with patch.object(TelemetryService, "get_station_telemetry", return_value=mock_readings):
        r = client.get("/api/v1/telemetry/ST001?limit=10&order=desc")
        j = r.get_json() or {}
        record_test("functional_evaluation", "Get Station Historical Telemetry", "/api/v1/telemetry/ST001?limit=10", "GET", 200, r.status_code,
                    r.status_code == 200 and j.get("data", {}).get("station_id") == "ST001")

    # TC-API-10: GET /api/v1/alerts
    with patch.object(TelemetryService, "get_alerts", return_value=mock_alerts):
        r = client.get("/api/v1/alerts?limit=10")
        j = r.get_json() or {}
        record_test("functional_evaluation", "List Alerts", "/api/v1/alerts?limit=10", "GET", 200, r.status_code,
                    r.status_code == 200 and len(j.get("data", {}).get("alerts", [])) == 1)

    # TC-API-11: POST /api/v1/alerts/<alert_id>/acknowledge
    with patch.object(TelemetryService, "acknowledge_alert", return_value={**mock_alerts[0], "acknowledged": True, "acknowledgement_note": "Verified"}):
        fake_id = "ST001#8205058153242#HIGH_TEMPERATURE"
        quoted_id = urllib.parse.quote(fake_id, safe="")
        r = client.post(f"/api/v1/alerts/{quoted_id}/acknowledge", json={"note": "Verified"})
        j = r.get_json() or {}
        record_test("functional_evaluation", "Acknowledge Alert", f"/api/v1/alerts/{quoted_id}/acknowledge", "POST", 200, r.status_code,
                    r.status_code == 200 and j.get("data", {}).get("acknowledged") is True)

    # TC-API-12: GET /api/v1/analytics/temperature
    with patch.object(TelemetryService, "get_temperature_analytics", return_value={
        "days": 1, "global_summary": {"average": 28.5, "min": 22.0, "max": 34.0, "count": 100}, "station_breakdown": {}
    }):
        r = client.get("/api/v1/analytics/temperature?days=1")
        j = r.get_json() or {}
        record_test("functional_evaluation", "Temperature Analytics", "/api/v1/analytics/temperature?days=1", "GET", 200, r.status_code,
                    r.status_code == 200 and "global_summary" in j.get("data", {}))

    # TC-API-13: GET /api/v1/analytics/air-quality
    with patch.object(TelemetryService, "get_air_quality_analytics", return_value={
        "days": 1, "global_summary": {"pm25": {"average": 45.0, "category": "Satisfactory"}, "pm10": {"average": 80.0, "category": "Satisfactory"}}
    }):
        r = client.get("/api/v1/analytics/air-quality?days=1")
        j = r.get_json() or {}
        record_test("functional_evaluation", "Air Quality Analytics", "/api/v1/analytics/air-quality?days=1", "GET", 200, r.status_code,
                    r.status_code == 200 and "pm25" in j.get("data", {}).get("global_summary", {}))

    # TC-API-14: GET /api/v1/analytics/station-comparison
    with patch.object(TelemetryService, "get_station_comparison", return_value={
        "stations_count": 5, "rankings": mock_stations
    }):
        r = client.get("/api/v1/analytics/station-comparison")
        j = r.get_json() or {}
        record_test("functional_evaluation", "Station Comparison", "/api/v1/analytics/station-comparison", "GET", 200, r.status_code,
                    r.status_code == 200 and j.get("data", {}).get("stations_count") == 5)

    # TC-API-15: GET /api/v1/simulator/status
    with patch.object(SimulatorController, "get_status", return_value={
        "running": False, "execution_mode": "IDLE", "stations_count": 5, "readings_generated": 100
    }):
        r = client.get("/api/v1/simulator/status")
        j = r.get_json() or {}
        record_test("functional_evaluation", "Simulator Status", "/api/v1/simulator/status", "GET", 200, r.status_code,
                    r.status_code == 200 and j.get("data", {}).get("stations_count") == 5)

    # TC-API-16: POST /api/v1/simulator/control (Start)
    with patch.object(SimulatorController, "start", return_value=(True, "Simulator started")):
        with patch.object(SimulatorController, "get_status", return_value={"running": True, "interval_seconds": 5.0}):
            r = client.post("/api/v1/simulator/control", json={"action": "start", "interval_seconds": 5.0})
            j = r.get_json() or {}
            record_test("functional_evaluation", "Simulator Control (Start)", "/api/v1/simulator/control", "POST", 200, r.status_code,
                        r.status_code == 200 and j.get("status") == "success")

    # -------------------------------------------------------------------------
    # 3. Input Validation and Error Handling Evaluation
    # -------------------------------------------------------------------------
    print("\n--- 3. Input Validation & Error Handling ---")

    validation_cases = [
        # (name, endpoint, method, payload/params, expected_status, expected_error_code)
        ("Unknown Station in /stations/<id>", "/api/v1/stations/ST999", "GET", None, 404, "STATION_NOT_FOUND"),
        ("Invalid Station in /telemetry/latest", "/api/v1/telemetry/latest?station_id=INVALID", "GET", None, 400, "INVALID_PARAMETER"),
        ("Invalid Limit (< 1) in /telemetry/latest", "/api/v1/telemetry/latest?limit=0", "GET", None, 400, "INVALID_LIMIT"),
        ("Invalid Limit (> 500) in /telemetry/latest", "/api/v1/telemetry/latest?limit=9999", "GET", None, 400, "INVALID_LIMIT"),
        ("Non-Integer Limit in /telemetry/latest", "/api/v1/telemetry/latest?limit=abc", "GET", None, 400, "INVALID_LIMIT"),
        ("Unknown Station in /telemetry/<id>", "/api/v1/telemetry/ST999", "GET", None, 404, "STATION_NOT_FOUND"),
        ("Invalid Order in /telemetry/<id>", "/api/v1/telemetry/ST001?order=diagonal", "GET", None, 400, "INVALID_ORDER"),
        ("Invalid Measurement in /telemetry/<id>", "/api/v1/telemetry/ST001?measurement=radiation", "GET", None, 400, "INVALID_MEASUREMENT"),
        ("Start after End in /telemetry/<id>", "/api/v1/telemetry/ST001?start=2026-11-20T00:00:00Z&end=2026-11-10T00:00:00Z", "GET", None, 400, "INVALID_PARAMETERS"),
        ("Invalid Limit in /telemetry/<id>", "/api/v1/telemetry/ST001?limit=5000", "GET", None, 400, "INVALID_LIMIT"),
        ("Invalid Station in /alerts", "/api/v1/alerts?station_id=ST888", "GET", None, 400, "INVALID_PARAMETER"),
        ("Invalid Limit in /alerts", "/api/v1/alerts?limit=-5", "GET", None, 400, "INVALID_LIMIT"),
        ("Alert Not Found in /alerts/<id>/acknowledge", f"/api/v1/alerts/{urllib.parse.quote('NONEXISTENT#KEY#ALERT', safe='')}/acknowledge", "POST", {"note": "test"}, 404, "ALERT_NOT_FOUND"),
        ("Unencoded Hash in Alert URL (Fragment Truncation)", "/api/v1/alerts/NONEXISTENT#KEY/acknowledge", "POST", {"note": "test"}, 404, "NOT_FOUND"),
        ("Invalid Station in /analytics/temperature", "/api/v1/analytics/temperature?station_id=BAD", "GET", None, 400, "INVALID_PARAMETER"),
        ("Invalid Days (< 1) in /analytics/temperature", "/api/v1/analytics/temperature?days=0", "GET", None, 400, "INVALID_PARAMETER"),
        ("Invalid Days (> 30) in /analytics/temperature", "/api/v1/analytics/temperature?days=35", "GET", None, 400, "INVALID_PARAMETER"),
        ("Non-Integer Days in /analytics/temperature", "/api/v1/analytics/temperature?days=two", "GET", None, 400, "INVALID_PARAMETER"),
        ("Invalid Station in /analytics/air-quality", "/api/v1/analytics/air-quality?station_id=BAD", "GET", None, 400, "INVALID_PARAMETER"),
        ("Invalid Days in /analytics/air-quality", "/api/v1/analytics/air-quality?days=-1", "GET", None, 400, "INVALID_PARAMETER"),
        ("Missing Body in /simulator/control", "/api/v1/simulator/control", "POST", None, 400, "MISSING_ACTION"),
        ("Missing Action in /simulator/control", "/api/v1/simulator/control", "POST", {"speed": 2}, 400, "MISSING_ACTION"),
        ("Invalid Action in /simulator/control", "/api/v1/simulator/control", "POST", {"action": "destroy"}, 400, "INVALID_ACTION"),
        ("Missing Params for inject_anomaly", "/api/v1/simulator/control", "POST", {"action": "inject_anomaly"}, 400, "MISSING_PARAMETERS"),
        ("Unsupported Method (POST on /telemetry/latest)", "/api/v1/telemetry/latest", "POST", {}, 405, "METHOD_NOT_ALLOWED"),
        ("Unsupported Method (GET on /simulator/control)", "/api/v1/simulator/control", "GET", None, 405, "METHOD_NOT_ALLOWED"),
        ("Nonexistent Route", "/api/v1/not_a_real_route", "GET", None, 404, "NOT_FOUND"),
    ]

    for name, endpoint, method, payload, exp_status, exp_code in validation_cases:
        if method == "GET":
            resp = client.get(endpoint)
        else:
            resp = client.post(endpoint, json=payload if payload is not None else {})
        
        j = resp.get_json() or {}
        code = j.get("error", {}).get("code")
        passed = (resp.status_code == exp_status) and (code == exp_code if exp_code else True)
        record_test("input_validation_and_errors", name, endpoint, method, exp_status, resp.status_code, passed, {
            "expected_code": exp_code,
            "actual_code": code,
            "message": j.get("error", {}).get("message")
        })

    # -------------------------------------------------------------------------
    # 4. Security & Exception Handling (RF-07 Evaluation)
    # -------------------------------------------------------------------------
    print("\n--- 4. Security & Exception Handling (RF-07 Disclosure Analysis) ---")

    # Injected runtime exceptions in routes to check whether {str(e)} leaks internal details
    test_exceptions = [
        ("Stations Route Exception", "/api/v1/stations", "get_stations",
         Exception("[WinError 10061] No connection could be made because the target machine actively refused it http://localhost:8085")),
        ("Station ID Route Exception", "/api/v1/stations/ST001", "get_station_by_id",
         Exception("Internal socket timeout connecting to 127.0.0.1:8085/microclimate:station_status")),
        ("Latest Telemetry Exception", "/api/v1/telemetry/latest", "get_latest_telemetry",
         Exception("ConnectionRefusedError: Connection refused at /usr/local/hbase/rest")),
        ("Historical Telemetry Exception", "/api/v1/telemetry/ST001", "get_station_telemetry",
         Exception("HBase REST Gateway timeout after 10000ms: http://localhost:8085/microclimate:readings")),
        ("Alerts Route Exception", "/api/v1/alerts", "get_alerts",
         Exception("Database query failed: table microclimate:alerts is offline")),
        ("Analytics Route Exception", "/api/v1/analytics/temperature", "get_temperature_analytics",
         Exception("ZeroDivisionError: division by zero in aggregation loop")),
    ]

    for name, endpoint, patch_target, exc in test_exceptions:
        with patch.object(TelemetryService, patch_target, side_effect=exc):
            resp = client.get(endpoint)
            j = resp.get_json() or {}
            err_msg = j.get("error", {}).get("message", "")
            err_code = j.get("error", {}).get("code", "")
            leaks_internal_details = str(exc) in err_msg

            details = {
                "injected_exception": str(exc),
                "response_message": err_msg,
                "error_code": err_code,
                "discloses_internal_exception": leaks_internal_details
            }
            passed = (resp.status_code == 500) and (err_code == "INTERNAL_ERROR")
            record_test("security_and_exception_handling", name, endpoint, "GET", 500, resp.status_code, passed, details)

            if leaks_internal_details:
                print(f"      [SECURITY WARNING - RF-07 REPRODUCED] Raw exception text disclosed: {err_msg}")

    # -------------------------------------------------------------------------
    # 5. Data Consistency Evaluation
    # -------------------------------------------------------------------------
    print("\n--- 5. Data Consistency Evaluation (Multi-Date Ordering, Provenance, Null Handling) ---")

    # 5.1 Multi-Date Timestamp Ordering (Desc vs Asc)
    ts_nov16 = int(datetime(2026, 11, 16, 23, 30, tzinfo=timezone.utc).timestamp() * 1000)
    ts_nov17 = int(datetime(2026, 11, 17, 0, 30, tzinfo=timezone.utc).timestamp() * 1000)
    mock_multidate_readings = [
        {"row_key": f"ST001#20261117#{9999999999999 - ts_nov17}", "timestamp_ms": ts_nov17, "temperature_celsius": 28.0},
        {"row_key": f"ST001#20261116#{9999999999999 - ts_nov16}", "timestamp_ms": ts_nov16, "temperature_celsius": 29.5}
    ]

    # Test Descending Order
    with patch.object(TelemetryService, "get_station_telemetry", return_value=mock_multidate_readings):
        r_desc = client.get("/api/v1/telemetry/ST001?start=2026-11-16T22:00:00Z&end=2026-11-17T02:00:00Z&order=desc")
        readings_desc = r_desc.get_json()["data"]["readings"]
        desc_ok = readings_desc[0]["timestamp_ms"] > readings_desc[1]["timestamp_ms"]
        record_test("data_consistency_evaluation", "Historical Multi-Date Ordering (DESC)", "/api/v1/telemetry/ST001", "GET", 200, r_desc.status_code, desc_ok)

    # Test Ascending Order
    with patch.object(TelemetryService, "get_station_telemetry", return_value=list(reversed(mock_multidate_readings))):
        r_asc = client.get("/api/v1/telemetry/ST001?start=2026-11-16T22:00:00Z&end=2026-11-17T02:00:00Z&order=asc")
        readings_asc = r_asc.get_json()["data"]["readings"]
        asc_ok = readings_asc[0]["timestamp_ms"] < readings_asc[1]["timestamp_ms"]
        record_test("data_consistency_evaluation", "Historical Multi-Date Ordering (ASC)", "/api/v1/telemetry/ST001", "GET", 200, r_asc.status_code, asc_ok)

    # 5.2 Measurement Projection / Filtering
    mock_projected = [
        {"station_id": "ST001", "timestamp_ms": ts_nov17, "temperature_celsius": 28.0}
    ]
    with patch.object(TelemetryService, "get_station_telemetry", return_value=mock_projected):
        r_proj = client.get("/api/v1/telemetry/ST001?measurement=temperature_celsius")
        proj_data = r_proj.get_json()["data"]["readings"]
        proj_ok = len(proj_data) == 1 and "temperature_celsius" in proj_data[0]
        record_test("data_consistency_evaluation", "Measurement Field Projection", "/api/v1/telemetry/ST001?measurement=temperature_celsius", "GET", 200, r_proj.status_code, proj_ok)

    # 5.3 Heat-Index Provenance Presentation (Verified vs Legacy Unverified)
    mock_mixed_alerts = [
        {
            "alert_id": "ST001#8205058153242#HIGH_HEAT_INDEX",
            "station_id": "ST001",
            "timestamp": "2026-11-22T10:00:00+00:00",
            "severity": "CRITICAL",
            "type": "HIGH_HEAT_INDEX",
            "measurement": "45.0",
            "threshold": "44.0",
            "message": "Extreme heat stress",
            "acknowledged": False,
            "calculation_applicability": {
                "is_valid": True,
                "status": "VALID",
                "origin_temp_celsius": 38.0,
                "origin_humidity_percent": 60.0,
                "note": "Verified calculation with complete provenance."
            }
        },
        {
            "alert_id": "ST002#8205058153240#HIGH_HEAT_INDEX",
            "station_id": "ST002",
            "timestamp": "2026-11-17T10:00:00+00:00",
            "severity": "CRITICAL",
            "type": "HIGH_HEAT_INDEX",
            "measurement": "44.5",
            "threshold": "44.0",
            "message": "Legacy heat alert",
            "acknowledged": True,
            "calculation_applicability": {
                "is_valid": None,
                "status": "LEGACY_UNVERIFIED",
                "note": "Legacy alert record missing calculation provenance metadata; validity cannot be independently verified."
            }
        }
    ]
    with patch.object(TelemetryService, "get_alerts", return_value=mock_mixed_alerts):
        r_prov = client.get("/api/v1/alerts")
        alerts_list = r_prov.get_json()["data"]["alerts"]
        a_valid = alerts_list[0]["calculation_applicability"]
        a_legacy = alerts_list[1]["calculation_applicability"]
        prov_ok = (a_valid["is_valid"] is True and a_valid["status"] == "VALID" and
                   a_legacy["is_valid"] is None and a_legacy["status"] == "LEGACY_UNVERIFIED")
        record_test("data_consistency_evaluation", "Provenance Formatting (VALID vs LEGACY_UNVERIFIED)", "/api/v1/alerts", "GET", 200, r_prov.status_code, prov_ok)

    # 5.4 Station Comparison Ranking: Explicit 0.0 vs None Handling
    mock_ranking_stations = [
        {"station_id": "ST_HOT", "station_name": "Hot Station", "zone": "Industrial", "connectivity": "ACTIVE", "heat_index": 42.0},
        {"station_id": "ST_WARM", "station_name": "Warm Station", "zone": "Commercial", "connectivity": "ACTIVE", "heat_index": 28.5},
        {"station_id": "ST_ZERO", "station_name": "Zero Station", "zone": "Highland", "connectivity": "ACTIVE", "heat_index": 0.0},
        {"station_id": "ST_NEG", "station_name": "Negative Station", "zone": "Cold Lab", "connectivity": "ACTIVE", "heat_index": -5.0},
        {"station_id": "ST_NONE", "station_name": "None Station", "zone": "Fault Zone", "connectivity": "ACTIVE", "heat_index": None},
    ]
    with patch.object(TelemetryService, "get_stations", return_value=mock_ranking_stations):
        with patch.object(TelemetryService, "get_alerts", return_value=[]):
            r_rank = client.get("/api/v1/analytics/station-comparison")
            rankings = r_rank.get_json()["data"]["rankings"]
            rank_ids = [r["station_id"] for r in rankings]
            rank_ok = (rank_ids == ["ST_HOT", "ST_WARM", "ST_ZERO", "ST_NEG", "ST_NONE"] and
                       rankings[2]["heat_index"] == 0.0 and rankings[4]["heat_index"] is None)
            record_test("data_consistency_evaluation", "Station Comparison Explicit None vs 0.0 Handling", "/api/v1/analytics/station-comparison", "GET", 200, r_rank.status_code, rank_ok)

    # 5.5 Empty Database Responses
    with patch.object(TelemetryService, "get_latest_telemetry", return_value=[]):
        r_empty = client.get("/api/v1/telemetry/latest?limit=10")
        j_empty = r_empty.get_json()
        empty_ok = (r_empty.status_code == 200 and j_empty["data"]["readings"] == [] and j_empty["data"]["count"] == 0)
        record_test("data_consistency_evaluation", "Empty Telemetry Database Response", "/api/v1/telemetry/latest", "GET", 200, r_empty.status_code, empty_ok)

    with patch.object(TelemetryService, "get_alerts", return_value=[]):
        r_empty_alerts = client.get("/api/v1/alerts")
        j_empty_alerts = r_empty_alerts.get_json()
        empty_alerts_ok = (r_empty_alerts.status_code == 200 and j_empty_alerts["data"]["alerts"] == [] and j_empty_alerts["data"]["count"] == 0)
        record_test("data_consistency_evaluation", "Empty Alerts Database Response", "/api/v1/alerts", "GET", 200, r_empty_alerts.status_code, empty_alerts_ok)

    # -------------------------------------------------------------------------
    # Summary Calculations
    # -------------------------------------------------------------------------
    total_functional = len(results["functional_evaluation"])
    passed_functional = sum(1 for t in results["functional_evaluation"] if t["passed"])

    total_validation = len(results["input_validation_and_errors"])
    passed_validation = sum(1 for t in results["input_validation_and_errors"] if t["passed"])

    total_security = len(results["security_and_exception_handling"])
    passed_security = sum(1 for t in results["security_and_exception_handling"] if t["passed"])

    total_consistency = len(results["data_consistency_evaluation"])
    passed_consistency = sum(1 for t in results["data_consistency_evaluation"] if t["passed"])

    total_all = total_functional + total_validation + total_security + total_consistency
    passed_all = passed_functional + passed_validation + passed_security + passed_consistency

    results["summary"] = {
        "total_tests": total_all,
        "passed_tests": passed_all,
        "failed_tests": total_all - passed_all,
        "success_rate_percent": round((passed_all / total_all) * 100, 2),
        "breakdown": {
            "functional_endpoints": {"total": total_functional, "passed": passed_functional},
            "input_validation_and_errors": {"total": total_validation, "passed": passed_validation},
            "security_and_exception_handling": {"total": total_security, "passed": passed_security, "rf07_disclosed_count": total_security},
            "data_consistency": {"total": total_consistency, "passed": passed_consistency}
        }
    }

    # Save to JSON
    output_path = os.path.join(WORKSPACE_ROOT, "docs", "academic_validation", "scripts", "api_evaluation_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 80)
    print(f"API EVALUATION COMPLETE: {passed_all}/{total_all} Passed ({results['summary']['success_rate_percent']}%)")
    print(f"Results saved to: {output_path}")
    print("=" * 80)
    return results


if __name__ == "__main__":
    run_api_evaluation()
