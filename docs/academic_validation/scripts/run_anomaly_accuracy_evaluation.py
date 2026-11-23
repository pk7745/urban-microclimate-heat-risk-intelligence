"""
Phase 8.4.4 - Anomaly Detection Accuracy & Alert Lifecycle Evaluation Script.
Evaluates:
  1. Anomaly detection accuracy for each implemented environmental rule:
     - Ambient dry-bulb temperature (warning >= 35°C, critical >= 40°C, unphysical [-10, 65]°C)
     - Relative humidity (unphysical [0, 100]%)
     - PM2.5 particulate matter (warning >= 60 µg/m³, critical >= 120 µg/m³, unphysical [0, 1500] µg/m³)
     - PM10 coarse particulate matter (warning >= 100 µg/m³, critical >= 200 µg/m³, unphysical [0, 2500] µg/m³)
     - Heat index apparent thermal stress (warning >= 38°C, critical >= 44°C, gated by validity)
     - Hardware status (OFFLINE, ERROR)
  2. Alert lifecycle & state machine:
     - First emission, cooldown suppression (60s), cooldown expiration, severity escalation, recovery clearing
  3. Heat index alert provenance tracking:
     - Valid calculation provenance, guard-rejected status, legacy alert handling (LEGACY_UNVERIFIED)
  4. Multi-metric simultaneous violation handling & alert acknowledgement.

Outputs raw structured results to docs/academic_validation/scripts/anomaly_accuracy_results.json.
Safe, non-mutating execution: Zero live HBase calls.
"""
import copy
import json
import logging
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Workspace root
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# Suppress log noise
logging.basicConfig(level=logging.CRITICAL)

from config import settings
from app.services.anomaly_detector import AnomalyDetector
from app.services.hbase_client import RowKeyBuilder
from app.services.telemetry_service import TelemetryService


