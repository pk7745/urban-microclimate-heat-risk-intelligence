"""
Comprehensive Test Suite for Heat Index Validation, NOAA/NWS Methodology, and Alert Data Integrity.
Updated for Phase 3.4.

Covers:
1. Normal temperature & humidity combinations.
2. Official NWS preliminary calculation and branching behavior:
   - Case A: hi_avg < 80.0°F -> Steadman preliminary value used directly.
   - Case B: T < 80.0°F but hi_avg >= 80.0°F -> branches to full Rothfusz regression.
3. Low-temperature suppression policy (< 20°C / < 68°F).
4. Physical sensor boundaries (unphysical temperature & humidity ranges).
5. Missing input handling (None values).
6. Project-specific conservative operational safeguard (T > 110°F and RH > 40%).
7. High-temperature synthetic anomaly scenarios (UHI peak modeling).
8. Anomaly detector heat index alert gating:
   - No alert when calculation is invalid/None.
   - Originating calculation metadata included on emitted alerts.
9. Independence of ambient temperature alerts (sensible air heat).
10. Integrity of particulate and hardware offline alerts.
11. Historical alert presentation:
    - Legacy unannotated alerts classified as LEGACY_UNVERIFIED without guessing from scalar values.
    - Verified absence of arbitrary scalar presentation thresholds (e.g., 57.8).
"""
import pytest
from app.services.sensor_simulator import calculate_heat_index, assess_heat_index, SensorStation
from app.services.anomaly_detector import AnomalyDetector
from config import settings
from app import create_app


# =============================================================================
# 1. Normal Temperature & Humidity Combinations
# =============================================================================
def test_normal_temperature_and_humidity():
    """Verify normal combinations yield verified apparent temperatures."""
    # 30°C at 60% RH
    res1 = assess_heat_index(30.0, 60.0)
    assert res1["is_valid"] is True
    assert res1["status"] == "VALID"
    assert res1["heat_index_celsius"] == 32.83
    assert calculate_heat_index(30.0, 60.0) == 32.83

    # 32°C at 70% RH
    res2 = assess_heat_index(32.0, 70.0)
    assert res2["is_valid"] is True
    assert res2["heat_index_celsius"] == 40.41

    # 35°C at 50% RH
    res3 = assess_heat_index(35.0, 50.0)
    assert res3["is_valid"] is True
    assert res3["heat_index_celsius"] == 40.68


# =============================================================================
# 2. Official NWS Preliminary Calculation & Branching
# =============================================================================
def test_nws_preliminary_calculation_and_branching():
    """
    Verify official NWS preliminary calculation and branching behavior:
    hi_simple = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (RH * 0.094))
    hi_avg = 0.5 * (hi_simple + T)
    """
    # Case A: T = 78.0°F (25.56°C), RH = 50.0%
    # hi_simple = 0.5 * (78 + 61 + 12 + 4.7) = 77.85°F
    # hi_avg = 0.5 * (77.85 + 78) = 77.925°F (< 80°F)
    # hi_c = (77.925 - 32) * 5 / 9 = 25.51°C
    t_c_78 = round((78.0 - 32.0) * 5.0 / 9.0, 4)
    res_a = assess_heat_index(t_c_78, 50.0)
    assert res_a["is_valid"] is True
    assert res_a["status"] == "VALID"
    assert "preliminary" in res_a["message"].lower()
    assert res_a["heat_index_celsius"] == 25.51

    # Case B: T = 79.0°F (26.11°C), RH = 95.0%
    # hi_simple = 0.5 * (79 + 61 + 13.2 + 8.93) = 81.065°F
    # hi_avg = 0.5 * (81.065 + 79) = 80.0325°F (>= 80°F)
    # Branches to full Rothfusz regression -> 28.55°C
    t_c_79 = round((79.0 - 32.0) * 5.0 / 9.0, 4)
    res_b = assess_heat_index(t_c_79, 95.0)
    assert res_b["is_valid"] is True
    assert res_b["status"] == "VALID"
    assert "rothfusz" in res_b["message"].lower()
    assert res_b["heat_index_celsius"] == 28.55


