"""
Phase 5.1 — Controlled Live End-to-End Ingestion Verification Script.
Safely proves that a newly generated sensor observation travels through:
Sensor Simulator -> Bounded Ingestion Queue -> Ingestion Worker -> HBase REST Gateway -> Apache HBase -> Flask REST API.
"""
import time
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
from datetime import datetime, timezone

from config import settings
from app.services.hbase_client import HBaseClient, RowKeyBuilder
from app.services.ingestion_service import IngestionService
from app.services.sensor_simulator import SensorStation
from app.services.simulator_service import SimulatorController


def run_live_ingestion_verification():
    print("=" * 60)
    print(" PHASE 5.1: LIVE INGESTION VERIFICATION PIPELINE TEST")
    print("=" * 60)

    # 1. Preflight safety checks
    hbase_client = HBaseClient(settings.HBASE_REST_URL)
    sim_status = SimulatorController().get_status()
    if sim_status.get("running"):
        raise RuntimeError("Safety check failed: Simulator is currently RUNNING. Must be STOPPED.")

    flask_resp = requests.get("http://localhost:5000/api/v1/health", timeout=10)
    if flask_resp.status_code != 200:
        raise RuntimeError(f"Safety check failed: Flask health returned {flask_resp.status_code}")

    # Record pre-ingestion counts
    pre_readings = hbase_client.scan_prefix(settings.TABLE_READINGS, "", limit=2000)
    pre_alerts = hbase_client.scan_prefix(settings.TABLE_ALERTS, "", limit=2000)
    pre_status = hbase_client.scan_prefix(settings.TABLE_STATION_STATUS, "", limit=2000)

    count_readings_before = len(pre_readings)
    count_alerts_before = len(pre_alerts)
    count_status_before = len(pre_status)

    print(f"PRE-TEST COUNTS: readings={count_readings_before}, alerts={count_alerts_before}, status={count_status_before}")
    print(f"Simulator State: {sim_status['execution_mode']} (running={sim_status['running']})")
    print(f"Flask API Health: HTTP {flask_resp.status_code} ({flask_resp.json().get('status')})")

    # 2. Generate a valid synthetic observation using existing simulation functions
    station = SensorStation(settings.STATIONS[0])  # ST001: Bengaluru Central
    test_reading = station.generate_reading()

    # Stamp provenance metadata explicitly
    test_reading["data_source"] = "SIMULATED_TEST_VERIFICATION"
    test_reading["sensor_status"] = "ACTIVE"

    expected_row_key = RowKeyBuilder.build_reading_key(
        test_reading["station_id"],
        test_reading["timestamp_ms"]
    )
    print(f"\nGENERATED OBSERVATION:")
    print(f"  Station ID:     {test_reading['station_id']}")
    print(f"  Station Name:   {test_reading['station_name']}")
    print(f"  Timestamp UTC:  {test_reading['timestamp']}")
    print(f"  Timestamp ms:   {test_reading['timestamp_ms']}")
    print(f"  Temperature:    {test_reading['temperature_celsius']} °C")
    print(f"  Humidity:       {test_reading['humidity_percent']} %")
    print(f"  Heat Index:     {test_reading['heat_index_celsius']} °C (valid={test_reading['heat_index_is_valid']})")
    print(f"  Data Source:    {test_reading['data_source']}")
    print(f"  Target Row Key: {expected_row_key}")

    # 3. Submit through the actual ingestion service and bounded queue
    print("\n[INGESTION] Initializing IngestionService and worker thread...")
    ingestor = IngestionService(hbase_client=hbase_client)
    ingestor.start()

    print("[INGESTION] Submitting observation to bounded queue...")
    submitted = ingestor.submit_reading(test_reading)
    if not submitted:
        ingestor.stop()
        raise RuntimeError("Failed to submit observation to ingestion queue!")

    # Wait for queue to drain
    start_wait = time.time()
    while ingestor.queue.qsize() > 0 and (time.time() - start_wait) < 5.0:
        time.sleep(0.1)

    # Allow slight buffer for thread write completion
    time.sleep(0.5)
    ingestor.stop(timeout=3.0)

    stats = ingestor.get_stats()
    print(f"[INGESTION] Worker stopped. Ingestion stats: {stats}")
    if stats["total_ingested"] != 1:
        raise RuntimeError(f"Ingestion worker failed to ingest record! Stats: {stats}")

    # 4. Direct HBase persistence verification
    print("\n[HBASE VERIFICATION] Querying Apache HBase for exact test row key...")
    stored_hbase_row = hbase_client.get_row(settings.TABLE_READINGS, expected_row_key)
    if not stored_hbase_row:
        raise AssertionError(f"Record NOT found in HBase table '{settings.TABLE_READINGS}' for key: {expected_row_key}")

    print(f"[HBASE VERIFICATION] Record successfully retrieved from Apache HBase!")
    print(f"  Stored station_id:   {stored_hbase_row.get('metadata:station_id')}")
    print(f"  Stored data_source:  {stored_hbase_row.get('metadata:data_source')}")
    print(f"  Stored temperature:  {stored_hbase_row.get('metrics:temperature_celsius')} °C")
    print(f"  Stored humidity:     {stored_hbase_row.get('metrics:humidity_percent')} %")
    print(f"  Stored heat_index:   {stored_hbase_row.get('metrics:heat_index_celsius')} °C")

    # Value comparison
    assert stored_hbase_row.get("metadata:station_id") == test_reading["station_id"]
    assert stored_hbase_row.get("metadata:data_source") == "SIMULATED_TEST_VERIFICATION"
    assert float(stored_hbase_row.get("metrics:temperature_celsius")) == test_reading["temperature_celsius"]
    assert float(stored_hbase_row.get("metrics:humidity_percent")) == test_reading["humidity_percent"]

    # 5. Flask REST API retrieval verification
    print("\n[API VERIFICATION] Querying Flask REST API (GET /api/v1/telemetry/ST001?limit=1)...")
    api_url = "http://localhost:5000/api/v1/telemetry/ST001?limit=1"
    api_resp = requests.get(api_url, timeout=10)
    assert api_resp.status_code == 200, f"Flask API returned status {api_resp.status_code}: {api_resp.text}"

    api_data = api_resp.json()
    readings_list = api_data.get("data", {}).get("readings", [])
    assert len(readings_list) > 0, "Flask API returned empty readings list!"

    latest_api_reading = readings_list[0]
    print(f"[API VERIFICATION] Retrieved latest telemetry record via Flask API:")
    print(f"  API row_key:         {latest_api_reading.get('row_key')}")
    print(f"  API station_id:      {latest_api_reading.get('station_id')}")
    print(f"  API data_source:     {latest_api_reading.get('data_source')}")
    print(f"  API temperature:     {latest_api_reading.get('temperature_celsius')} °C")
    print(f"  API heat_index:      {latest_api_reading.get('heat_index_celsius')} °C")

    assert latest_api_reading.get("row_key") == expected_row_key
    assert latest_api_reading.get("data_source") == "SIMULATED_TEST_VERIFICATION"
    assert latest_api_reading.get("temperature_celsius") == test_reading["temperature_celsius"]

    # 6. Post-verification integrity check
    print("\n[FINAL INTEGRITY] Checking post-ingestion HBase row counts...")
    post_readings = hbase_client.scan_prefix(settings.TABLE_READINGS, "", limit=2000)
    post_alerts = hbase_client.scan_prefix(settings.TABLE_ALERTS, "", limit=2000)
    post_status = hbase_client.scan_prefix(settings.TABLE_STATION_STATUS, "", limit=2000)

    count_readings_after = len(post_readings)
    count_alerts_after = len(post_alerts)
    count_status_after = len(post_status)

    delta_readings = count_readings_after - count_readings_before
    delta_alerts = count_alerts_after - count_alerts_before
    delta_status = count_status_after - count_status_before

    print(f"POST-TEST COUNTS: readings={count_readings_after} (delta={delta_readings}), alerts={count_alerts_after} (delta={delta_alerts}), status={count_status_after} (delta={delta_status})")

    assert delta_readings == 1, f"Expected exactly +1 reading, got delta {delta_readings}"
    assert delta_alerts == 0, f"Expected 0 change in alerts, got delta {delta_alerts}"
    assert delta_status == 0, f"Expected 0 change in station status count, got delta {delta_status}"

    final_sim_status = SimulatorController().get_status()
    print(f"Final Simulator State: {final_sim_status['execution_mode']} (running={final_sim_status['running']})")
    assert not final_sim_status["running"], "Simulator must remain STOPPED!"

    print("\n" + "=" * 60)
    print(" >>> LIVE INGESTION VERIFICATION: COMPLETE SUCCESS (PASS) <<< ")
    print(f" Verified Row Key: {expected_row_key}")
    print("=" * 60)


if __name__ == "__main__":
    run_live_ingestion_verification()