# =============================================================================
# 1. EVALUATION OF INDIVIDUAL ANOMALY DETECTION RULES
# =============================================================================
def evaluate_individual_rules() -> Dict[str, Any]:
    print("Evaluating Individual Anomaly Detection Rules...")
    detector = AnomalyDetector()

    rules_test_cases = [
        # --- AMBIENT TEMPERATURE RULES ---
        # Warning >= 35.0°C, Critical >= 40.0°C
        {"metric": "temperature", "temp": 34.9, "expected_alert": None, "desc": "Temperature just below warning (34.9°C)"},
        {"metric": "temperature", "temp": 35.0, "expected_alert": ("HIGH_TEMPERATURE", "WARNING"), "desc": "Temperature exactly at warning (35.0°C)"},
        {"metric": "temperature", "temp": 37.5, "expected_alert": ("HIGH_TEMPERATURE", "WARNING"), "desc": "Temperature in warning zone (37.5°C)"},
        {"metric": "temperature", "temp": 39.9, "expected_alert": ("HIGH_TEMPERATURE", "WARNING"), "desc": "Temperature just below critical (39.9°C)"},
        {"metric": "temperature", "temp": 40.0, "expected_alert": ("HIGH_TEMPERATURE", "CRITICAL"), "desc": "Temperature exactly at critical (40.0°C)"},
        {"metric": "temperature", "temp": 43.0, "expected_alert": ("HIGH_TEMPERATURE", "CRITICAL"), "desc": "Temperature well above critical (43.0°C)"},
        {"metric": "temperature", "temp": 65.0, "expected_alert": ("HIGH_TEMPERATURE", "CRITICAL"), "desc": "Temperature at upper physical boundary (65.0°C)"},
        {"metric": "temperature", "temp": 65.1, "expected_alert": ("INVALID_READING", "CRITICAL"), "desc": "Temperature above sanity envelope (65.1°C)"},
        {"metric": "temperature", "temp": -10.0, "expected_alert": None, "desc": "Temperature at lower physical boundary (-10.0°C)"},
        {"metric": "temperature", "temp": -10.1, "expected_alert": ("INVALID_READING", "CRITICAL"), "desc": "Temperature below sanity envelope (-10.1°C)"},
        {"metric": "temperature", "temp": None, "expected_alert": None, "desc": "Missing temperature (None)"},

        # --- PM2.5 PARTICULATE RULES ---
        # Warning >= 60.0 µg/m³, Critical >= 120.0 µg/m³
        {"metric": "pm25", "pm25": 59.9, "expected_alert": None, "desc": "PM2.5 just below warning (59.9 µg/m³)"},
        {"metric": "pm25", "pm25": 60.0, "expected_alert": ("ELEVATED_PM25", "WARNING"), "desc": "PM2.5 exactly at warning (60.0 µg/m³)"},
        {"metric": "pm25", "pm25": 119.9, "expected_alert": ("ELEVATED_PM25", "WARNING"), "desc": "PM2.5 just below critical (119.9 µg/m³)"},
        {"metric": "pm25", "pm25": 120.0, "expected_alert": ("ELEVATED_PM25", "CRITICAL"), "desc": "PM2.5 exactly at critical (120.0 µg/m³)"},
        {"metric": "pm25", "pm25": 1500.0, "expected_alert": ("ELEVATED_PM25", "CRITICAL"), "desc": "PM2.5 at upper physical boundary (1500.0 µg/m³)"},
        {"metric": "pm25", "pm25": 1500.1, "expected_alert": ("INVALID_READING", "CRITICAL"), "desc": "PM2.5 above sanity envelope (1500.1 µg/m³)"},
        {"metric": "pm25", "pm25": -0.1, "expected_alert": ("INVALID_READING", "CRITICAL"), "desc": "Negative PM2.5 (-0.1 µg/m³)"},

        # --- PM10 PARTICULATE RULES ---
        # Warning >= 100.0 µg/m³, Critical >= 200.0 µg/m³
        {"metric": "pm10", "pm10": 99.9, "expected_alert": None, "desc": "PM10 just below warning (99.9 µg/m³)"},
        {"metric": "pm10", "pm10": 100.0, "expected_alert": ("ELEVATED_PM10", "WARNING"), "desc": "PM10 exactly at warning (100.0 µg/m³)"},
        {"metric": "pm10", "pm10": 199.9, "expected_alert": ("ELEVATED_PM10", "WARNING"), "desc": "PM10 just below critical (199.9 µg/m³)"},
        {"metric": "pm10", "pm10": 200.0, "expected_alert": ("ELEVATED_PM10", "CRITICAL"), "desc": "PM10 exactly at critical (200.0 µg/m³)"},
        {"metric": "pm10", "pm10": 2500.0, "expected_alert": ("ELEVATED_PM10", "CRITICAL"), "desc": "PM10 at upper physical boundary (2500.0 µg/m³)"},
        {"metric": "pm10", "pm10": 2500.1, "expected_alert": ("INVALID_READING", "CRITICAL"), "desc": "PM10 above sanity envelope (2500.1 µg/m³)"},
        {"metric": "pm10", "pm10": -1.0, "expected_alert": ("INVALID_READING", "CRITICAL"), "desc": "Negative PM10 (-1.0 µg/m³)"},

        # --- RELATIVE HUMIDITY PHYSICAL ENVELOPE ---
        {"metric": "humidity", "hum": 100.0, "expected_alert": None, "desc": "Humidity at upper boundary (100.0%)"},
        {"metric": "humidity", "hum": 100.1, "expected_alert": ("INVALID_READING", "CRITICAL"), "desc": "Humidity above physical boundary (100.1%)"},
        {"metric": "humidity", "hum": 0.0, "expected_alert": None, "desc": "Humidity at lower boundary (0.0%)"},
        {"metric": "humidity", "hum": -0.1, "expected_alert": ("INVALID_READING", "CRITICAL"), "desc": "Negative humidity (-0.1%)"},

        # --- HEAT INDEX RULES ---
        # Warning >= 38.0°C, Critical >= 44.0°C (gated by validity)
        {"metric": "heat_index", "hi": 37.9, "hi_valid": True, "expected_alert": None, "desc": "Heat index just below warning (37.9°C)"},
        {"metric": "heat_index", "hi": 38.0, "hi_valid": True, "expected_alert": ("HIGH_HEAT_INDEX", "WARNING"), "desc": "Heat index exactly at warning (38.0°C)"},
        {"metric": "heat_index", "hi": 43.9, "hi_valid": True, "expected_alert": ("HIGH_HEAT_INDEX", "WARNING"), "desc": "Heat index just below critical (43.9°C)"},
        {"metric": "heat_index", "hi": 44.0, "hi_valid": True, "expected_alert": ("HIGH_HEAT_INDEX", "CRITICAL"), "desc": "Heat index exactly at critical (44.0°C)"},
        {"metric": "heat_index", "hi": 48.0, "hi_valid": False, "expected_alert": None, "desc": "Heat index 48.0°C but heat_index_is_valid=False (gated)"},
        {"metric": "heat_index", "hi": None, "hi_valid": False, "expected_alert": None, "desc": "Heat index is None (suppressed/low-temp)"},

        # --- HARDWARE / SENSOR STATUS ---
        {"metric": "sensor_status", "status": "OFFLINE", "expected_alert": ("SENSOR_OFFLINE", "CRITICAL"), "desc": "Sensor reported OFFLINE status"},
        {"metric": "sensor_status", "status": "ERROR", "expected_alert": ("INVALID_READING", "CRITICAL"), "desc": "Sensor reported ERROR status"}
    ]

    results = []
    passed = 0
    failed = 0

    for idx, tc in enumerate(rules_test_cases, 1):
        detector.active_alert_states.clear()

        # Build baseline reading
        reading = {
            "station_id": "ST001",
            "station_name": "Bengaluru Central",
            "timestamp": "2026-11-18T10:00:00Z",
            "timestamp_ms": 1794941200000,
            "sensor_status": tc.get("status", "ACTIVE")
        }

        # Apply metric values
        if "temp" in tc:
            reading["temperature_celsius"] = tc["temp"]
        if "hum" in tc:
            reading["humidity_percent"] = tc["hum"]
        if "pm25" in tc:
            reading["pm25"] = tc["pm25"]
        if "pm10" in tc:
            reading["pm10"] = tc["pm10"]
        if "hi" in tc:
            reading["heat_index_celsius"] = tc["hi"]
            reading["heat_index_is_valid"] = tc.get("hi_valid", True)
            reading["heat_index_status"] = "VALID" if tc.get("hi_valid") else "NOT_APPLICABLE_LOW_TEMPERATURE"

        alerts = detector.analyze_reading(reading)

        # Check outcome
        exp = tc["expected_alert"]
        if exp is None:
            case_passed = (len(alerts) == 0)
            actual_str = "None"
        else:
            exp_type, exp_sev = exp
            matched = any(a["alert_type"] == exp_type and a["severity"] == exp_sev for a in alerts)
            case_passed = matched
            actual_str = f"{alerts[0]['alert_type']}:{alerts[0]['severity']}" if alerts else "None"

        if case_passed:
            passed += 1
        else:
            failed += 1

        results.append({
            "test_id": f"RULE_TEST_{idx:02d}",
            "metric_evaluated": tc["metric"],
            "description": tc["desc"],
            "expected_alert": f"{exp[0]}:{exp[1]}" if exp else "None",
            "actual_alert": actual_str,
            "passed": case_passed
        })

    return {
        "total_rule_tests": len(results),
        "passed": passed,
        "failed": failed,
        "results": results
    }


