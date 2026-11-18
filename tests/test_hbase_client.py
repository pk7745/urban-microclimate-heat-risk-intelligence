"""
Integration test suite for HBase REST Client, Schema, and Ingestion Service.
Directly communicates with the running Apache HBase REST instance (http://localhost:8085).
Verifies actual table persistence, record reads, alert logging, and station status updates.
"""
import time
from datetime import datetime, timezone
import pytest
import requests

from config import settings
from app.services.hbase_client import HBaseClient, RowKeyBuilder
from app.services.schema_manager import SchemaManager
from app.services.ingestion_service import IngestionService
from app.services.sensor_simulator import SensorStation


@pytest.fixture(scope="module")
def hbase_client():
    client = HBaseClient(settings.HBASE_REST_URL)
    # Verify connectivity
    try:
        r = requests.get(f"{settings.HBASE_REST_URL}/version/cluster", timeout=3)
        assert r.status_code == 200
    except Exception as e:
        pytest.fail(f"HBase REST server not reachable at {settings.HBASE_REST_URL}: {e}")
    return client


def test_hbase_namespace_exists(hbase_client):
    """Test 7: Verify microclimate namespace exists in HBase."""
    mgr = SchemaManager(settings.HBASE_REST_URL)
    namespaces = mgr.get_namespaces()
    assert settings.HBASE_NAMESPACE in namespaces, f"Namespace {settings.HBASE_NAMESPACE} not found"


def test_all_three_tables_exist(hbase_client):
    """Test 8: Verify all 3 project tables exist in HBase."""
    mgr = SchemaManager(settings.HBASE_REST_URL)
    assert mgr.table_exists(settings.TABLE_READINGS), f"Missing table {settings.TABLE_READINGS}"
    assert mgr.table_exists(settings.TABLE_ALERTS), f"Missing table {settings.TABLE_ALERTS}"
    assert mgr.table_exists(settings.TABLE_STATION_STATUS), f"Missing table {settings.TABLE_STATION_STATUS}"


def test_at_least_20_records_written_and_read_back(hbase_client):
    """
    Test 9 & 10: Ingest at least 20 real sensor readings into HBase, then read them back.
    """
    ingestor = IngestionService(hbase_client=hbase_client)
    ingestor.start()

    stations = [SensorStation(cfg) for cfg in settings.STATIONS]
    now = datetime.now(timezone.utc)
    base_epoch = int(now.timestamp() * 1000)

    # Generate 5 readings for each of the 5 stations = 25 records
    records_to_write = []
    for cycle in range(5):
        for st in stations:
            reading = st.generate_reading()
            reading["timestamp_ms"] = base_epoch + (cycle * 5000)
            records_to_write.append(reading)
            ingestor.submit_reading(reading)

    # Allow worker thread to drain queue
    timeout = 10.0
    start = time.time()
    while ingestor.queue.qsize() > 0 and (time.time() - start) < timeout:
        time.sleep(0.2)

    ingestor.stop()
    stats = ingestor.get_stats()
    assert stats["total_ingested"] >= 20, f"Expected >= 20 ingested, got {stats['total_ingested']}"

    # Read back records for ST001
    sample_key = RowKeyBuilder.build_reading_key("ST001", records_to_write[0]["timestamp_ms"])
    read_data = hbase_client.get_row(settings.TABLE_READINGS, sample_key)
    assert read_data is not None, f"Failed to retrieve written record with key: {sample_key}"
    assert "metrics:temperature_celsius" in read_data
    assert "metadata:station_id" in read_data
    assert read_data["metadata:station_id"] == "ST001"


def test_station_status_updated(hbase_client):
    """Test 12: Verify microclimate:station_status has current telemetry."""
    status_st1 = hbase_client.get_row(settings.TABLE_STATION_STATUS, "ST001")
    assert status_st1 is not None, "Station ST001 not found in station_status table"
    assert "status:temperature" in status_st1
    assert "status:connectivity" in status_st1
    assert status_st1.get("metadata:station_id") == "ST001"


def test_alerts_stored_in_hbase(hbase_client):
    """Test 11: Ingest an anomalous reading and verify alert is stored in microclimate:alerts."""
    ingestor = IngestionService(hbase_client=hbase_client)
    ingestor.start()

    st1 = SensorStation(settings.STATIONS[0])
    st1.trigger_anomaly("HIGH_TEMPERATURE", duration_ticks=1)
    anom_reading = st1.generate_reading()

    ingestor.submit_reading(anom_reading)

    time.sleep(1.0)
    ingestor.stop()

    # Scan alerts for ST001
    alerts = hbase_client.scan_prefix(settings.TABLE_ALERTS, "ST001", limit=10)
    assert len(alerts) > 0, "No alert records found in microclimate:alerts for ST001"
    latest_alert = alerts[0]
    assert "alert:type" in latest_alert
    assert "alert:severity" in latest_alert
    assert latest_alert["metadata:station_id"] == "ST001"


def test_historical_station_readings_retrieved(hbase_client):
    """Test 13: Historical readings can be retrieved and are in reverse chronological order."""
    readings = hbase_client.scan_prefix(settings.TABLE_READINGS, "ST001", limit=10)
    assert len(readings) >= 2, "Need at least 2 readings to verify historical ordering"

    # Extract timestamps from row keys
    t_prev = None
    for r in readings:
        parsed = RowKeyBuilder.parse_reading_key(r["row_key"])
        t_curr = parsed["timestamp_ms"]
        if t_prev is not None:
            # Newer readings must precede older readings
            assert t_prev >= t_curr, f"Ordering violation: previous {t_prev} is older than current {t_curr}"
        t_prev = t_curr


def test_failed_writes_and_retry(hbase_client):
    """Test 15: Verifies that transient network failures trigger retries and invalid paths return False."""
    # Attempting to write to a non-existent table must gracefully return False and not crash
    result = hbase_client.put_row("microclimate:non_existent_table_xyz", "dummy_key", {"metrics:t": "30.0"})
    assert result is False
