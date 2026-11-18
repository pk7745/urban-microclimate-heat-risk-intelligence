"""
Comprehensive Failure Scenarios and Error Recovery Tests (Phase 5 Part 4).
Tests 10 explicit failure scenarios in isolation without corrupting persistent data:
1. HBase REST gateway unavailable.
2. Invalid sensor reading.
3. Ingestion queue full.
4. HBase write timeout.
5. Malformed API parameters.
6. Empty historical query result.
7. Missing heat-index value.
8. Simulator already running.
9. Simulator already stopped.
10. Invalid simulator control request.
"""
import pytest
import queue
from unittest.mock import MagicMock, patch
import requests

from app import create_app
from app.services.hbase_client import HBaseClient
from app.services.ingestion_service import IngestionService
from app.services.anomaly_detector import AnomalyDetector
from app.services.sensor_simulator import assess_heat_index, calculate_heat_index
from app.services.simulator_service import SimulatorController


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


# 1. HBase REST gateway unavailable
def test_scenario_1_hbase_gateway_unavailable(client, monkeypatch):
    from app.services.telemetry_service import TelemetryService
    monkeypatch.setattr(TelemetryService, "check_health",
                        lambda self, simulator_running=False: (
                            {"app_status": "DEGRADED", "hbase_connected": False, "tables": {}}, 503
                        ))
    resp = client.get("/api/v1/health")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "SERVICE_UNAVAILABLE"


# 2. Invalid sensor reading
def test_scenario_2_invalid_sensor_reading():
    detector = AnomalyDetector()
    invalid_reading = {
        "station_id": "ST001",
        "station_name": "Bengaluru Central",
        "timestamp": "2026-11-18T00:00:00Z",
        "timestamp_ms": 1794941200000,
        "temperature_celsius": -999.0,
        "humidity_percent": -5.0,
        "pm25": -10.0,
        "pm10": 99999.0,
        "atmospheric_pressure_hpa": 0.0,
        "sensor_status": "ERROR"
    }
    alerts = detector.analyze_reading(invalid_reading)
    types = [a["alert_type"] for a in alerts]
    assert "INVALID_READING" in types


# 3. Queue full
def test_scenario_3_queue_full():
    mock_hbase = MagicMock()
    # Queue with maxsize 1
    ingestor = IngestionService(hbase_client=mock_hbase, queue_maxsize=1)
    reading1 = {"station_id": "ST001", "timestamp_ms": 1000}
    reading2 = {"station_id": "ST002", "timestamp_ms": 2000}

    assert ingestor.submit_reading(reading1) is True
    # Queue is now saturated; submit_reading must return False without crashing
    assert ingestor.submit_reading(reading2) is False
    stats = ingestor.get_stats()
    assert stats["dropped_due_to_queue_full"] == 1


# 4. HBase write timeout
def test_scenario_4_hbase_write_timeout(monkeypatch):
    client = HBaseClient("http://localhost:8085", timeout=1)
    def mock_put(*args, **kwargs):
        raise requests.exceptions.Timeout("Connection timed out")
    monkeypatch.setattr(client.session, "put", mock_put)

    result = client.put_row("microclimate:readings", "TEST_KEY", {"metrics:temperature_celsius": "30.0"})
    assert result is False


# 5. Malformed API parameters
def test_scenario_5_malformed_api_parameters(client):
    r1 = client.get("/api/v1/telemetry/ST001?order=sideways")
    assert r1.status_code == 400
    assert r1.get_json()["error"]["code"] == "INVALID_ORDER"

    r2 = client.get("/api/v1/alerts?severity=SUPER_CRITICAL")
    assert r2.status_code == 400
    assert r2.get_json()["error"]["code"] == "INVALID_PARAMETER"


# 6. Empty historical query result
def test_scenario_6_empty_historical_query(client, monkeypatch):
    from app.services.telemetry_service import TelemetryService
    monkeypatch.setattr(TelemetryService, "get_station_telemetry", lambda *args, **kwargs: [])
    resp = client.get("/api/v1/telemetry/ST001?start=2026-01-01T00:00:00Z&end=2026-01-02T00:00:00Z")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["data"]["readings"] == []
    assert data["data"]["count"] == 0


# 7. Missing heat-index value
def test_scenario_7_missing_heat_index_value():
    res1 = assess_heat_index(None, 60.0)
    assert res1["heat_index_celsius"] is None
    assert res1["is_valid"] is False
    assert res1["status"] == "MISSING_INPUT"

    res2 = assess_heat_index(28.0, None)
    assert res2["heat_index_celsius"] is None
    assert res2["is_valid"] is False
    assert res2["status"] == "MISSING_INPUT"


# 8. Simulator already running
def test_scenario_8_simulator_already_running():
    controller = SimulatorController()
    # Mock simulator running state
    mock_sim = MagicMock()
    mock_sim.is_running.return_value = True
    controller._simulator = mock_sim

    success, msg = controller.start()
    assert success is False
    assert "already running" in msg
    controller._simulator = None


# 9. Simulator already stopped
def test_scenario_9_simulator_already_stopped():
    controller = SimulatorController()
    controller._simulator = None
    controller._ingestor = None

    success, msg = controller.stop()
    assert success is False
    assert "not currently running" in msg


# 10. Invalid simulator control request
def test_scenario_10_invalid_simulator_control(client):
    r1 = client.post("/api/v1/simulator/control", json={})
    assert r1.status_code == 400
    assert r1.get_json()["error"]["code"] == "MISSING_ACTION"

    r2 = client.post("/api/v1/simulator/control", json={"action": "reboot_galaxy"})
    assert r2.status_code == 400
    assert r2.get_json()["error"]["code"] == "INVALID_ACTION"
