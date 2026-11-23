"""
Independent Reference Implementation and Verification Script for NWS Heat Index.

Phase 7.3.1 — Academic Evidence & Formula Verification Protocol.
Author: Academic Technical Review Team
Date: November 2026

Strict Independence Requirement:
This script implements the National Weather Service (NWS) Steadman & Rothfusz (1990)
equations independently from first principles. It does NOT import or reuse any internal
calculation functions from app.services.sensor_simulator.
"""
import math
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

# Add project root to sys.path so we can import the application's function for comparison
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Project-defined numerical verification tolerance (for rounding / floating-point parity)
PROJECT_NUMERICAL_TOLERANCE_C = 0.05  # degrees Celsius


def independent_nws_heat_index(temp_celsius: float, relative_humidity: float) -> Tuple[float, float, str]:
    """
    Independent reference implementation of the official National Weather Service (NWS)
    Heat Index algorithm based on Steadman (1979) and NOAA Technical Attachment SR 90-23 (Rothfusz, 1990).

    Returns:
        (unrounded_celsius, rounded_celsius, branch_name)
    """
    t_f = (temp_celsius * 9.0 / 5.0) + 32.0
    rh = relative_humidity

    # Step 1: Steadman preliminary equation
    hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))

    # Step 2: Steadman averaging step
    hi_avg = 0.5 * (hi_simple + t_f)

    # Step 3: Branching condition at 80 deg F
    if hi_avg < 80.0:
        hi_c_unrounded = (hi_avg - 32.0) * 5.0 / 9.0
        return hi_c_unrounded, round(hi_c_unrounded, 2), "STEADMAN_PRELIMINARY_AVERAGE"

    # Step 4: Full 9-term Rothfusz polynomial regression
    hi_f = (-42.379
            + 2.04901523 * t_f
            + 10.14333127 * rh
            - 0.22475541 * t_f * rh
            - 0.00683783 * (t_f ** 2)
            - 0.05481717 * (rh ** 2)
            + 0.00122874 * (t_f ** 2) * rh
            + 0.00085282 * t_f * (rh ** 2)
            - 0.00000199 * (t_f ** 2) * (rh ** 2))

    branch = "ROTHFUSZ_FULL_REGRESSION"

    # Step 5: Low-RH adjustment
    if rh < 13.0 and 80.0 <= t_f <= 112.0:
        adj = ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(t_f - 95.0)) / 17.0)
        hi_f -= adj
        branch = "ROTHFUSZ_LOW_RH_ADJUSTED"
    # Step 6: High-RH adjustment
    elif rh > 85.0 and 80.0 <= t_f <= 87.0:
        adj = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
        hi_f += adj
        branch = "ROTHFUSZ_HIGH_RH_ADJUSTED"

    hi_c_unrounded = (hi_f - 32.0) * 5.0 / 9.0
    return hi_c_unrounded, round(hi_c_unrounded, 2), branch


