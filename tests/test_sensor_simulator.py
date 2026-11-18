"""
Unit and functional tests for the Sensor Simulator.
Verifies distinct station IDs, temporal metric variation, schema completeness,
valid timestamps, Heat Index physics, and graceful lifecycle shutdown.
"""
import time
from datetime import datetime
import pytest

from config import settings
from app.services.sensor_simulator import (
    SensorStation,
    SensorSimulatorManager,
    calculate_heat_index
)


def test_heat_index_calculation():
    # At 30°C and 70% humidity, apparent temperature should be higher than ambient
    hi = calculate_heat_index(30.0, 70.0)
    assert hi is not None
    assert hi > 30.0

    # At 20°C (cool day), heat index is near ambient
    hi_cool = calculate_heat_index(20.0, 50.0)
    assert abs(hi_cool - 20.0) < 3.0


def test_five_stations_distinct_ids():
    sim = SensorSimulatorManager()
    assert len(sim.stations) == 5
    station_ids = list(sim.stations.keys())
    assert len(set(station_ids)) == 5
    assert set(station_ids) == {"ST001", "ST002", "ST003", "ST004", "ST005"}


def test_required_fields_exist():
    station = SensorStation(settings.STATIONS[0])
    reading = station.generate_reading()

    required_fields = [
        "temperature_celsius",
        "humidity_percent",
        "pm25",
        "pm10",
        "atmospheric_pressure_hpa",
        "heat_index_celsius",
        "sensor_status",
        "station_id",
        "timestamp",
        "data_source"
    ]
    for field in required_fields:
        assert field in reading, f"Missing required field: {field}"
        assert reading[field] is not None

    assert reading["data_source"] == "SIMULATED"
    assert reading["station_id"] == "ST001"


def test_valid_timestamps():
    station = SensorStation(settings.STATIONS[1])
    reading = station.generate_reading()

    # Must parse as valid ISO timestamp
    ts_str = reading["timestamp"]
    parsed = datetime.fromisoformat(ts_str)
    assert parsed.year >= 2026


def test_measurements_change_over_time():
    station = SensorStation(settings.STATIONS[0])
    r1 = station.generate_reading()
    time.sleep(0.05)
    r2 = station.generate_reading()
    time.sleep(0.05)
    r3 = station.generate_reading()

    # Values must not be identical across ticks due to stochastic drift
    # Check that at least some measurement differs
    changed = (
        r1["temperature_celsius"] != r2["temperature_celsius"] or
        r1["humidity_percent"] != r2["humidity_percent"] or
        r1["pm25"] != r2["pm25"]
    )
    assert changed, "Sensor values failed to exhibit temporal variation"


def test_anomaly_injection():
    station = SensorStation(settings.STATIONS[0])

    # Normal reading first
    r_norm = station.generate_reading()
    assert r_norm["sensor_status"] == "ACTIVE"

    # Inject HIGH_TEMPERATURE
    station.trigger_anomaly("HIGH_TEMPERATURE", duration_ticks=2)
    r_anom = station.generate_reading()
    assert r_anom["sensor_status"] == "CRITICAL"
    assert r_anom["temperature_celsius"] > 40.0

    # Inject SENSOR_OFFLINE
    station.trigger_anomaly("SENSOR_OFFLINE", duration_ticks=1)
    r_off = station.generate_reading()
    assert r_off["sensor_status"] == "OFFLINE"
    assert r_off["temperature_celsius"] is None


def test_graceful_start_and_stop():
    collected = []
    sim = SensorSimulatorManager(interval_seconds=0.1, on_reading_callback=collected.append)

    assert not sim.is_running()
    sim.start()
    assert sim.is_running()

    time.sleep(0.35)
    sim.stop(timeout=2.0)
    assert not sim.is_running()

    assert len(collected) >= 5, f"Expected at least 5 readings collected, got {len(collected)}"
