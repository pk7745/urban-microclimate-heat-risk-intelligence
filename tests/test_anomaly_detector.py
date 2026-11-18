"""
Unit and functional tests for the Rule-based Anomaly Detection and Deduplication Engine.
Verifies detection thresholds, unphysical value filtering, and alert deduplication.
"""
import time
from app.services.anomaly_detector import AnomalyDetector


def make_sample_reading(station_id="ST001", temp=30.0, hum=50.0, pm25=30.0, pm10=50.0, status="ACTIVE", heat_index=30.0):
    return {
        "station_id": station_id,
        "station_name": "Bengaluru Central",
        "timestamp": "2026-11-18T00:00:00Z",
        "timestamp_ms": int(time.time() * 1000),
        "temperature_celsius": temp,
        "humidity_percent": hum,
        "pm25": pm25,
        "pm10": pm10,
        "atmospheric_pressure_hpa": 920.0,
        "heat_index_celsius": heat_index,
        "sensor_status": status,
        "data_source": "SIMULATED"
    }


def test_normal_reading_no_alerts():
    detector = AnomalyDetector()
    r = make_sample_reading(temp=28.0, pm25=25.0, pm10=45.0)
    alerts = detector.analyze_reading(r)
    assert len(alerts) == 0


def test_temperature_warning_and_critical():
    detector = AnomalyDetector()

    # Warning threshold (35°C <= temp < 40°C), low humidity to prevent heat index triggering
    r_warn = make_sample_reading(temp=36.5, hum=25.0)
    alerts_w = detector.analyze_reading(r_warn)
    assert any(a["alert_type"] == "HIGH_TEMPERATURE" and a["severity"] == "WARNING" for a in alerts_w)

    # Escalation to Critical (temp >= 40°C)
    r_crit = make_sample_reading(temp=41.2, hum=25.0)
    alerts_c = detector.analyze_reading(r_crit)
    assert any(a["alert_type"] == "HIGH_TEMPERATURE" and a["severity"] == "CRITICAL" for a in alerts_c)


def test_particulate_matter_thresholds():
    detector = AnomalyDetector()

    # PM2.5 Warning (> 60)
    r_pm25 = make_sample_reading(pm25=75.0)
    a_pm25 = detector.analyze_reading(r_pm25)
    assert any(a["alert_type"] == "ELEVATED_PM25" and a["severity"] == "WARNING" for a in a_pm25)

    # PM10 Critical (> 200)
    r_pm10 = make_sample_reading(pm10=220.0)
    a_pm10 = detector.analyze_reading(r_pm10)
    assert any(a["alert_type"] == "ELEVATED_PM10" and a["severity"] == "CRITICAL" for a in a_pm10)


def test_sensor_offline_detection():
    detector = AnomalyDetector()
    r_off = make_sample_reading(status="OFFLINE")
    alerts = detector.analyze_reading(r_off)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "SENSOR_OFFLINE"
    assert alerts[0]["severity"] == "CRITICAL"


def test_invalid_unphysical_reading_detection():
    detector = AnomalyDetector()

    # Out of physical bounds temperature
    r_invalid = make_sample_reading(temp=-999.0)
    alerts = detector.analyze_reading(r_invalid)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "INVALID_READING"
    assert alerts[0]["severity"] == "CRITICAL"


def test_alert_deduplication():
    """
    CRITICAL PROPERTY:
    Continuous violations at the same severity must NOT flood with duplicate alerts.
    """
    detector = AnomalyDetector(cooldown_seconds=30.0)

    # First violation -> emits alert (low humidity prevents concurrent heat index alert)
    r1 = make_sample_reading(temp=37.0, hum=25.0)
    a1 = detector.analyze_reading(r1)
    assert len(a1) == 1
    assert a1[0]["alert_type"] == "HIGH_TEMPERATURE"

    # Second violation immediately after with same severity -> suppressed!
    r2 = make_sample_reading(temp=37.2, hum=25.0)
    a2 = detector.analyze_reading(r2)
    assert len(a2) == 0, "Duplicate alert was not suppressed during continuous event"

    # Return to normal
    r3 = make_sample_reading(temp=29.0, hum=25.0)
    a3 = detector.analyze_reading(r3)
    assert len(a3) == 0
    # State should be cleared
    assert ("ST001", "HIGH_TEMPERATURE") not in detector.active_alert_states

    # Violation occurs again after recovery -> emits new alert
    r4 = make_sample_reading(temp=37.5, hum=25.0)
    a4 = detector.analyze_reading(r4)
    assert len(a4) == 1
