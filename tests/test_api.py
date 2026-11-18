"""
Comprehensive Test Suite for Urban Microclimate Flask REST API.
Includes unit tests with mocked backends and non-mutating live HBase integration tests.
Covers all 16 Phase 3.8 test requirements.
"""
from datetime import datetime, timezone, timedelta
import pytest
from flask.testing import FlaskClient

from app import create_app
from config import settings
from app.services.hbase_client import RowKeyBuilder
from app.services.telemetry_service import TelemetryService


@pytest.fixture
def app():
    """Creates a fresh test application instance."""
    app_instance = create_app({"TESTING": True})
    return app_instance


@pytest.fixture
def client(app) -> FlaskClient:
    """Provides a test client for simulating HTTP requests."""
    return app.test_client()


# =============================================================================
# 1. Application Startup & Info
# =============================================================================
def test_flask_app_startup(client):
    """Test 1: Verify application starts and returns root service metadata."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "service" in data
    assert "version" in data
    assert data["database"] == "Apache HBase 2.6.7 (REST)"


# =============================================================================
# 2. Health Endpoint
# =============================================================================
def test_health_endpoint_operational(client):
    """Test 2: Verify GET /api/v1/health returns operational status on running cluster."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["app_status"] == "UP"
    assert data["hbase_connected"] is True
    assert data["hbase_version"] is not None
    assert data["tables"][settings.TABLE_READINGS] is True
    assert data["tables"][settings.TABLE_ALERTS] is True
    assert data["tables"][settings.TABLE_STATION_STATUS] is True


def test_health_endpoint_hbase_unavailable(client, monkeypatch):
    """Test 15: Verify GET /api/v1/health reports degraded status (503) when HBase is down."""
    from app.services import telemetry_service

    def mock_check_health(self, simulator_running=False):
        return {
            "app_status": "DEGRADED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hbase_connected": False,
            "hbase_version": None,
            "tables": {t: False for t in settings.TABLE_READINGS},
            "simulator_running": False
        }, 503

    monkeypatch.setattr(TelemetryService, "check_health", mock_check_health)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"


# =============================================================================
# 3. Stations Listing & Lookup
# =============================================================================
def test_station_listing(client):
    """Test 3: Verify GET /api/v1/stations lists all 5 configured stations."""
    resp = client.get("/api/v1/stations")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    stations = body["data"]["stations"]
    assert len(stations) == 5
    station_ids = [s["station_id"] for s in stations]
    assert "ST001" in station_ids
    assert "ST005" in station_ids
    # Verify presence of telemetry metrics
    st1 = next(s for s in stations if s["station_id"] == "ST001")
    assert "station_name" in st1
    assert "connectivity" in st1
    assert "temperature" in st1
    assert "heat_index" in st1


def test_individual_station_lookup(client):
    """Test 4: Verify GET /api/v1/stations/<station_id> returns detailed station info."""
    resp = client.get("/api/v1/stations/ST001")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["station_id"] == "ST001"
    assert data["station_name"] == "Bengaluru Central"
    assert "status" in data
    assert "latest_reading" in data
    assert "recent_alerts" in data


def test_unknown_station_lookup(client):
    """Test 5: Verify GET /api/v1/stations/<unknown_id> returns HTTP 404."""
    resp = client.get("/api/v1/stations/ST999")
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "STATION_NOT_FOUND"


# =============================================================================
# 4. Telemetry Retrieval & Multi-Date Partitioning
# =============================================================================
def test_latest_telemetry_retrieval(client):
    """Test 6: Verify GET /api/v1/telemetry/latest returns records sorted newest-first."""
    resp = client.get("/api/v1/telemetry/latest?limit=10")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    readings = body["data"]["readings"]
    assert len(readings) > 0
    # Verify global descending timestamp order
    t_prev = None
    for r in readings:
        t_curr = r["timestamp_ms"]
        if t_prev is not None:
            assert t_prev >= t_curr, f"Ordering violation: previous {t_prev} is older than {t_curr}"
        t_prev = t_curr


