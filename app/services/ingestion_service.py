"""
Real-time Ingestion Service for Urban Microclimate Telemetry into Apache HBase.
Connects the Sensor Simulator and Anomaly Detector to HBase REST tables using an
asynchronous bounded Python queue with retry policies and real-time metric tracking.
"""
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from config import settings
from app.services.hbase_client import HBaseClient, RowKeyBuilder
from app.services.anomaly_detector import AnomalyDetector

logger = logging.getLogger(__name__)


class IngestionService:
    """
    Decoupled queue-based ingestion worker that persists streaming sensor readings,
    anomaly alerts, and station heartbeats into Apache HBase via REST.
    """

    def __init__(self,
                 hbase_client: Optional[HBaseClient] = None,
                 anomaly_detector: Optional[AnomalyDetector] = None,
                 queue_maxsize: int = settings.INGESTION_QUEUE_MAXSIZE):
        self.hbase = hbase_client or HBaseClient()
        self.detector = anomaly_detector or AnomalyDetector()
        self.queue: queue.Queue = queue.Queue(maxsize=queue_maxsize)

        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Telemetry metrics & telemetry counters
        self.metrics = {
            "total_received": 0,
            "total_ingested": 0,
            "total_failed": 0,
            "alerts_created": 0,
            "dropped_due_to_queue_full": 0,
            "last_ingest_timestamp": None
        }
        self._lock = threading.Lock()

    def submit_reading(self, reading: Dict[str, Any]) -> bool:
        """
        Thread-safe submission of sensor reading into the ingestion buffer.
        Non-blocking: returns False if queue is saturated to protect producers.
        """
        try:
            self.queue.put(reading, block=False)
            with self._lock:
                self.metrics["total_received"] += 1
            return True
        except queue.Full:
            with self._lock:
                self.metrics["dropped_due_to_queue_full"] += 1
            logger.error("Ingestion buffer full! Dropping reading from station %s",
                         reading.get("station_id"))
            return False

    def start(self):
        """Starts the background consumer thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            logger.warning("Ingestion worker is already running.")
            return

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="HBaseIngestionWorker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info("HBase Ingestion Service started successfully.")

    def stop(self, timeout: float = 10.0):
        """Signals stop and drains any remaining items within timeout."""
        logger.info("Stopping Ingestion Service (queue size remaining: %d)...", self.queue.qsize())
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
        logger.info("Ingestion Service stopped. Ingested: %d, Failed: %d",
                    self.metrics["total_ingested"], self.metrics["total_failed"])

    def is_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def get_stats(self) -> Dict[str, Any]:
        """Returns current operational statistics."""
        with self._lock:
            stats = dict(self.metrics)
            stats["queue_size"] = self.queue.qsize()
            return stats

    def _worker_loop(self):
        """Continuous consumer loop."""
        while not self._stop_event.is_set() or not self.queue.empty():
            try:
                reading = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                self._process_single_reading(reading)
            except Exception as e:
                logger.error("Unhandled error processing reading: %s", e, exc_info=True)
                with self._lock:
                    self.metrics["total_failed"] += 1
            finally:
                self.queue.task_done()

    def _process_single_reading(self, reading: Dict[str, Any]):
        """Processes and writes reading, station status, and alerts to HBase."""
        station_id = reading["station_id"]
        timestamp_ms = reading["timestamp_ms"]

        # 1. Evaluate Anomaly Detection
        detected_alerts = self.detector.analyze_reading(reading)

        # 2. Write to microclimate:readings
        reading_key = RowKeyBuilder.build_reading_key(station_id, timestamp_ms)
        reading_cols = {
            f"{settings.CF_READINGS_METRICS}:temperature_celsius": reading.get("temperature_celsius"),
            f"{settings.CF_READINGS_METRICS}:humidity_percent": reading.get("humidity_percent"),
            f"{settings.CF_READINGS_METRICS}:pm25": reading.get("pm25"),
            f"{settings.CF_READINGS_METRICS}:pm10": reading.get("pm10"),
            f"{settings.CF_READINGS_METRICS}:atmospheric_pressure_hpa": reading.get("atmospheric_pressure_hpa"),
            f"{settings.CF_READINGS_METRICS}:heat_index_celsius": reading.get("heat_index_celsius"),
            f"{settings.CF_READINGS_METADATA}:station_id": reading.get("station_id"),
            f"{settings.CF_READINGS_METADATA}:station_name": reading.get("station_name"),
            f"{settings.CF_READINGS_METADATA}:timestamp": reading.get("timestamp"),
            f"{settings.CF_READINGS_METADATA}:sensor_status": reading.get("sensor_status"),
            f"{settings.CF_READINGS_METADATA}:data_source": reading.get("data_source")
        }

        success = self.hbase.put_row(settings.TABLE_READINGS, reading_key, reading_cols)
        if not success:
            with self._lock:
                self.metrics["total_failed"] += 1
            return

        with self._lock:
            self.metrics["total_ingested"] += 1
            self.metrics["last_ingest_timestamp"] = datetime.now(timezone.utc).isoformat()

        # 3. Update microclimate:station_status
        status_key = RowKeyBuilder.build_status_key(station_id)
        status_cols = {
            f"{settings.CF_STATUS_STATUS}:last_reading_time": reading.get("timestamp"),
            f"{settings.CF_STATUS_STATUS}:connectivity": reading.get("sensor_status"),
            f"{settings.CF_STATUS_STATUS}:temperature": reading.get("temperature_celsius"),
            f"{settings.CF_STATUS_STATUS}:humidity": reading.get("humidity_percent"),
            f"{settings.CF_STATUS_STATUS}:pm25": reading.get("pm25"),
            f"{settings.CF_STATUS_STATUS}:pm10": reading.get("pm10"),
            f"{settings.CF_STATUS_STATUS}:heat_index": reading.get("heat_index_celsius"),
            f"{settings.CF_STATUS_METADATA}:station_id": station_id,
            f"{settings.CF_STATUS_METADATA}:station_name": reading.get("station_name"),
            f"{settings.CF_STATUS_METADATA}:updated_at": datetime.now(timezone.utc).isoformat()
        }
        self.hbase.put_row(settings.TABLE_STATION_STATUS, status_key, status_cols)

        # 4. If any alerts were detected, write each to microclimate:alerts
        for alert in detected_alerts:
            alert_key = RowKeyBuilder.build_alert_key(station_id, alert["alert_type"], alert["timestamp_ms"])
            alert_cols = {
                f"{settings.CF_ALERTS_ALERT}:type": alert["alert_type"],
                f"{settings.CF_ALERTS_ALERT}:severity": alert["severity"],
                f"{settings.CF_ALERTS_ALERT}:measurement": alert["measurement"],
                f"{settings.CF_ALERTS_ALERT}:threshold": alert["threshold"],
                f"{settings.CF_ALERTS_ALERT}:message": alert["message"],
                f"{settings.CF_ALERTS_METADATA}:station_id": alert["station_id"],
                f"{settings.CF_ALERTS_METADATA}:timestamp": alert["timestamp"],
                f"{settings.CF_ALERTS_METADATA}:acknowledged": alert["acknowledged"]
            }
            if "calculation_status" in alert and alert["calculation_status"] is not None:
                alert_cols[f"{settings.CF_ALERTS_ALERT}:calculation_status"] = str(alert["calculation_status"])
            if "origin_temp" in alert and alert["origin_temp"] is not None:
                alert_cols[f"{settings.CF_ALERTS_ALERT}:origin_temp"] = str(alert["origin_temp"])
            if "origin_humidity" in alert and alert["origin_humidity"] is not None:
                alert_cols[f"{settings.CF_ALERTS_ALERT}:origin_humidity"] = str(alert["origin_humidity"])
            if "data_source" in alert and alert["data_source"] is not None:
                alert_cols[f"{settings.CF_ALERTS_METADATA}:data_source"] = str(alert["data_source"])

            if self.hbase.put_row(settings.TABLE_ALERTS, alert_key, alert_cols):
                with self._lock:
                    self.metrics["alerts_created"] += 1
                logger.info("[HBASE] Persisted alert '%s' for station '%s'", alert["alert_type"], station_id)
            else:
                logger.error("[HBASE] Failed to persist alert for station '%s'", station_id)
