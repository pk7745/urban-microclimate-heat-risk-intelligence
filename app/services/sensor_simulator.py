"""
Real-time Environmental Sensor Simulator for Urban Microclimate Monitoring.
Simulates 5 independent stations across Bengaluru with realistic environmental dynamics,
diurnal cycle variation, continuous stochastic drift, and controlled anomaly injection.
"""
import math
import random
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable

from config import settings

logger = logging.getLogger(__name__)


def assess_heat_index(temp_celsius: Optional[float], humidity_percent: Optional[float]) -> Dict[str, Any]:
    """
    Validates input atmospheric conditions and computes the National Weather Service (NWS)
    Heat Index (apparent temperature) in Celsius according to Steadman and Rothfusz methodology.

    Methodology Reference:
    - Official NWS Heat Index: https://www.weather.gov/ctp/heat
    - NOAA Technical Attachment SR 90-23 (Rothfusz, 1990)

    Procedure & Policies:
    1. Input Validation:
       - Relative Humidity must be strictly within physical bounds [0.0%, 100.0%].
       - Temperature must be physically plausible (-50.0°C to 65.0°C).
    2. Project Operational Policy (Low-Temperature Suppression):
       - Heat Index is defined exclusively as a metric of physiological heat stress.
       - Under project operational policy, for temperatures below 20.0°C (68.0°F),
         the calculation is suppressed to avoid misleading metrics during cool/cold weather.
         Status: NOT_APPLICABLE_LOW_TEMPERATURE, heat_index_celsius: None.
    3. Official NWS Preliminary Calculation & Averaging:
       - hi_simple = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094))
       - hi_avg = 0.5 * (hi_simple + T)
       - If hi_avg < 80.0°F: use hi_avg directly.
    4. Official NWS Rothfusz Regression (hi_avg >= 80.0°F):
       - Full 9-term polynomial equation fitted to Steadman's biometeorological data.
       - Low-humidity adjustment applied when RH < 13% and 80°F <= T <= 112°F.
       - High-humidity adjustment applied when RH > 85% and 80°F <= T <= 87°F.
    5. Project Conservative Safeguard (Polynomial Divergence Guard):
       - When T > 110.0°F (43.33°C) and RH > 40.0%, the unconstrained 9-term polynomial
         diverges into extreme unverified outputs (e.g. 78°C+). As an operational guard,
         the system halts extrapolation and returns status UNSUPPORTED_EXTRAPOLATION.
         (Note: This is an explicit project safeguard, not an official NWS formula rule).

    Returns:
        dict: {
            "heat_index_celsius": Optional[float],
            "is_valid": bool,
            "status": "VALID" | "NOT_APPLICABLE_LOW_TEMPERATURE" | "INVALID_HUMIDITY" | "UNSUPPORTED_EXTRAPOLATION" | "MISSING_INPUT",
            "message": str
        }
    """
    if temp_celsius is None or humidity_percent is None:
        return {
            "heat_index_celsius": None,
            "is_valid": False,
            "status": "MISSING_INPUT",
            "message": "Temperature or humidity input is missing (None)."
        }

    # Validate relative humidity boundaries [0, 100]%
    if humidity_percent < 0.0 or humidity_percent > 100.0:
        return {
            "heat_index_celsius": None,
            "is_valid": False,
            "status": "INVALID_HUMIDITY",
            "message": f"Relative humidity {humidity_percent}% is outside physical atmospheric bounds [0, 100]%."
        }

    # Validate temperature bounds [-50, 65] °C
    if temp_celsius < -50.0 or temp_celsius > 65.0:
        return {
            "heat_index_celsius": None,
            "is_valid": False,
            "status": "UNPHYSICAL_TEMPERATURE",
            "message": f"Temperature {temp_celsius}°C is outside valid sensor operational bounds [-50, 65]°C."
        }

    t_f = (temp_celsius * 9.0 / 5.0) + 32.0
    rh = humidity_percent

    # Project Operational Policy: Low-temperature boundary
    # Suppress calculation below 20.0°C (68.0°F) because heat stress does not occur in cold conditions.
    if t_f < 68.0:  # < 20.0°C
        return {
            "heat_index_celsius": None,
            "is_valid": False,
            "status": "NOT_APPLICABLE_LOW_TEMPERATURE",
            "message": f"Temperature {temp_celsius}°C is below 20.0°C (68°F); Heat Index is suppressed under project operational policy."
        }

    # Official NWS Preliminary Calculation & Averaging
    hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))
    hi_avg = 0.5 * (hi_simple + t_f)

    # Official NWS Branching: If averaged preliminary calculation is below 80°F, use it directly
    if hi_avg < 80.0:
        hi_c = round((hi_avg - 32.0) * 5.0 / 9.0, 2)
        return {
            "heat_index_celsius": hi_c,
            "is_valid": True,
            "status": "VALID",
            "message": "Calculated via NWS Steadman preliminary equation (hi_avg < 80°F)."
        }

    # hi_avg >= 80.0°F -> Proceed to full Rothfusz regression
    # Project Conservative Operational Guard:
    # If T > 110°F (43.33°C) and RH > 40%, high-order polynomial regression diverges into unphysical values.
    if t_f > 110.0 and rh > 40.0:
        return {
            "heat_index_celsius": None,
            "is_valid": False,
            "status": "UNSUPPORTED_EXTRAPOLATION",
            "message": f"Conditions (T={temp_celsius}°C, RH={rh}%) exceed conservative project safeguard (T > 110°F, RH > 40%) where polynomial regression diverges."
        }

    # Full 9-term Rothfusz regression
    hi_f = (-42.379
            + 2.04901523 * t_f
            + 10.14333127 * rh
            - 0.22475541 * t_f * rh
            - 0.00683783 * (t_f ** 2)
            - 0.05481717 * (rh ** 2)
            + 0.00122874 * (t_f ** 2) * rh
            + 0.00085282 * t_f * (rh ** 2)
            - 0.00000199 * (t_f ** 2) * (rh ** 2))

    # Low-humidity adjustment
    if rh < 13.0 and 80.0 <= t_f <= 112.0:
        adj = ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(t_f - 95.0)) / 17.0)
        hi_f -= adj
    # High-humidity adjustment
    elif rh > 85.0 and 80.0 <= t_f <= 87.0:
        adj = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
        hi_f += adj

    hi_c = round((hi_f - 32.0) * 5.0 / 9.0, 2)
    return {
        "heat_index_celsius": hi_c,
        "is_valid": True,
        "status": "VALID",
        "message": "Calculated via NWS Rothfusz regression polynomial (hi_avg >= 80°F)."
    }