def test_historical_telemetry_multi_date_partitioning(client, monkeypatch):
    """
    Test 7: Verify that historical telemetry correctly scans and merges multiple UTC date partitions.
    Simulates records across 2 consecutive UTC dates (20261116 and 20261117).
    """
    # Create synthetic records spanning 2 dates
    ts1 = int(datetime(2026, 11, 16, 23, 30, tzinfo=timezone.utc).timestamp() * 1000)
    ts2 = int(datetime(2026, 11, 17, 0, 30, tzinfo=timezone.utc).timestamp() * 1000)

    key1 = RowKeyBuilder.build_reading_key("ST001", ts1)
    key2 = RowKeyBuilder.build_reading_key("ST001", ts2)

    def mock_scan_prefix(self, table, prefix, limit=1000):
        if "20261116" in prefix:
            return [{
                "row_key": key1,
                "metrics:temperature_celsius": "29.5",
                "metadata:timestamp": "2026-11-16T23:30:00+00:00"
            }]
        elif "20261117" in prefix:
            return [{
                "row_key": key2,
                "metrics:temperature_celsius": "28.0",
                "metadata:timestamp": "2026-11-17T00:30:00+00:00"
            }]
        return []

    from app.services.hbase_client import HBaseClient
    monkeypatch.setattr(HBaseClient, "scan_prefix", mock_scan_prefix)

    # Query across the 2-day window
    resp = client.get("/api/v1/telemetry/ST001?start=2026-11-16T22:00:00Z&end=2026-11-17T02:00:00Z&order=desc")
    assert resp.status_code == 200
    body = resp.get_json()
    readings = body["data"]["readings"]
    assert len(readings) == 2
    # Newest record (Nov 17) must be first in desc order
    assert readings[0]["timestamp_ms"] == ts2
    assert readings[1]["timestamp_ms"] == ts1


def test_historical_ordering_desc_and_asc(client):
    """Test 8: Verify ascending and descending sorting on historical queries."""
    # Descending
    resp_desc = client.get("/api/v1/telemetry/ST001?limit=10&order=desc")
    assert resp_desc.status_code == 200
    readings_desc = resp_desc.get_json()["data"]["readings"]
    if len(readings_desc) >= 2:
        assert readings_desc[0]["timestamp_ms"] >= readings_desc[-1]["timestamp_ms"]

    # Ascending
    resp_asc = client.get("/api/v1/telemetry/ST001?limit=10&order=asc")
    assert resp_asc.status_code == 200
    readings_asc = resp_asc.get_json()["data"]["readings"]
    if len(readings_asc) >= 2:
        assert readings_asc[0]["timestamp_ms"] <= readings_asc[-1]["timestamp_ms"]


def test_filtering_by_measurement(client):
    """Test 9: Verify filtering by specific measurement returns projected field."""
    resp = client.get("/api/v1/telemetry/ST001?measurement=temperature_celsius&limit=5")
    assert resp.status_code == 200
    readings = resp.get_json()["data"]["readings"]
    for r in readings:
        assert r["temperature_celsius"] is not None


# =============================================================================
# 5. Alerts Retrieval & Acknowledgement
# =============================================================================
def test_alert_retrieval_and_filtering(client):
    """Test 10: Verify alert retrieval and filtering by severity."""
    resp = client.get("/api/v1/alerts?limit=10")
    assert resp.status_code == 200
    body = resp.get_json()
    alerts = body["data"]["alerts"]
    assert len(alerts) > 0
    # Test severity filtering
    resp_crit = client.get("/api/v1/alerts?severity=CRITICAL&limit=10")
    assert resp_crit.status_code == 200
    crit_alerts = resp_crit.get_json()["data"]["alerts"]
    for a in crit_alerts:
        assert a["severity"] == "CRITICAL"