# =============================================================================
# 3. Low-Temperature Conditions (< 20°C / < 68°F)
# =============================================================================
def test_low_temperature_not_applicable():
    """Temperatures < 20°C must return NOT_APPLICABLE_LOW_TEMPERATURE and None."""
    # 10°C (cool winter morning)
    res_10c = assess_heat_index(10.0, 60.0)
    assert res_10c["is_valid"] is False
    assert res_10c["status"] == "NOT_APPLICABLE_LOW_TEMPERATURE"
    assert res_10c["heat_index_celsius"] is None
    assert calculate_heat_index(10.0, 60.0) is None

    # 15°C
    res_15c = assess_heat_index(15.0, 50.0)
    assert res_15c["is_valid"] is False
    assert res_15c["status"] == "NOT_APPLICABLE_LOW_TEMPERATURE"
    assert calculate_heat_index(15.0, 50.0) is None

    # Boundary at 20°C (68°F): exactly at threshold, calculation proceeds
    res_20c = assess_heat_index(20.0, 50.0)
    assert res_20c["is_valid"] is True
    assert abs(res_20c["heat_index_celsius"] - 20.0) < 3.0


# =============================================================================
# 4. High-Temperature Synthetic Anomaly Scenario
# =============================================================================
def test_high_temperature_synthetic_anomaly():
    """High-temp anomaly generates physically consistent UHI scenario."""
    station = SensorStation(settings.STATIONS[0])
    station.trigger_anomaly("HIGH_TEMPERATURE", duration_ticks=2)
    reading = station.generate_reading()

    # Temperature must be elevated (39.5°C to 42.0°C)
    assert 39.0 <= reading["temperature_celsius"] <= 42.5
    # Relative humidity must reflect convective drying (25% to 40%)
    assert 25.0 <= reading["humidity_percent"] <= 40.0
    # Heat index must be valid and indicate severe heat stress
    assert reading["heat_index_is_valid"] is True
    assert reading["heat_index_status"] == "VALID"
    assert reading["heat_index_celsius"] >= 43.0
    # Must preserve SIMULATED provenance
    assert reading["data_source"] == "SIMULATED"


# =============================================================================
# 5. Invalid Humidity Values (< 0% or > 100%)
# =============================================================================
def test_invalid_humidity_boundaries():
    """Humidity < 0% or > 100% must return INVALID_HUMIDITY and None."""
    # Negative humidity
    res_neg = assess_heat_index(30.0, -5.0)
    assert res_neg["is_valid"] is False
    assert res_neg["status"] == "INVALID_HUMIDITY"
    assert res_neg["heat_index_celsius"] is None
    assert calculate_heat_index(30.0, -5.0) is None

    # Overshoot humidity > 100%
    res_over = assess_heat_index(30.0, 105.0)
    assert res_over["is_valid"] is False
    assert res_over["status"] == "INVALID_HUMIDITY"
    assert res_over["heat_index_celsius"] is None
    assert calculate_heat_index(30.0, 105.0) is None


# =============================================================================
# 6. Unphysical Temperature Boundaries (< -50°C or > 65°C)
# =============================================================================
def test_unphysical_temperature_boundaries():
    """Temperatures outside physical limits [-50, 65]°C return UNPHYSICAL_TEMPERATURE."""
    res_low = assess_heat_index(-60.0, 50.0)
    assert res_low["is_valid"] is False
    assert res_low["status"] == "UNPHYSICAL_TEMPERATURE"
    assert res_low["heat_index_celsius"] is None

    res_high = assess_heat_index(70.0, 50.0)
    assert res_high["is_valid"] is False
    assert res_high["status"] == "UNPHYSICAL_TEMPERATURE"
    assert res_high["heat_index_celsius"] is None