def calculate_heat_index(temp_celsius: Optional[float], humidity_percent: Optional[float]) -> Optional[float]:
    """
    Computes the Heat Index (apparent temperature) in Celsius using standard NWS methodology.
    Returns None if inputs are invalid, temperature is below 20°C, or conditions fall outside
    the validated empirical regression envelope.
    """
    result = assess_heat_index(temp_celsius, humidity_percent)
    return result["heat_index_celsius"]


class SensorStation:
    """
    Represents an individual physical microclimate monitoring station.
    Maintains state and applies continuous autoregressive drifting and anomalies.
    """

    def __init__(self, station_config: Dict[str, Any]):
        self.station_id = station_config["id"]
        self.name = station_config["name"]
        self.zone = station_config.get("zone", "Urban")
        self.lat = station_config.get("latitude", 12.97)
        self.lon = station_config.get("longitude", 77.59)

        # Baseline parameters
        self.baseline_temp = station_config["baseline_temp"]
        self.baseline_humidity = station_config["baseline_humidity"]
        self.baseline_pm25 = station_config["baseline_pm25"]
        self.baseline_pm10 = station_config["baseline_pm10"]
        self.baseline_pressure = station_config["baseline_pressure"]

        # Current internal state
        self.current_temp = self.baseline_temp
        self.current_humidity = self.baseline_humidity
        self.current_pm25 = self.baseline_pm25
        self.current_pm10 = self.baseline_pm10
        self.current_pressure = self.baseline_pressure
        self.sensor_status = "ACTIVE"

        # Active anomaly control
        self.active_anomaly: Optional[str] = None
        self.anomaly_remaining_ticks: int = 0

    def trigger_anomaly(self, anomaly_type: str, duration_ticks: int = 4):
        """Injects a controlled anomaly for a given number of generation cycles."""
        self.active_anomaly = anomaly_type
        self.anomaly_remaining_ticks = duration_ticks
        logger.warning("[%s] Injected anomaly '%s' for %d cycles",
                       self.station_id, anomaly_type, duration_ticks)

    def generate_reading(self) -> Dict[str, Any]:
        """
        Computes the next telemetry reading for this station.
        Applies diurnal cycle + autoregressive drift + Gaussian noise + anomalies.
        """
        now = datetime.now(timezone.utc)
        epoch_ms = int(now.timestamp() * 1000)

        # Handle active anomaly if present
        if self.anomaly_remaining_ticks > 0 and self.active_anomaly:
            reading = self._generate_anomaly_reading(now, epoch_ms)
            self.anomaly_remaining_ticks -= 1
            if self.anomaly_remaining_ticks == 0:
                logger.info("[%s] Anomaly '%s' concluded; returning to normal state.",
                            self.station_id, self.active_anomaly)
                self.active_anomaly = None
                self.sensor_status = "ACTIVE"
            return reading

        # Normal diurnal and autoregressive environmental modeling
        # Diurnal solar cycle: peak at 14:00 UTC+5.30 (approx 08:30 UTC), minimum at 05:00 UTC+5.30
        hour_frac = now.hour + (now.minute / 60.0)
        diurnal_temp_delta = 2.5 * math.sin((hour_frac - 9.0) * math.pi / 12.0)
        diurnal_humidity_delta = -4.0 * math.sin((hour_frac - 9.0) * math.pi / 12.0)

        # Autoregressive drift (80% previous + 20% target baseline + noise)
        target_temp = self.baseline_temp + diurnal_temp_delta
        self.current_temp = (0.80 * self.current_temp) + (0.20 * target_temp) + random.gauss(0, 0.15)
        self.current_temp = round(max(15.0, min(50.0, self.current_temp)), 2)

        target_humidity = self.baseline_humidity + diurnal_humidity_delta
        self.current_humidity = (0.80 * self.current_humidity) + (0.20 * target_humidity) + random.gauss(0, 0.4)
        self.current_humidity = round(max(10.0, min(100.0, self.current_humidity)), 2)

        # Particulate matter dynamics (traffic & wind drift)
        self.current_pm25 = (0.85 * self.current_pm25) + (0.15 * self.baseline_pm25) + random.gauss(0, 1.2)
        self.current_pm25 = round(max(5.0, min(500.0, self.current_pm25)), 2)

        self.current_pm10 = (0.85 * self.current_pm10) + (0.15 * self.baseline_pm10) + random.gauss(0, 2.0)
        self.current_pm10 = round(max(10.0, min(800.0, self.current_pm10)), 2)

        # Barometric pressure drift
        self.current_pressure = (0.90 * self.current_pressure) + (0.10 * self.baseline_pressure) + random.gauss(0, 0.05)
        self.current_pressure = round(self.current_pressure, 2)

        hi_assessment = assess_heat_index(self.current_temp, self.current_humidity)
        heat_index = hi_assessment["heat_index_celsius"]

        return {
            "station_id": self.station_id,
            "station_name": self.name,
            "timestamp": now.isoformat(),
            "timestamp_ms": epoch_ms,
            "temperature_celsius": self.current_temp,
            "humidity_percent": self.current_humidity,
            "pm25": self.current_pm25,
            "pm10": self.current_pm10,
            "atmospheric_pressure_hpa": self.current_pressure,
            "heat_index_celsius": heat_index,
            "heat_index_is_valid": hi_assessment["is_valid"],
            "heat_index_status": hi_assessment["status"],
            "sensor_status": self.sensor_status,
            "data_source": settings.DATA_SOURCE_LABEL
        }

    def _generate_anomaly_reading(self, now: datetime, epoch_ms: int) -> Dict[str, Any]:
        """Synthesizes readings corresponding to explicit anomaly scenarios."""
        anomaly = self.active_anomaly

        if anomaly == "SENSOR_OFFLINE":
            self.sensor_status = "OFFLINE"
            return {
                "station_id": self.station_id,
                "station_name": self.name,
                "timestamp": now.isoformat(),
                "timestamp_ms": epoch_ms,
                "temperature_celsius": None,
                "humidity_percent": None,
                "pm25": None,
                "pm10": None,
                "atmospheric_pressure_hpa": None,
                "heat_index_celsius": None,
                "heat_index_is_valid": False,
                "heat_index_status": "OFFLINE",
                "sensor_status": "OFFLINE",
                "data_source": settings.DATA_SOURCE_LABEL
            }

        if anomaly == "INVALID_READING":
            self.sensor_status = "ERROR"
            return {
                "station_id": self.station_id,
                "station_name": self.name,
                "timestamp": now.isoformat(),
                "timestamp_ms": epoch_ms,
                "temperature_celsius": -999.0,  # Unphysical invalid value
                "humidity_percent": -1.0,
                "pm25": -50.0,
                "pm10": 99999.0,
                "atmospheric_pressure_hpa": 0.0,
                "heat_index_celsius": None,
                "heat_index_is_valid": False,
                "heat_index_status": "INVALID_SENSOR_DATA",
                "sensor_status": "ERROR",
                "data_source": settings.DATA_SOURCE_LABEL
            }

        # Value anomalies
        temp = self.current_temp
        hum = self.current_humidity
        pm25 = self.current_pm25
        pm10 = self.current_pm10
        status = "WARNING"

        if anomaly == "HIGH_TEMPERATURE":
            # Documented Synthetic Scenario: Urban Heat Island Peak (UHI)
            # Simulates severe solar heating over urban surface infrastructure (40.5°C to 42.0°C)
            # accompanied by natural boundary-layer convective drying (relative humidity 28.0% to 36.0%).
            # This represents a realistic extreme urban heat scenario within the validated NOAA Rothfusz
            # regression domain (T <= 110°F), producing an apparent heat-stress index of 44°C to 48°C.
            temp = round(random.uniform(40.5, 42.0), 2)
            hum = round(random.uniform(28.0, 36.0), 2)
            status = "CRITICAL"
        elif anomaly == "HIGH_HUMIDITY":
            hum = round(random.uniform(88.0, 96.5), 2)
            status = "WARNING"
        elif anomaly == "ELEVATED_PM25":
            pm25 = round(random.uniform(130.0, 240.0), 2)
            pm10 = round(pm25 * random.uniform(1.4, 1.8), 2)
            status = "CRITICAL"
        elif anomaly == "ELEVATED_PM10":
            pm10 = round(random.uniform(220.0, 390.0), 2)
            status = "CRITICAL"

        self.sensor_status = status
        hi_assessment = assess_heat_index(temp, hum)
        hi = hi_assessment["heat_index_celsius"]

        return {
            "station_id": self.station_id,
            "station_name": self.name,
            "timestamp": now.isoformat(),
            "timestamp_ms": epoch_ms,
            "temperature_celsius": temp,
            "humidity_percent": hum,
            "pm25": pm25,
            "pm10": pm10,
            "atmospheric_pressure_hpa": self.current_pressure,
            "heat_index_celsius": hi,
            "heat_index_is_valid": hi_assessment["is_valid"],
            "heat_index_status": hi_assessment["status"],
            "sensor_status": self.sensor_status,
            "data_source": settings.DATA_SOURCE_LABEL
        }