def test_alert_acknowledgement(client, monkeypatch):
    """Test 11: Verify POST /api/v1/alerts/<alert_id>/acknowledge updates acknowledgement."""
    import urllib.parse
    fake_alert_key = "ST001#8205058153242#HIGH_TEMPERATURE"

    def mock_get_row(self, table, row_key):
        if row_key == fake_alert_key:
            return {
                "metadata:station_id": "ST001",
                "alert:type": "HIGH_TEMPERATURE",
                "alert:severity": "CRITICAL",
                "alert:measurement": "45.0",
                "alert:threshold": "40.0",
                "alert:message": "Extreme heat alert",
                "metadata:acknowledged": "false"
            }
        return None

    def mock_put_row(self, table, row_key, columns):
        return True

    from app.services.hbase_client import HBaseClient
    monkeypatch.setattr(HBaseClient, "get_row", mock_get_row)
    monkeypatch.setattr(HBaseClient, "put_row", mock_put_row)

    quoted_key = urllib.parse.quote(fake_alert_key, safe="")
    resp = client.post(f"/api/v1/alerts/{quoted_key}/acknowledge", json={"note": "Verified by operator"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert "acknowledged successfully" in body["message"]


# =============================================================================
# 6. Analytics Calculations
# =============================================================================
def test_analytics_calculations(client):
    """Test 12: Verify statistical calculations (avg, min, max, count) on analytics endpoints."""
    # Temperature analytics
    resp_temp = client.get("/api/v1/analytics/temperature?days=1")
    assert resp_temp.status_code == 200
    temp_data = resp_temp.get_json()["data"]
    assert "global_summary" in temp_data
    assert "station_breakdown" in temp_data
    summary = temp_data["global_summary"]
    if summary["count"] > 0:
        assert summary["min"] <= summary["average"] <= summary["max"]

    # Air quality analytics
    resp_aq = client.get("/api/v1/analytics/air-quality?days=1")
    assert resp_aq.status_code == 200
    aq_data = resp_aq.get_json()["data"]
    assert "global_summary" in aq_data
    assert "pm25" in aq_data["global_summary"]
    assert "pm10" in aq_data["global_summary"]

    # Station comparison
    resp_comp = client.get("/api/v1/analytics/station-comparison")
    assert resp_comp.status_code == 200
    comp_data = resp_comp.get_json()["data"]
    assert comp_data["stations_count"] == 5
    assert len(comp_data["rankings"]) == 5
    # Verify rankings sorted by heat index descending with explicit None handling
    rankings = comp_data["rankings"]
    score = lambda r: r["heat_index"] if r.get("heat_index") is not None else float("-inf")
    for i in range(len(rankings) - 1):
        assert score(rankings[i]) >= score(rankings[i + 1])


def test_station_comparison_ranking_explicit_none_handling(client, monkeypatch):
    """
    Verify that station comparison ranking strictly preserves 0.0°C as a valid number
    and sorts None (missing/invalid NWS data) to the bottom of descending rankings.
    """
    from app.services.telemetry_service import TelemetryService

    mock_stations = [
        {"station_id": "ST_NEG", "station_name": "Subzero Station", "zone": "Cold Lab", "connectivity": "ONLINE", "heat_index": -5.0, "temperature": -5.0, "humidity": 80.0, "pm25": 10.0, "pm10": 20.0},
        {"station_id": "ST_NONE", "station_name": "Missing HI Station", "zone": "Sensor Fault", "connectivity": "ONLINE", "heat_index": None, "temperature": 30.0, "humidity": 20.0, "pm25": 15.0, "pm10": 25.0},
        {"station_id": "ST_HOT", "station_name": "Hot Station", "zone": "Industrial", "connectivity": "ONLINE", "heat_index": 42.0, "temperature": 35.0, "humidity": 65.0, "pm25": 45.0, "pm10": 80.0},
        {"station_id": "ST_ZERO", "station_name": "Freezing Zero Station", "zone": "Highland", "connectivity": "ONLINE", "heat_index": 0.0, "temperature": 0.0, "humidity": 75.0, "pm25": 12.0, "pm10": 22.0},
        {"station_id": "ST_WARM", "station_name": "Warm Station", "zone": "Residential", "connectivity": "ONLINE", "heat_index": 28.5, "temperature": 27.0, "humidity": 55.0, "pm25": 20.0, "pm10": 35.0},
    ]

    monkeypatch.setattr(TelemetryService, "get_stations", lambda self: mock_stations)
    monkeypatch.setattr(TelemetryService, "get_alerts", lambda self, **kwargs: [])

    resp = client.get("/api/v1/analytics/station-comparison")
    assert resp.status_code == 200
    rankings = resp.get_json()["data"]["rankings"]

    expected_order = ["ST_HOT", "ST_WARM", "ST_ZERO", "ST_NEG", "ST_NONE"]
    actual_order = [r["station_id"] for r in rankings]
    assert actual_order == expected_order

    # Explicit check: ST_ZERO (0.0) ranks above ST_NEG (-5.0), ST_NONE (None) is at the end
    assert rankings[2]["station_id"] == "ST_ZERO"
    assert rankings[2]["heat_index"] == 0.0
    assert rankings[3]["station_id"] == "ST_NEG"
    assert rankings[3]["heat_index"] == -5.0
    assert rankings[4]["station_id"] == "ST_NONE"
    assert rankings[4]["heat_index"] is None


# =============================================================================
# 7. Parameter Validation & Edge Cases
# =============================================================================
def test_invalid_parameters(client):
    """Test 13 & 14: Verify handling of invalid timestamps, order, limits, and station IDs."""
    # Invalid limit (< 1)
    r1 = client.get("/api/v1/telemetry/latest?limit=0")
    assert r1.status_code == 400
    assert r1.get_json()["error"]["code"] == "INVALID_LIMIT"

    # Non-integer limit
    r2 = client.get("/api/v1/telemetry/latest?limit=abc")
    assert r2.status_code == 400

    # Invalid order
    r3 = client.get("/api/v1/telemetry/ST001?order=invalid_order")
    assert r3.status_code == 400
    assert r3.get_json()["error"]["code"] == "INVALID_ORDER"

    # Invalid measurement
    r4 = client.get("/api/v1/telemetry/ST001?measurement=non_existent_metric")
    assert r4.status_code == 400
    assert r4.get_json()["error"]["code"] == "INVALID_MEASUREMENT"

    # Start after End timestamp
    r5 = client.get("/api/v1/telemetry/ST001?start=2026-11-18T10:00:00Z&end=2026-11-17T10:00:00Z")
    assert r5.status_code == 400
    assert "must be before end" in r5.get_json()["error"]["message"]


def test_empty_database_responses(client, monkeypatch):
    """Test 16: Verify graceful handling and valid JSON structures on empty database results."""
    from app.services.hbase_client import HBaseClient

    def mock_scan_prefix(self, table, prefix, limit=50):
        return []

    monkeypatch.setattr(HBaseClient, "scan_prefix", mock_scan_prefix)

    # Empty telemetry
    resp = client.get("/api/v1/telemetry/latest?limit=10")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["readings"] == []
    assert body["data"]["count"] == 0

    # Empty alerts
    resp_alerts = client.get("/api/v1/alerts")
    assert resp_alerts.status_code == 200
    assert resp_alerts.get_json()["data"]["alerts"] == []


# =============================================================================
# 8. Simulator Control Endpoints
# =============================================================================
def test_simulator_status_and_control_validation(client):
    """Verify GET /api/v1/simulator/status and validation on POST /api/v1/simulator/control."""
    # Status check
    resp = client.get("/api/v1/simulator/status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "running" in data
    assert "stations_count" in data
    assert data["stations_count"] == 5

    # Missing action in control
    r_bad = client.post("/api/v1/simulator/control", json={})
    assert r_bad.status_code == 400
    assert r_bad.get_json()["error"]["code"] == "MISSING_ACTION"

    # Invalid action
    r_invalid = client.post("/api/v1/simulator/control", json={"action": "explode"})
    assert r_invalid.status_code == 400
    assert r_invalid.get_json()["error"]["code"] == "INVALID_ACTION"