def run_independent_verification() -> Dict[str, Any]:
    """Executes Task 1 and Task 2 verification protocols and returns structured evidence."""
    from app.services.sensor_simulator import assess_heat_index

    results = {
        "task1_formula_verification": [],
        "task2_policy_verification": [],
        "total_task1": 0,
        "passed_task1": 0,
        "total_task2": 0,
        "passed_task2": 0
    }

    # =========================================================================
    # Task 1: Required Test Cases
    # =========================================================================
    task1_cases = [
        {"id": "TC-HI-01", "t_c": 25.0, "rh": 50.0},
        {"id": "TC-HI-02", "t_c": 27.0, "rh": 60.0},
        {"id": "TC-HI-03", "t_c": 30.0, "rh": 70.0},
        {"id": "TC-HI-04", "t_c": 32.0, "rh": 80.0},
        {"id": "TC-HI-05", "t_c": 35.0, "rh": 50.0},
        {"id": "TC-HI-06", "t_c": 38.0, "rh": 10.0},
        {"id": "TC-HI-07", "t_c": 29.0, "rh": 90.0},
    ]

    print("=" * 115)
    print("TASK 1: INDEPENDENT NWS HEAT-INDEX FORMULA IMPLEMENTATION VERIFICATION")
    print(f"Project Numerical Implementation Tolerance: +/- {PROJECT_NUMERICAL_TOLERANCE_C} deg C (Project-Defined Parity)")
    print("=" * 115)
    header = f"{'Case ID':<10} | {'Temp (C)':<8} | {'RH (%)':<6} | {'Unrounded Ref':<14} | {'Rounded Ref':<12} | {'App Result':<12} | {'Full-Prec Diff':<16} | {'Status'}"
    print(header)
    print("-" * 115)

    for c in task1_cases:
        cid = c["id"]
        tc = c["t_c"]
        rh = c["rh"]

        # Run independent reference calculation
        ref_unrounded, ref_rounded, branch = independent_nws_heat_index(tc, rh)

        # Run application implementation (which returns rounded to 2 decimal places)
        app_res = assess_heat_index(tc, rh)
        app_hi = app_res["heat_index_celsius"]

        # Full precision difference: |Unrounded Ref - App Result|
        diff_full = abs(ref_unrounded - app_hi) if (ref_unrounded is not None and app_hi is not None) else None
        diff_rounded = abs(ref_rounded - app_hi) if (ref_rounded is not None and app_hi is not None) else None

        # Evaluated against project tolerance of 0.05 C
        is_pass = diff_full is not None and (diff_full <= PROJECT_NUMERICAL_TOLERANCE_C)

        results["total_task1"] += 1
        if is_pass:
            results["passed_task1"] += 1

        status_str = "PASS" if is_pass else "FAIL"
        diff_str = f"{diff_full:.8f} C" if diff_full is not None else "N/A"
        print(f"{cid:<10} | {tc:<8.1f} | {rh:<6.1f} | {ref_unrounded:<14.6f} | {ref_rounded:<12.2f} | {app_hi:<12.2f} | {diff_str:<16} | {status_str}")

        results["task1_formula_verification"].append({
            "id": cid,
            "temp_c": tc,
            "rh": rh,
            "unrounded_reference": ref_unrounded,
            "rounded_reference": ref_rounded,
            "application_result": app_hi,
            "full_precision_difference": diff_full,
            "rounded_difference": diff_rounded,
            "branch": branch,
            "passed": is_pass
        })

    print("-" * 115)
    print(f"Task 1 Summary: {results['passed_task1']} / {results['total_task1']} cases passed tolerance (|Delta| <= {PROJECT_NUMERICAL_TOLERANCE_C} C).\n")

    # =========================================================================
    # Task 2: Project-Specific Operational Policy Tests
    # =========================================================================
    task2_cases = [
        {
            "id": "TC-POL-01",
            "desc": "Temperature below 20 deg C (< 68 deg F)",
            "t_c": 18.0,
            "rh": 50.0,
            "expected_val": None,
            "expected_status": "NOT_APPLICABLE_LOW_TEMPERATURE",
            "rationale": "Project policy suppresses Heat Index during cold weather (heat stress not applicable)."
        },
        {
            "id": "TC-POL-02",
            "desc": "Relative humidity below 0%",
            "t_c": 30.0,
            "rh": -5.0,
            "expected_val": None,
            "expected_status": "INVALID_HUMIDITY",
            "rationale": "Physical atmospheric boundary check (RH cannot be negative)."
        },
        {
            "id": "TC-POL-03",
            "desc": "Relative humidity above 100%",
            "t_c": 30.0,
            "rh": 105.0,
            "expected_val": None,
            "expected_status": "INVALID_HUMIDITY",
            "rationale": "Physical atmospheric boundary check (RH cannot exceed supersaturation limit)."
        },
        {
            "id": "TC-POL-04",
            "desc": "Temperature above operational upper bound (> 65 deg C)",
            "t_c": 70.0,
            "rh": 50.0,
            "expected_val": None,
            "expected_status": "UNPHYSICAL_TEMPERATURE",
            "rationale": "Sensor physical operational limit [-50, 65] deg C exceeded."
        },
        {
            "id": "TC-POL-05",
            "desc": "Conservative extreme-condition guard (T > 110 deg F & RH > 40%)",
            "t_c": 45.0,  # 113 deg F
            "rh": 50.0,
            "expected_val": None,
            "expected_status": "UNSUPPORTED_EXTRAPOLATION",
            "rationale": "Project operational guard to prevent unconstrained 9-term polynomial divergence."
        },
    ]

    print("=" * 115)
    print("TASK 2: PROJECT-SPECIFIC OPERATIONAL POLICIES & BOUNDARY GUARDS")
    print("Note: These are project-defined operational safeguards, distinct from official NWS calculation rules.")
    print("=" * 115)
    header2 = f"{'Case ID':<10} | {'Test Scenario':<36} | {'Exp Val':<8} | {'Act Val':<8} | {'Exp Status':<30} | {'Act Status':<30} | {'Result'}"
    print(header2)
    print("-" * 115)

    for p in task2_cases:
        pid = p["id"]
        tc = p["t_c"]
        rh = p["rh"]
        exp_val = p["expected_val"]
        exp_stat = p["expected_status"]

        app_res = assess_heat_index(tc, rh)
        act_val = app_res["heat_index_celsius"]
        act_stat = app_res["status"]

        is_val_match = (act_val == exp_val)
        is_stat_match = (act_stat == exp_stat)
        is_pass = is_val_match and is_stat_match

        results["total_task2"] += 1
        if is_pass:
            results["passed_task2"] += 1

        val_str = str(act_val)
        exp_val_str = str(exp_val)
        status_str = "PASS" if is_pass else "FAIL"
        print(f"{pid:<10} | {p['desc'][:36]:<36} | {exp_val_str:<8} | {val_str:<8} | {exp_stat:<30} | {act_stat:<30} | {status_str}")

        results["task2_policy_verification"].append({
            "id": pid,
            "scenario": p["desc"],
            "temp_c": tc,
            "rh": rh,
            "expected_val": exp_val,
            "actual_val": act_val,
            "expected_status": exp_stat,
            "actual_status": act_stat,
            "passed": is_pass,
            "rationale": p["rationale"]
        })

    print("-" * 115)
    print(f"Task 2 Summary: {results['passed_task2']} / {results['total_task2']} policy tests passed.\n")

    return results


if __name__ == "__main__":
    run_independent_verification()
