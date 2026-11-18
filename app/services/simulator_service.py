"""
Simulator Control Service for Urban Microclimate Monitoring.
Provides thread-safe singleton control of the virtual sensor simulator
and ingestion pipeline, preventing duplicate workers and ensuring clean lifecycle.
"""
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from config import settings
from app.services.sensor_simulator import SensorSimulatorManager
from app.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

PID_FILE = settings.BASE_DIR / "simulator.pid"

VALID_ANOMALIES = {
    "HIGH_TEMPERATURE",
    "HIGH_HUMIDITY",
    "ELEVATED_PM25",
    "ELEVATED_PM10",
    "SENSOR_OFFLINE",
    "INVALID_READING"
}


class SimulatorController:
    """
    Singleton controller managing the sensor simulator and ingestion worker.
    """
    _instance: Optional["SimulatorController"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SimulatorController, cls).__new__(cls)
                cls._instance._init_controller()
            return cls._instance

    def _init_controller(self):
        self._simulator: Optional[SensorSimulatorManager] = None
        self._ingestor: Optional[IngestionService] = None
        self._state_lock = threading.Lock()

    def _is_external_process_alive(self) -> Tuple[bool, Optional[int]]:
        """Checks if an external start_simulator.py process is alive via PID file."""
        if not PID_FILE.exists():
            return False, None
        try:
            pid = int(PID_FILE.read_text().strip())
            # On Windows, os.kill(pid, 0) checks process existence
            os.kill(pid, 0)
            return True, pid
        except (ValueError, OSError):
            # PID file is stale or process died
            return False, None

    def get_status(self) -> Dict[str, Any]:
        """Returns the current runtime state of the sensor simulator."""
        with self._state_lock:
            ext_alive, ext_pid = self._is_external_process_alive()
            internal_alive = (self._simulator is not None and self._simulator.is_running())

            is_running = internal_alive or ext_alive
            mode = "IN_PROCESS" if internal_alive else ("EXTERNAL_PROCESS" if ext_alive else "STOPPED")

            status = {
                "running": is_running,
                "execution_mode": mode,
                "pid": ext_pid if ext_alive else os.getpid(),
                "stations_count": len(settings.STATIONS),
                "data_source": settings.DATA_SOURCE_LABEL
            }

            if internal_alive and self._simulator and self._ingestor:
                status["interval_seconds"] = self._simulator.interval
                status["readings_generated"] = self._simulator.generated_count
                status["ingestion_stats"] = self._ingestor.get_stats()
            elif ext_alive:
                status["external_pid"] = ext_pid

            return status

    def start(self, interval_seconds: Optional[float] = None) -> Tuple[bool, str]:
        """
        Starts the in-process simulator and ingestion worker safely.
        """
        with self._state_lock:
            ext_alive, ext_pid = self._is_external_process_alive()
            if ext_alive:
                return False, f"Simulator is already running as an external process (PID {ext_pid})."

            if self._simulator is not None and self._simulator.is_running():
                return False, "In-process simulator is already running."

            interval = float(interval_seconds) if interval_seconds else settings.SIMULATOR_INTERVAL_SECONDS
            if interval < 0.5 or interval > 60.0:
                return False, "Interval must be between 0.5 and 60.0 seconds."

            # Instantiate ingestion worker
            self._ingestor = IngestionService()
            self._ingestor.start()

            # Instantiate simulator with callback to ingestion queue
            self._simulator = SensorSimulatorManager(
                interval_seconds=interval,
                on_reading_callback=self._ingestor.submit_reading
            )
            self._simulator.start()

            logger.info("Simulator and Ingestion pipeline started by REST API controller.")
            return True, f"Simulator started successfully with {len(settings.STATIONS)} stations at {interval}s interval."

    def stop(self) -> Tuple[bool, str]:
        """
        Gracefully stops the in-process simulator and drains the ingestion queue.
        """
        with self._state_lock:
            stopped_any = False
            msg_parts = []

            # 1. Stop internal simulator if active
            if self._simulator is not None and self._simulator.is_running():
                self._simulator.stop(timeout=3.0)
                self._simulator = None
                stopped_any = True
                msg_parts.append("In-process simulator stopped.")

            # 2. Stop internal ingestor if active
            if self._ingestor is not None and self._ingestor.is_running():
                self._ingestor.stop(timeout=5.0)
                self._ingestor = None
                stopped_any = True
                msg_parts.append("In-process ingestion worker stopped.")

            # 3. Check external process
            ext_alive, ext_pid = self._is_external_process_alive()
            if ext_alive and ext_pid:
                try:
                    import signal
                    os.kill(ext_pid, signal.SIGTERM)
                    if PID_FILE.exists():
                        PID_FILE.unlink()
                    stopped_any = True
                    msg_parts.append(f"External simulator process (PID {ext_pid}) terminated.")
                except Exception as e:
                    logger.warning("Could not terminate external process %d: %s", ext_pid, e)
                    msg_parts.append(f"Failed to terminate external PID {ext_pid}: {e}")

            if not stopped_any:
                return False, "Simulator is not currently running."

            return True, " ".join(msg_parts)

    def inject_anomaly(self, station_id: str, anomaly_type: str, duration_ticks: int = 3) -> Tuple[bool, str]:
        """
        Injects a temporary controlled anomaly into a virtual station.
        """
        with self._state_lock:
            station_id = station_id.upper()
            anomaly_type = anomaly_type.upper()

            if station_id not in {s["id"] for s in settings.STATIONS}:
                return False, f"Unknown station_id '{station_id}'."

            if anomaly_type not in VALID_ANOMALIES:
                return False, f"Invalid anomaly_type '{anomaly_type}'. Allowed: {sorted(list(VALID_ANOMALIES))}"

            if duration_ticks < 1 or duration_ticks > 20:
                return False, "duration_ticks must be between 1 and 20."

            if self._simulator is None or not self._simulator.is_running():
                return False, "Simulator must be running in-process to inject an anomaly via REST API."

            success = self._simulator.trigger_anomaly(station_id, anomaly_type, duration_ticks=duration_ticks)
            if success:
                return True, f"Injected anomaly '{anomaly_type}' into {station_id} for {duration_ticks} cycles."
            return False, f"Failed to trigger anomaly on station {station_id}."
