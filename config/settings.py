"""
Configuration settings for Urban Microclimate & Heat-Risk Intelligence System.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# HBase REST Gateway Configuration
HBASE_REST_HOST = os.getenv("HBASE_REST_HOST", "localhost")
HBASE_REST_PORT = int(os.getenv("HBASE_REST_PORT", "8085"))
HBASE_REST_URL = f"http://{HBASE_REST_HOST}:{HBASE_REST_PORT}"

# HBase Namespace and Tables
HBASE_NAMESPACE = "microclimate"
TABLE_READINGS = f"{HBASE_NAMESPACE}:readings"
TABLE_ALERTS = f"{HBASE_NAMESPACE}:alerts"
TABLE_STATION_STATUS = f"{HBASE_NAMESPACE}:station_status"

# Column Families
CF_READINGS_METRICS = "metrics"
CF_READINGS_METADATA = "metadata"

CF_ALERTS_ALERT = "alert"
CF_ALERTS_METADATA = "metadata"

CF_STATUS_STATUS = "status"
CF_STATUS_METADATA = "metadata"

# Monitoring Stations Definition
STATIONS = [
    {
        "id": "ST001",
        "name": "Bengaluru Central",
        "zone": "Commercial / Urban Core",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "baseline_temp": 31.0,
        "baseline_humidity": 55.0,
        "baseline_pm25": 52.0,
        "baseline_pm10": 85.0,
        "baseline_pressure": 920.0,
    },
    {
        "id": "ST002",
        "name": "Bengaluru East",
        "zone": "Tech Corridor / Dense Traffic",
        "latitude": 12.9784,
        "longitude": 77.6408,
        "baseline_temp": 30.0,
        "baseline_humidity": 58.0,
        "baseline_pm25": 46.0,
        "baseline_pm10": 76.0,
        "baseline_pressure": 921.0,
    },
    {
        "id": "ST003",
        "name": "Bengaluru South",
        "zone": "Residential / Green Canopy",
        "latitude": 12.9250,
        "longitude": 77.5938,
        "baseline_temp": 28.5,
        "baseline_humidity": 64.0,
        "baseline_pm25": 32.0,
        "baseline_pm10": 52.0,
        "baseline_pressure": 923.0,
    },
    {
        "id": "ST004",
        "name": "Bengaluru West",
        "zone": "Industrial / Transit Interchange",
        "latitude": 12.9750,
        "longitude": 77.5350,
        "baseline_temp": 31.5,
        "baseline_humidity": 52.0,
        "baseline_pm25": 58.0,
        "baseline_pm10": 98.0,
        "baseline_pressure": 919.0,
    },
    {
        "id": "ST005",
        "name": "Bengaluru North",
        "zone": "Highway / Peri-urban",
        "latitude": 13.0358,
        "longitude": 77.5970,
        "baseline_temp": 29.5,
        "baseline_humidity": 60.0,
        "baseline_pm25": 42.0,
        "baseline_pm10": 78.0,
        "baseline_pressure": 922.0,
    },
]

# Simulator Settings
SIMULATOR_INTERVAL_SECONDS = float(os.getenv("SIMULATOR_INTERVAL", "5.0"))
DATA_SOURCE_LABEL = "SIMULATED"

# Ingestion Queue Settings
INGESTION_QUEUE_MAXSIZE = 1000
INGESTION_RETRY_ATTEMPTS = 3
INGESTION_RETRY_BACKOFF = 0.3

# Anomaly Detection Thresholds (Prototype Alert Rules)
THRESHOLDS = {
    "temperature": {
        "warning": 35.0,
        "critical": 40.0
    },
    "pm25": {
        "warning": 60.0,
        "critical": 120.0
    },
    "pm10": {
        "warning": 100.0,
        "critical": 200.0
    },
    "heat_index": {
        "warning": 38.0,
        "critical": 44.0
    }
}

# Alert Deduplication Cooldown (seconds)
ALERT_COOLDOWN_SECONDS = 60.0

# Logging
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
SIMULATOR_LOG_FILE = LOG_DIR / "sensor_simulator.log"
INGESTION_LOG_FILE = LOG_DIR / "ingestion_service.log"
