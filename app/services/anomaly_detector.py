"""
Rule-based Microclimate Anomaly Detection and Alert Deduplication Engine.
Monitors environmental metrics against configurable safety thresholds, detects
hardware/communication failures, and suppresses duplicate alerts during continuous events.
"""
import logging
import time
from typing import Dict, Any, List, Optional, Tuple

from config import settings

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Evaluates streaming sensor telemetry against urban environmental health thresholds.
    Implements stateful alert deduplication so continuous violations don't flood the database.
    """

    def __init__(self,
                 thresholds: Dict[str, Any] = settings.THRESHOLDS,
                 cooldown_seconds: float = settings.ALERT_COOLDOWN_SECONDS):
        self.thresholds = thresholds
        self.cooldown_seconds = cooldown_seconds
        # In-memory alert state: key = (station_id, alert_type) -> {"severity": str, "last_alert_time": float}
        self.active_alert_states: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def analyze_reading(self, reading: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyzes a single sensor reading and returns any newly triggered or escalated alerts.
        """
        station_id = reading.get("station_id")
        timestamp_str = reading.get("timestamp")
        timestamp_ms = reading.get("timestamp_ms", int(time.time() * 1000))
        sensor_status = reading.get("sensor_status", "ACTIVE")

        alerts: List[Dict[str, Any]] = []

        # 1. Check for Hardware / Communication failure (Sensor Offline)
        if sensor_status == "OFFLINE":
            alert = self._evaluate_condition(
                station_id=station_id,
                alert_type="SENSOR_OFFLINE",
                severity="CRITICAL",
                measurement="OFFLINE",
                threshold="ACTIVE",
                message=f"Station {station_id} is reporting OFFLINE status. No telemetry available.",
                timestamp_str=timestamp_str,
                timestamp_ms=timestamp_ms
            )
            if alert:
                alerts.append(alert)
            return alerts
        else:
            self._clear_condition_if_recovered(station_id, "SENSOR_OFFLINE")

        # 2. Check for Malformed / Invalid / Out-of-bounds Data
        if sensor_status == "ERROR" or self._is_reading_unphysical(reading):
            alert = self._evaluate_condition(
                station_id=station_id,
                alert_type="INVALID_READING",
                severity="CRITICAL",
                measurement=str(reading.get("temperature_celsius")),
                threshold="Physical bounds [-10, 65] °C",
                message=f"Station {station_id} generated unphysical or corrupted sensor readings.",
                timestamp_str=timestamp_str,
                timestamp_ms=timestamp_ms
            )
            if alert:
                alerts.append(alert)
            return alerts
        else:
            self._clear_condition_if_recovered(station_id, "INVALID_READING")

        # 3. Environmental Metric Threshold Evaluations
        # ---------------------------------------------------------------------
        # A. Ambient Dry-Bulb Air Temperature (Physical Atmospheric Energy)
        # Directly measures sensible ambient heat independent of atmospheric moisture.
        # Thresholds: Warning >= 35.0°C, Critical >= 40.0°C.
        temp = reading.get("temperature_celsius")
        if temp is not None:
            t_cfg = self.thresholds.get("temperature", {})
            if temp >= t_cfg.get("critical", 40.0):
                a = self._evaluate_condition(
                    station_id, "HIGH_TEMPERATURE", "CRITICAL", temp, t_cfg["critical"],
                    f"Extreme heat alert: Temperature at {temp}°C exceeds critical threshold {t_cfg['critical']}°C.",
                    timestamp_str, timestamp_ms
                )
                if a:
                    alerts.append(a)
            elif temp >= t_cfg.get("warning", 35.0):
                a = self._evaluate_condition(
                    station_id, "HIGH_TEMPERATURE", "WARNING", temp, t_cfg["warning"],
                    f"High temperature warning: Temperature at {temp}°C exceeds warning threshold {t_cfg['warning']}°C.",
                    timestamp_str, timestamp_ms
                )
                if a:
                    alerts.append(a)
            else:
                self._clear_condition_if_recovered(station_id, "HIGH_TEMPERATURE")

        # B. PM2.5 (Fine particulate matter)
        pm25 = reading.get("pm25")
        if pm25 is not None:
            p25_cfg = self.thresholds.get("pm25", {})
            if pm25 >= p25_cfg.get("critical", 120.0):
                a = self._evaluate_condition(
                    station_id, "ELEVATED_PM25", "CRITICAL", pm25, p25_cfg["critical"],
                    f"Hazardous air quality: PM2.5 level at {pm25} µg/m³ exceeds critical threshold {p25_cfg['critical']} µg/m³.",
                    timestamp_str, timestamp_ms
                )
                if a:
                    alerts.append(a)
            elif pm25 >= p25_cfg.get("warning", 60.0):
                a = self._evaluate_condition(
                    station_id, "ELEVATED_PM25", "WARNING", pm25, p25_cfg["warning"],
                    f"Elevated particulate warning: PM2.5 level at {pm25} µg/m³ exceeds warning threshold {p25_cfg['warning']} µg/m³.",
                    timestamp_str, timestamp_ms
                )
                if a:
                    alerts.append(a)
            else:
                self._clear_condition_if_recovered(station_id, "ELEVATED_PM25")

        # C. PM10 (Coarse particulate matter)
        pm10 = reading.get("pm10")
        if pm10 is not None:
            p10_cfg = self.thresholds.get("pm10", {})
            if pm10 >= p10_cfg.get("critical", 200.0):
                a = self._evaluate_condition(
                    station_id, "ELEVATED_PM10", "CRITICAL", pm10, p10_cfg["critical"],
                    f"Severe dust/soot: PM10 level at {pm10} µg/m³ exceeds critical threshold {p10_cfg['critical']} µg/m³.",
                    timestamp_str, timestamp_ms
                )
                if a:
                    alerts.append(a)
            elif pm10 >= p10_cfg.get("warning", 100.0):
                a = self._evaluate_condition(
                    station_id, "ELEVATED_PM10", "WARNING", pm10, p10_cfg["warning"],
                    f"Dust warning: PM10 level at {pm10} µg/m³ exceeds warning threshold {p10_cfg['warning']} µg/m³.",
                    timestamp_str, timestamp_ms
                )
                if a:
                    alerts.append(a)
            else:
                self._clear_condition_if_recovered(station_id, "ELEVATED_PM10")

        # D. Heat Index (Apparent Human Thermal Stress)
        # Measures physiological heat stress caused by combined heat and humidity impeding sweat evaporation.
        # Thresholds: Caution/Warning >= 38.0°C, Danger/Critical >= 44.0°C.
        # Safeguard: Alerts are generated ONLY when the calculation is validated and reliable.
        hi = reading.get("heat_index_celsius")
        hi_valid = reading.get("heat_index_is_valid", True)

        if hi is not None and hi_valid:
            hi_cfg = self.thresholds.get("heat_index", {})
            origin_temp = reading.get("temperature_celsius")
            origin_hum = reading.get("humidity_percent")
            calc_status = reading.get("heat_index_status", "VALID")
            data_source = reading.get("data_source", settings.DATA_SOURCE_LABEL)

            if hi >= hi_cfg.get("critical", 44.0):
                a = self._evaluate_condition(
                    station_id, "HIGH_HEAT_INDEX", "CRITICAL", hi, hi_cfg["critical"],
                    f"Danger Heat Index: Apparent temp {hi}°C indicates imminent heat illness risk.",
                    timestamp_str, timestamp_ms,
                    calculation_status=calc_status,
                    origin_temp=origin_temp,
                    origin_humidity=origin_hum,
                    data_source=data_source
                )
                if a:
                    alerts.append(a)
            elif hi >= hi_cfg.get("warning", 38.0):
                a = self._evaluate_condition(
                    station_id, "HIGH_HEAT_INDEX", "WARNING", hi, hi_cfg["warning"],
                    f"Caution Heat Index: Apparent temp {hi}°C requires outdoor fatigue precautions.",
                    timestamp_str, timestamp_ms,
                    calculation_status=calc_status,
                    origin_temp=origin_temp,
                    origin_humidity=origin_hum,
                    data_source=data_source
                )
                if a:
                    alerts.append(a)
            else:
                self._clear_condition_if_recovered(station_id, "HIGH_HEAT_INDEX")
        else:
            # Heat index is unavailable, unverified, or not applicable (< 20°C); clear active condition
            self._clear_condition_if_recovered(station_id, "HIGH_HEAT_INDEX")

        return alerts

    def _is_reading_unphysical(self, reading: Dict[str, Any]) -> bool:
        """Validates that sensor values lie within acceptable physical atmospheric ranges."""
        temp = reading.get("temperature_celsius")
        hum = reading.get("humidity_percent")
        pm25 = reading.get("pm25")
        pm10 = reading.get("pm10")

        if temp is not None and (temp < -10.0 or temp > 65.0):
            return True
        if hum is not None and (hum < 0.0 or hum > 100.0):
            return True
        if pm25 is not None and (pm25 < 0.0 or pm25 > 1500.0):
            return True
        if pm10 is not None and (pm10 < 0.0 or pm10 > 2500.0):
            return True
        return False

    def _evaluate_condition(self,
                            station_id: str,
                            alert_type: str,
                            severity: str,
                            measurement: Any,
                            threshold: Any,
                            message: str,
                            timestamp_str: str,
                            timestamp_ms: int,
                            **extra_metadata) -> Optional[Dict[str, Any]]:
        """
        Deduplicates alerts: fires an alert only when entering violation, escalating severity,
        or when the alert cooldown period has elapsed.
        """
        key = (station_id, alert_type)
        now_sec = time.time()
        existing = self.active_alert_states.get(key)

        should_emit = False
        if not existing:
            # Brand new alert
            should_emit = True
        elif existing["severity"] != severity:
            # Severity escalated or changed (e.g. WARNING -> CRITICAL)
            should_emit = True
        elif (now_sec - existing["last_alert_time"]) >= self.cooldown_seconds:
            # Cooldown passed; periodic reminder for ongoing anomaly
            should_emit = True

        if should_emit:
            self.active_alert_states[key] = {
                "severity": severity,
                "last_alert_time": now_sec
            }
            logger.warning("[ALERT TRIGGERED] [%s] %s (%s): %s", station_id, alert_type, severity, message)
            alert_dict = {
                "station_id": station_id,
                "timestamp": timestamp_str,
                "timestamp_ms": timestamp_ms,
                "alert_type": alert_type,
                "severity": severity,
                "measurement": str(measurement),
                "threshold": str(threshold),
                "message": message,
                "acknowledged": "false"
            }
            alert_dict.update(extra_metadata)
            return alert_dict
        return None

    def _clear_condition_if_recovered(self, station_id: str, alert_type: str):
        """Clears active alert state when metric returns to normal range."""
        key = (station_id, alert_type)
        if key in self.active_alert_states:
            logger.info("[ALERT RESOLVED] [%s] %s has normalized.", station_id, alert_type)
            del self.active_alert_states[key]