# =============================================================================
# 7. Missing Input Handling (None)
# =============================================================================
def test_missing_input_handling():
    """None inputs must return MISSING_INPUT and None."""
    res1 = assess_heat_index(None, 60.0)
    assert res1["is_valid"] is False
    assert res1["status"] == "MISSING_INPUT"
    assert res1["heat_index_celsius"] is None
    assert calculate_heat_index(None, 60.0) is None

    res2 = assess_heat_index(30.0, None)
    assert res2["is_valid"] is False
    assert res2["status"] == "MISSING_INPUT"
    assert calculate_heat_index(30.0, None) is None


# =============================================================================
# 8. Regression Applicability Boundaries (Refusing Unverified Extrapolations)
# =============================================================================
def test_regression_applicability_envelope():
    """Conditions outside conservative safeguard must report UNSUPPORTED_EXTRAPOLATION."""
    # Historical problematic combination: 45.17°C with 53.43% RH (T > 110°F and RH > 40%)
    res_extreme = assess_heat_index(45.17, 53.43)
    assert res_extreme["is_valid"] is False
    assert res_extreme["status"] == "UNSUPPORTED_EXTRAPOLATION"
    assert res_extreme["heat_index_celsius"] is None
    # Must NOT return diverging 78.1°C
    assert calculate_heat_index(45.17, 53.43) is None

    # Contrast with valid hot & moderately dry day: 40.0°C with 32.0% RH
    res_valid_hot = assess_heat_index(40.0, 32.0)
    assert res_valid_hot["is_valid"] is True
    assert res_valid_hot["status"] == "VALID"
    assert res_valid_hot["heat_index_celsius"] == 44.05


# =============================================================================
# 9. No Heat-Index Alert When Calculation Is Invalid
# =============================================================================
def test_no_heat_index_alert_when_calculation_invalid():
    """Anomaly detector must NOT trigger a heat-index alert if heat index is None/invalid."""
    detector = AnomalyDetector()
    sample_reading = {
        "station_id": "ST001",
        "timestamp": "2026-11-18T12:00:00Z",
        "timestamp_ms": 1794941000000,
        "temperature_celsius": 45.17,
        "humidity_percent": 53.43,
        "heat_index_celsius": None,  # Marked None by calculation safeguard
        "heat_index_is_valid": False,
        "sensor_status": "ACTIVE"
    }

    alerts = detector.analyze_reading(sample_reading)
    # Must NOT contain HIGH_HEAT_INDEX alert
    heat_alerts = [a for a in alerts if a["alert_type"] == "HIGH_HEAT_INDEX"]
    assert len(heat_alerts) == 0


# =============================================================================
# 10. Heat Index Alert Emits Complete Originating Metadata
# =============================================================================
def test_anomaly_detector_emits_heat_index_metadata():
    """Valid heat index alert must contain calculation_status and originating readings."""
    detector = AnomalyDetector()
    sample_reading = {
        "station_id": "ST002",
        "timestamp": "2026-11-18T12:00:00Z",
        "timestamp_ms": 1794941000000,
        "temperature_celsius": 40.0,
        "humidity_percent": 32.0,
        "heat_index_celsius": 44.05,
        "heat_index_is_valid": True,
        "heat_index_status": "VALID",
        "sensor_status": "ACTIVE",
        "data_source": "SIMULATED"
    }

    alerts = detector.analyze_reading(sample_reading)
    heat_alerts = [a for a in alerts if a["alert_type"] == "HIGH_HEAT_INDEX"]
    assert len(heat_alerts) == 1
    a = heat_alerts[0]
    assert a["severity"] == "CRITICAL"
    assert a["calculation_status"] == "VALID"
    assert a["origin_temp"] == 40.0
    assert a["origin_humidity"] == 32.0
    assert a["data_source"] == "SIMULATED"