# =============================================================================
# 2. EVALUATION OF ALERT LIFECYCLE & STATE MACHINE
# =============================================================================
def evaluate_alert_lifecycle() -> Dict[str, Any]:
    print("Evaluating Alert Lifecycle & State Machine...")
    detector = AnomalyDetector(cooldown_seconds=60.0)
    station_id = "ST001"
    base_ts = 1794941200000

    lifecycle_events = []

    # Step 1: First occurrence of Warning (36.0°C) -> Should EMIT
    r1 = {"station_id": station_id, "timestamp": "2026-11-18T10:00:00Z", "timestamp_ms": base_ts, "temperature_celsius": 36.0}
    a1 = detector.analyze_reading(r1)
    emitted_1 = len(a1) == 1 and a1[0]["alert_type"] == "HIGH_TEMPERATURE" and a1[0]["severity"] == "WARNING"
    lifecycle_events.append({
        "step": 1, "description": "Initial Warning condition (36°C)",
        "expected": "EMIT Warning", "actual": f"Emitted {len(a1)} alert(s)", "verified": emitted_1
    })

    # Step 2: Repeated occurrence within cooldown (30s later, 36.5°C) -> Should SUPPRESS
    # Mocking time progression
    original_time = time.time
    t0 = time.time()
    try:
        # Advance 30s
        time.time = lambda: t0 + 30.0
        r2 = {"station_id": station_id, "timestamp": "2026-11-18T10:00:30Z", "timestamp_ms": base_ts + 30000, "temperature_celsius": 36.5}
        a2 = detector.analyze_reading(r2)
        suppressed_2 = (len(a2) == 0)
        lifecycle_events.append({
            "step": 2, "description": "Repeated Warning within cooldown (30s elapsed)",
            "expected": "SUPPRESS (0 alerts)", "actual": f"Emitted {len(a2)} alert(s)", "verified": suppressed_2
        })

        # Step 3: Severity Escalation within cooldown (45s later, 41.0°C >= 40.0°C Critical) -> Should EMIT CRITICAL immediately!
        time.time = lambda: t0 + 45.0
        r3 = {"station_id": station_id, "timestamp": "2026-11-18T10:00:45Z", "timestamp_ms": base_ts + 45000, "temperature_celsius": 41.0}
        a3 = detector.analyze_reading(r3)
        escalated_3 = len(a3) == 1 and a3[0]["severity"] == "CRITICAL"
        lifecycle_events.append({
            "step": 3, "description": "Severity Escalation to Critical (41°C) during cooldown",
            "expected": "EMIT Critical immediately", "actual": f"Emitted {a3[0]['severity'] if a3 else 'None'}", "verified": escalated_3
        })

        # Step 4: Repeated Critical within cooldown (55s later, 41.5°C) -> Should SUPPRESS
        time.time = lambda: t0 + 55.0
        r4 = {"station_id": station_id, "timestamp": "2026-11-18T10:00:55Z", "timestamp_ms": base_ts + 55000, "temperature_celsius": 41.5}
        a4 = detector.analyze_reading(r4)
        suppressed_4 = (len(a4) == 0)
        lifecycle_events.append({
            "step": 4, "description": "Repeated Critical within cooldown (10s after escalation)",
            "expected": "SUPPRESS (0 alerts)", "actual": f"Emitted {len(a4)} alert(s)", "verified": suppressed_4
        })

        # Step 5: Cooldown expiration for continuous Critical (65s after escalation -> t0 + 110s) -> Should RE-EMIT reminder
        time.time = lambda: t0 + 110.0
        r5 = {"station_id": station_id, "timestamp": "2026-11-18T10:01:50Z", "timestamp_ms": base_ts + 110000, "temperature_celsius": 42.0}
        a5 = detector.analyze_reading(r5)
        reemitted_5 = len(a5) == 1 and a5[0]["severity"] == "CRITICAL"
        lifecycle_events.append({
            "step": 5, "description": "Cooldown expired (65s after last alert) during ongoing Critical",
            "expected": "RE-EMIT Critical reminder", "actual": f"Emitted {len(a5)} alert(s)", "verified": reemitted_5
        })

        # Step 6: Recovery to normal (30.0°C) -> Should CLEAR condition
        time.time = lambda: t0 + 120.0
        r6 = {"station_id": station_id, "timestamp": "2026-11-18T10:02:00Z", "timestamp_ms": base_ts + 120000, "temperature_celsius": 30.0}
        a6 = detector.analyze_reading(r6)
        cleared_6 = (len(a6) == 0 and (station_id, "HIGH_TEMPERATURE") not in detector.active_alert_states)
        lifecycle_events.append({
            "step": 6, "description": "Metric recovers to normal (30°C)",
            "expected": "CLEAR active condition from state dict", "actual": f"Active state key exists: {(station_id, 'HIGH_TEMPERATURE') in detector.active_alert_states}", "verified": cleared_6
        })

        # Step 7: Subsequent new violation after recovery (36.0°C) -> Should EMIT immediately as new alert
        time.time = lambda: t0 + 130.0
        r7 = {"station_id": station_id, "timestamp": "2026-11-18T10:02:10Z", "timestamp_ms": base_ts + 130000, "temperature_celsius": 36.0}
        a7 = detector.analyze_reading(r7)
        new_emit_7 = len(a7) == 1 and a7[0]["severity"] == "WARNING"
        lifecycle_events.append({
            "step": 7, "description": "Subsequent Warning after recovery",
            "expected": "EMIT Warning immediately as fresh alert", "actual": f"Emitted {len(a7)} alert(s)", "verified": new_emit_7
        })
    finally:
        time.time = original_time

    # Step 8: Simultaneous Multiple Metric Violations
    detector.active_alert_states.clear()
    multi_reading = {
        "station_id": "ST002",
        "timestamp": "2026-11-18T10:00:00Z",
        "timestamp_ms": base_ts,
        "temperature_celsius": 41.0,     # HIGH_TEMPERATURE CRITICAL
        "pm25": 135.0,                  # ELEVATED_PM25 CRITICAL
        "pm10": 220.0,                  # ELEVATED_PM10 CRITICAL
        "heat_index_celsius": 45.0,     # HIGH_HEAT_INDEX CRITICAL
        "heat_index_is_valid": True,
        "heat_index_status": "VALID",
        "sensor_status": "ACTIVE"
    }
    multi_alerts = detector.analyze_reading(multi_reading)
    multi_types = sorted([a["alert_type"] for a in multi_alerts])
    expected_multi = ["ELEVATED_PM10", "ELEVATED_PM25", "HIGH_HEAT_INDEX", "HIGH_TEMPERATURE"]
    multi_verified = (multi_types == expected_multi)
    lifecycle_events.append({
        "step": 8, "description": "Simultaneous multiple metric violations (Temp, PM25, PM10, Heat Index)",
        "expected": str(expected_multi), "actual": str(multi_types), "verified": multi_verified
    })

    return {
        "cooldown_configured_seconds": 60.0,
        "lifecycle_steps_evaluated": len(lifecycle_events),
        "all_steps_verified": all(e["verified"] for e in lifecycle_events),
        "steps": lifecycle_events
    }