class SensorSimulatorManager:
    """
    Manages the lifecycle, threads, and dispatching of all virtual stations.
    """

    def __init__(self,
                 interval_seconds: float = settings.SIMULATOR_INTERVAL_SECONDS,
                 on_reading_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.interval = interval_seconds
        self.callback = on_reading_callback
        self.stations: Dict[str, SensorStation] = {}
        for s_cfg in settings.STATIONS:
            self.stations[s_cfg["id"]] = SensorStation(s_cfg)

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.generated_count = 0

    def trigger_anomaly(self, station_id: str, anomaly_type: str, duration_ticks: int = 3):
        """Triggers a controlled anomaly on a specific station."""
        if station_id in self.stations:
            self.stations[station_id].trigger_anomaly(anomaly_type, duration_ticks)
            return True
        logger.error("Unknown station_id '%s' for anomaly injection", station_id)
        return False

    def start(self):
        """Starts the simulator background generation loop."""
        if self._thread and self._thread.is_alive():
            logger.warning("Simulator is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="SensorSimulatorThread", daemon=True)
        self._thread.start()
        logger.info("Sensor Simulator started with %d stations at %.1fs intervals.",
                    len(self.stations), self.interval)

    def stop(self, timeout: float = 5.0):
        """Gracefully halts the simulator loop."""
        logger.info("Stopping Sensor Simulator...")
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("Sensor Simulator stopped successfully.")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self):
        while not self._stop_event.is_set():
            start_time = time.time()
            for station in self.stations.values():
                if self._stop_event.is_set():
                    break
                reading = station.generate_reading()
                self.generated_count += 1
                if self.callback:
                    try:
                        self.callback(reading)
                    except Exception as e:
                        logger.error("Error in simulator callback: %s", e)

            # Sleep remainder of the cycle interval
            elapsed = time.time() - start_time
            sleep_duration = max(0.1, self.interval - elapsed)
            self._stop_event.wait(timeout=sleep_duration)