# =============================================================================
# 11. Ambient-Temperature Alerts Functioning Independently
# =============================================================================
def test_ambient_temperature_alert_functions_independently():
    """Extreme dry-bulb air temperature still triggers HIGH_TEMPERATURE independently."""
    detector = AnomalyDetector()
    sample_reading = {
        "station_id": "ST001",
        "timestamp": "2026-11-18T12:00:00Z",
        "timestamp_ms": 1794941000000,
        "temperature_celsius": 45.0,  # Exceeds critical threshold 40.0°C
        "humidity_percent": 15.0,
        "heat_index_celsius": None,   # Heat index unavailable or not applicable
        "heat_index_is_valid": False,
        "sensor_status": "ACTIVE"
    }

    alerts = detector.analyze_reading(sample_reading)
    # Must trigger HIGH_TEMPERATURE CRITICAL alert
    temp_alerts = [a for a in alerts if a["alert_type"] == "HIGH_TEMPERATURE"]
    assert len(temp_alerts) == 1
    assert temp_alerts[0]["severity"] == "CRITICAL"
    assert float(temp_alerts[0]["measurement"]) == 45.0


# =============================================================================
# 12. Existing Particulate & Hardware Alerts Fully Functional
# =============================================================================
def test_particulate_and_hardware_alerts_functional():
    """PM2.5, PM10, and offline alerts continue to function correctly."""
    detector = AnomalyDetector()

    # PM2.5 Critical alert
    r_pm25 = {
        "station_id": "ST004",
        "timestamp": "2026-11-18T12:00:00Z",
        "timestamp_ms": 1794941000000,
        "temperature_celsius": 30.0,
        "humidity_percent": 50.0,
        "pm25": 140.0,  # Critical threshold >= 120.0
        "pm10": 80.0,
        "heat_index_celsius": 31.0,
        "sensor_status": "ACTIVE"
    }
    alerts_pm25 = detector.analyze_reading(r_pm25)
    pm25_alerts = [a for a in alerts_pm25 if a["alert_type"] == "ELEVATED_PM25"]
    assert len(pm25_alerts) == 1
    assert pm25_alerts[0]["severity"] == "CRITICAL"

    # Hardware Offline alert
    r_offline = {
        "station_id": "ST003",
        "timestamp": "2026-11-18T12:00:00Z",
        "timestamp_ms": 1794941000000,
        "temperature_celsius": None,
        "humidity_percent": None,
        "sensor_status": "OFFLINE"
    }
    alerts_off = detector.analyze_reading(r_offline)
    assert any(a["alert_type"] == "SENSOR_OFFLINE" for a in alerts_off)


# =============================================================================
# 13. API Identification of Simulated Provenance & Legacy Alert Classification
# =============================================================================
def test_api_alert_presentation_and_provenance():
    """API identifies SIMULATED provenance and classifies legacy alerts as LEGACY_UNVERIFIED."""
    app = create_app({"TESTING": True})
    client = app.test_client()

    resp = client.get("/api/v1/alerts?limit=10")
    assert resp.status_code == 200
    alerts = resp.get_json()["data"]["alerts"]
    assert len(alerts) > 0

    for a in alerts:
        # Must clearly identify data provenance
        assert a["data_source"] == "SIMULATED"
        assert "event_status" in a
        assert a["event_status"] in ("HISTORICAL_UNACKNOWLEDGED", "HISTORICAL_ACKNOWLEDGED")
        assert "calculation_applicability" in a
        assert "status" in a["calculation_applicability"]

    # Specific check on the historical 78.1°C alert in HBase:
    # Under Phase 3.4 methodology, legacy alerts lacking provenance metadata must be
    # classified as LEGACY_UNVERIFIED without relying on an arbitrary scalar cap (e.g. 57.8).
    legacy_heat_alerts = [a for a in alerts if a.get("measurement") == "78.1"]
    if legacy_heat_alerts:
        alert_78 = legacy_heat_alerts[0]
        assert alert_78["calculation_applicability"]["is_valid"] is None
        assert alert_78["calculation_applicability"]["status"] == "LEGACY_UNVERIFIED"
        assert "provenance" in alert_78["calculation_applicability"]["note"].lower()