# =============================================================================
# 3. EVALUATION OF HEAT-INDEX PROVENANCE & LEGACY UNVERIFIED HANDLING
# =============================================================================
def evaluate_provenance_and_presentation() -> Dict[str, Any]:
    print("Evaluating Heat-Index Provenance & Alert Formatting...")
    provenance_cases = []

    # Case A: High Heat Index with full provenance metadata
    alert_row_verified = {
        "row_key": "ST001#8205058799999#HIGH_HEAT_INDEX",
        "metadata:station_id": "ST001",
        "metadata:timestamp": "2026-11-18T10:00:00Z",
        "metadata:acknowledged": "false",
        "metadata:data_source": "SIMULATED",
        "alert:type": "HIGH_HEAT_INDEX",
        "alert:severity": "CRITICAL",
        "alert:measurement": "45.2",
        "alert:threshold": "44.0",
        "alert:calculation_status": "VALID",
        "alert:origin_temp": "38.0",
        "alert:origin_humidity": "50.0"
    }
    parsed_a = TelemetryService._format_alert_row(alert_row_verified)
    app_a = parsed_a.get("calculation_applicability", {})
    verified_a = (app_a.get("is_valid") is True and 
                  app_a.get("status") == "VALID" and 
                  app_a.get("origin_temp_celsius") == 38.0 and 
                  app_a.get("origin_humidity_percent") == 50.0 and
                  parsed_a.get("event_status") == "HISTORICAL_UNACKNOWLEDGED")

    provenance_cases.append({
        "case": "A_verified_provenance",
        "description": "Alert with complete calculation metadata",
        "applicability_output": app_a,
        "event_status": parsed_a.get("event_status"),
        "verified": verified_a
    })

    # Case B: Legacy alert row missing calculation_status metadata
    alert_row_legacy = {
        "row_key": "ST001#8205058799999#HIGH_HEAT_INDEX",
        "metadata:station_id": "ST001",
        "metadata:timestamp": "2026-11-18T10:00:00Z",
        "metadata:acknowledged": "true",
        "alert:type": "HIGH_HEAT_INDEX",
        "alert:severity": "CRITICAL",
        "alert:measurement": "45.2",
        "alert:threshold": "44.0"
        # No calculation_status, origin_temp, or origin_humidity
    }
    parsed_b = TelemetryService._format_alert_row(alert_row_legacy)
    app_b = parsed_b.get("calculation_applicability", {})
    verified_b = (app_b.get("is_valid") is None and 
                  app_b.get("status") == "LEGACY_UNVERIFIED" and
                  parsed_b.get("event_status") == "HISTORICAL_ACKNOWLEDGED")

    provenance_cases.append({
        "case": "B_legacy_unverified",
        "description": "Legacy alert without calculation provenance",
        "applicability_output": app_b,
        "event_status": parsed_b.get("event_status"),
        "verified": verified_b
    })

    # Case C: Non-heat-index alert (Direct physical sensor metric)
    alert_row_physical = {
        "row_key": "ST001#8205058799999#HIGH_TEMPERATURE",
        "metadata:station_id": "ST001",
        "metadata:acknowledged": "false",
        "alert:type": "HIGH_TEMPERATURE",
        "alert:severity": "WARNING",
        "alert:measurement": "36.5"
    }
    parsed_c = TelemetryService._format_alert_row(alert_row_physical)
    app_c = parsed_c.get("calculation_applicability", {})
    verified_c = (app_c.get("is_valid") is True and app_c.get("status") == "VALIDATED_DOMAIN")

    provenance_cases.append({
        "case": "C_direct_physical_metric",
        "description": "Standard physical metric (HIGH_TEMPERATURE)",
        "applicability_output": app_c,
        "verified": verified_c
    })

    return {
        "provenance_cases_evaluated": len(provenance_cases),
        "all_cases_verified": all(c["verified"] for c in provenance_cases),
        "cases": provenance_cases
    }


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================
def main():
    print("=" * 80)
    print("PHASE 8.4.4: ANOMALY DETECTION & ALERT ACCURACY EVALUATION")
    print("=" * 80)

    summary = {
        "metadata": {
            "evaluation_phase": "Phase 8.4.4",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": "AnomalyDetector & TelemetryService Alert Pipeline"
        },
        "individual_rules_evaluation": evaluate_individual_rules(),
        "alert_lifecycle_evaluation": evaluate_alert_lifecycle(),
        "provenance_and_presentation_evaluation": evaluate_provenance_and_presentation()
    }

    out_file = Path(__file__).resolve().parent / "anomaly_accuracy_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 80)
    print(f"Anomaly detection evaluation complete. Results written to:\n  {out_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
