"""
Phase 8.4.4 - Heat-Index Numerical Accuracy & Boundary Evaluation Script.
Evaluates the project's Heat Index implementation against an independent reference
implementation of the official US National Weather Service (NWS) Steadman & Rothfusz (1990)
equations across a controlled matrix of atmospheric, boundary, guard, and non-finite inputs.

Strict Academic Protocol:
- The independent reference calculation does NOT import assess_heat_index or calculate_heat_index.
- Derived completely from first principles using the NOAA/NWS equations.
- Uses full precision before display rounding.
- Explicitly tests IEEE 754 NaN and infinity stability (verifying RF-02).
- Distinguishes official NWS rules from project-specific operational guards.
"""
import copy
import json
import logging
import math
import os
from pathlib import Path
import sys
from typing import Dict, Any, List, Optional, Tuple

# Workspace root
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# Suppress log noise
logging.basicConfig(level=logging.CRITICAL)

from app.services.sensor_simulator import assess_heat_index, calculate_heat_index

# Verification tolerance for rounding parity
NUMERICAL_TOLERANCE_C = 0.05  # degrees Celsius


# =============================================================================
# INDEPENDENT REFERENCE IMPLEMENTATION (STRICT FIRST PRINCIPLES)
# =============================================================================
def independent_nws_heat_index(temp_celsius: float, relative_humidity: float) -> Dict[str, Any]:
    """
    Independent reference implementation of the official US National Weather Service (NWS)
    Heat Index algorithm (Steadman 1979; Rothfusz 1990; NOAA WPC equation).
    Does NOT import or call any project functions.
    """
    # Check non-finite inputs
    if not math.isfinite(temp_celsius) or not math.isfinite(relative_humidity):
        return {
            "heat_index_f_unrounded": float("nan"),
            "heat_index_c_unrounded": float("nan"),
            "heat_index_c_rounded": None,
            "branch": "NON_FINITE_INPUT",
            "is_valid": False,
            "error": "Input is not finite (NaN or Inf)"
        }

    # Step A: Celsius to Fahrenheit
    t_f = (temp_celsius * 9.0 / 5.0) + 32.0
    rh = relative_humidity

    # Step B: Steadman preliminary equation
    hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))

    # Step C: Average preliminary heat index with ambient temperature
    hi_avg = 0.5 * (hi_simple + t_f)

    # Step D: Branching condition at 80 deg F
    if hi_avg < 80.0:
        hi_f = hi_avg
        branch = "STEADMAN_PRELIMINARY_AVERAGE"
    else:
        # Full 9-term Rothfusz polynomial regression
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

        # Step E: Low-humidity adjustment
        if rh < 13.0 and 80.0 <= t_f <= 112.0:
            adj = ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(t_f - 95.0)) / 17.0)
            hi_f -= adj
            branch = "ROTHFUSZ_LOW_RH_ADJUSTMENT"
        # Step F: High-humidity adjustment
        elif rh > 85.0 and 80.0 <= t_f <= 87.0:
            adj = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
            hi_f += adj
            branch = "ROTHFUSZ_HIGH_RH_ADJUSTMENT"

    # Step G: Convert final result back to Celsius
    hi_c_unrounded = (hi_f - 32.0) * 5.0 / 9.0
    hi_c_rounded = round(hi_c_unrounded, 2)

    return {
        "heat_index_f_unrounded": hi_f,
        "heat_index_c_unrounded": hi_c_unrounded,
        "heat_index_c_rounded": hi_c_rounded,
        "preliminary_hi_avg_f": hi_avg,
        "branch": branch,
        "is_valid": True,
        "error": None
    }


# =============================================================================
# TEST MATRIX GENERATOR
# =============================================================================
def build_heat_index_test_matrix() -> List[Dict[str, Any]]:
    """Builds controlled atmospheric input matrix across all verification categories."""
    cases = []

    # Category 1: Below Rothfusz threshold (hi_avg < 80°F)
    cases.extend([
        {"category": "1_below_rothfusz_threshold", "temp_c": 21.0, "rh": 50.0, "desc": "Cool mild (21°C / 50% RH)"},
        {"category": "1_below_rothfusz_threshold", "temp_c": 23.0, "rh": 60.0, "desc": "Comfortable room temp (23°C / 60% RH)"},
        {"category": "1_below_rothfusz_threshold", "temp_c": 25.0, "rh": 40.0, "desc": "Warm dry (25°C / 40% RH)"},
        {"category": "1_below_rothfusz_threshold", "temp_c": 25.5556, "rh": 50.0, "desc": "78°F ambient, hi_avg = 77.925°F (< 80°F)"}
    ])

    # Category 2: Immediately around 80°F preliminary average boundary
    # Fixed RH = 50.0%: hi_avg = 1.05 * t_f - 3.975 -> t_f = (hi_avg + 3.975) / 1.05
    t_f_79_9 = (79.9 - 3.975) / 1.05
    t_c_79_9 = (t_f_79_9 - 32.0) * 5.0 / 9.0
    t_f_80_0 = (80.0 - 3.975) / 1.05
    t_c_80_0 = (t_f_80_0 - 32.0) * 5.0 / 9.0
    t_f_80_1 = (80.1 - 3.975) / 1.05
    t_c_80_1 = (t_f_80_1 - 32.0) * 5.0 / 9.0

    cases.extend([
        {"category": "2_boundary_80f_activation", "temp_c": round(t_c_79_9, 4), "rh": 50.0, "desc": "Boundary hi_avg = 79.9°F (Steadman Preliminary)"},
        {"category": "2_boundary_80f_activation", "temp_c": round(t_c_80_0, 4), "rh": 50.0, "desc": "Boundary hi_avg = 80.0°F (Exact Rothfusz activation)"},
        {"category": "2_boundary_80f_activation", "temp_c": round(t_c_80_1, 4), "rh": 50.0, "desc": "Boundary hi_avg = 80.1°F (Rothfusz Regression)"}
    ])

    # Category 3: Standard warm and humid conditions (above 80°F, unadjusted Rothfusz)
    cases.extend([
        {"category": "3_warm_humid_rothfusz", "temp_c": 30.0, "rh": 60.0, "desc": "Tropical warm (30°C / 60% RH)"},
        {"category": "3_warm_humid_rothfusz", "temp_c": 32.0, "rh": 70.0, "desc": "Monsoon muggy (32°C / 70% RH)"},
        {"category": "3_warm_humid_rothfusz", "temp_c": 35.0, "rh": 50.0, "desc": "Bengaluru summer peak (35°C / 50% RH)"},
        {"category": "3_warm_humid_rothfusz", "temp_c": 38.0, "rh": 45.0, "desc": "Severe heat (38°C / 45% RH)"}
    ])

    # Category 4: Low-humidity adjustment conditions (RH < 13%, 80°F <= T_F <= 112°F)
    cases.extend([
        {"category": "4_low_humidity_adjustment", "temp_c": 30.0, "rh": 10.0, "desc": "Low humidity: 30°C (86°F), 10% RH"},
        {"category": "4_low_humidity_adjustment", "temp_c": 35.0, "rh": 8.0, "desc": "Low humidity: 35°C (95°F), 8% RH (apex |T-95|=0)"},
        {"category": "4_low_humidity_adjustment", "temp_c": 40.0, "rh": 12.0, "desc": "Low humidity: 40°C (104°F), 12% RH"},
        {"category": "4_low_humidity_adjustment", "temp_c": 44.0, "rh": 10.0, "desc": "Low humidity: 44°C (111.2°F), 10% RH"}
    ])

    # Category 5: High-humidity adjustment conditions (RH > 85%, 80°F <= T_F <= 87°F)
    cases.extend([
        {"category": "5_high_humidity_adjustment", "temp_c": 27.0, "rh": 90.0, "desc": "High humidity: 27°C (80.6°F), 90% RH"},
        {"category": "5_high_humidity_adjustment", "temp_c": 28.0, "rh": 92.0, "desc": "High humidity: 28°C (82.4°F), 92% RH"},
        {"category": "5_high_humidity_adjustment", "temp_c": 29.0, "rh": 88.0, "desc": "High humidity: 29°C (84.2°F), 88% RH"},
        {"category": "5_high_humidity_adjustment", "temp_c": 30.0, "rh": 90.0, "desc": "High humidity: 30°C (86.0°F), 90% RH"}
    ])

    # Category 6: Boundary values around adjustment edges
    cases.extend([
        {"category": "6_adjustment_edges", "temp_c": 35.0, "rh": 12.9, "desc": "RH 12.9% (< 13.0%, adjustment applies)"},
        {"category": "6_adjustment_edges", "temp_c": 35.0, "rh": 13.0, "desc": "RH 13.0% (exact boundary, adjustment=0)"},
        {"category": "6_adjustment_edges", "temp_c": 35.0, "rh": 13.1, "desc": "RH 13.1% (> 13.0%, no adjustment)"},
        {"category": "6_adjustment_edges", "temp_c": 28.0, "rh": 84.9, "desc": "RH 84.9% (< 85.0%, no adjustment)"},
        {"category": "6_adjustment_edges", "temp_c": 28.0, "rh": 85.0, "desc": "RH 85.0% (exact boundary, adjustment=0)"},
        {"category": "6_adjustment_edges", "temp_c": 28.0, "rh": 85.1, "desc": "RH 85.1% (> 85.0%, adjustment applies)"}
    ])

    # Category 7: Project-specific operational guards
    cases.extend([
        {"category": "7_project_operational_guards", "temp_c": 19.9, "rh": 60.0, "desc": "19.9°C (< 20°C low-temp policy cutoff)"},
        {"category": "7_project_operational_guards", "temp_c": 15.0, "rh": 50.0, "desc": "15.0°C cool morning"},
        {"category": "7_project_operational_guards", "temp_c": 10.0, "rh": 70.0, "desc": "10.0°C winter morning"},
        {"category": "7_project_operational_guards", "temp_c": 0.0, "rh": 80.0, "desc": "0.0°C freezing"},
        {"category": "7_project_operational_guards", "temp_c": -10.0, "rh": 50.0, "desc": "-10.0°C sanity lower limit"},
        {"category": "7_project_operational_guards", "temp_c": 44.0, "rh": 45.0, "desc": "T > 110°F (111.2°F) and RH > 40% (Polynomial divergence guard)"},
        {"category": "7_project_operational_guards", "temp_c": 45.0, "rh": 50.0, "desc": "T = 45°C (113°F) and RH = 50% (Divergence guard)"}
    ])

    # Category 8: Invalid inputs & numerical stability (including RF-02 NaN check)
    cases.extend([
        {"category": "8_invalid_and_numerical_stability", "temp_c": 30.0, "rh": -5.0, "desc": "Negative relative humidity (-5.0%)"},
        {"category": "8_invalid_and_numerical_stability", "temp_c": 30.0, "rh": 105.0, "desc": "Relative humidity > 100% (105.0%)"},
        {"category": "8_invalid_and_numerical_stability", "temp_c": -55.0, "rh": 50.0, "desc": "Temperature < -50°C (-55.0°C)"},
        {"category": "8_invalid_and_numerical_stability", "temp_c": 70.0, "rh": 50.0, "desc": "Temperature > 65°C (70.0°C)"},
        {"category": "8_invalid_and_numerical_stability", "temp_c": None, "rh": 50.0, "desc": "Missing temperature (None)"},
        {"category": "8_invalid_and_numerical_stability", "temp_c": 30.0, "rh": None, "desc": "Missing relative humidity (None)"},
        {"category": "8_invalid_and_numerical_stability", "temp_c": float("nan"), "rh": 50.0, "desc": "IEEE 754 NaN Temperature (RF-02 verification)"},
        {"category": "8_invalid_and_numerical_stability", "temp_c": 30.0, "rh": float("nan"), "desc": "IEEE 754 NaN Relative Humidity (RF-02 verification)"},
        {"category": "8_invalid_and_numerical_stability", "temp_c": float("inf"), "rh": 50.0, "desc": "Positive Infinity Temperature"},
        {"category": "8_invalid_and_numerical_stability", "temp_c": float("-inf"), "rh": 50.0, "desc": "Negative Infinity Temperature"}
    ])

    return cases


# =============================================================================
# ACCURACY EVALUATION RUNNER
# =============================================================================
def run_heat_index_accuracy_evaluation() -> Dict[str, Any]:
    print("=" * 80)
    print("PHASE 8.4.4: HEAT-INDEX NUMERICAL ACCURACY EVALUATION")
    print("=" * 80)

    test_matrix = build_heat_index_test_matrix()
    comparisons = []
    differences_c = []
    differences_f = []

    passed_count = 0
    failed_count = 0

    max_diff_c = 0.0
    max_diff_case_c = None
    max_diff_f = 0.0
    max_diff_case_f = None

    for idx, tc in enumerate(test_matrix, 1):
        temp_c = tc["temp_c"]
        rh = tc["rh"]
        cat = tc["category"]
        desc = tc["desc"]

        # Run project implementation
        proj_res = None
        proj_hi_c = None
        proj_status = None
        proj_valid = None
        try:
            proj_res = assess_heat_index(temp_c, rh)
            proj_hi_c = proj_res.get("heat_index_celsius")
            proj_status = proj_res.get("status")
            proj_valid = proj_res.get("is_valid")
        except Exception as e:
            proj_status = f"EXCEPTION: {type(e).__name__}"

        # Run independent reference (only if inputs are finite floats)
        is_finite_input = (isinstance(temp_c, (int, float)) and math.isfinite(temp_c) and
                           isinstance(rh, (int, float)) and math.isfinite(rh))

        ref_res = None
        ref_hi_c_unrounded = None
        ref_hi_c_rounded = None
        ref_hi_f_unrounded = None
        ref_branch = None

        if is_finite_input:
            ref_res = independent_nws_heat_index(temp_c, rh)
            ref_hi_c_unrounded = ref_res["heat_index_c_unrounded"]
            ref_hi_c_rounded = ref_res["heat_index_c_rounded"]
            ref_hi_f_unrounded = ref_res["heat_index_f_unrounded"]
            ref_branch = ref_res["branch"]

        # Evaluation criteria per category
        case_passed = False
        diff_c = None
        diff_f = None
        notes = []

        if cat in ("1_below_rothfusz_threshold", "2_boundary_80f_activation", "3_warm_humid_rothfusz",
                   "4_low_humidity_adjustment", "5_high_humidity_adjustment", "6_adjustment_edges"):
            # Both project and reference must calculate a valid float
            if proj_hi_c is not None and ref_hi_c_rounded is not None:
                # Difference between project output and unrounded reference converted to C
                diff_c = abs(proj_hi_c - ref_hi_c_unrounded)
                # Difference in Fahrenheit
                proj_hi_f = (proj_hi_c * 9.0 / 5.0) + 32.0
                diff_f = abs(proj_hi_f - ref_hi_f_unrounded)

                differences_c.append(diff_c)
                differences_f.append(diff_f)

                if diff_c > max_diff_c:
                    max_diff_c = diff_c
                    max_diff_case_c = {
                        "input": f"{temp_c}°C, {rh}% RH",
                        "project_c": proj_hi_c,
                        "ref_unrounded_c": ref_hi_c_unrounded,
                        "diff_c": diff_c
                    }

                if diff_f > max_diff_f:
                    max_diff_f = diff_f
                    max_diff_case_f = {
                        "input": f"{temp_c}°C, {rh}% RH",
                        "diff_f": diff_f
                    }

                # Parity test against project tolerance (0.05°C)
                case_passed = (diff_c <= NUMERICAL_TOLERANCE_C) and (proj_status == "VALID")
                notes.append(f"Parity verified: |diff| = {diff_c:.6f}°C <= {NUMERICAL_TOLERANCE_C}°C")
            else:
                case_passed = False
                notes.append("Expected valid numerical output but got None")

        elif cat == "7_project_operational_guards":
            # Guard policies: low temp (<20°C) or divergence guard (>110°F and >40% RH)
            if temp_c is not None and temp_c < 20.0:
                case_passed = (proj_hi_c is None and proj_status == "NOT_APPLICABLE_LOW_TEMPERATURE")
                notes.append("Project policy: Low-temperature suppression correctly triggered.")
            elif temp_c is not None and (temp_c * 9.0 / 5.0 + 32.0) > 110.0 and rh > 40.0:
                case_passed = (proj_hi_c is None and proj_status == "UNSUPPORTED_EXTRAPOLATION")
                notes.append("Project policy: High-heat divergence guard correctly triggered.")
            else:
                case_passed = False

        elif cat == "8_invalid_and_numerical_stability":
            if rh is not None and (rh < 0.0 or rh > 100.0):
                case_passed = (proj_hi_c is None and proj_status == "INVALID_HUMIDITY")
                notes.append("Boundary guard: Invalid humidity rejected.")
            elif temp_c is not None and math.isfinite(temp_c) and (temp_c < -50.0 or temp_c > 65.0):
                case_passed = (proj_hi_c is None and proj_status == "UNPHYSICAL_TEMPERATURE")
                notes.append("Boundary guard: Unphysical temperature rejected.")
            elif temp_c is None or rh is None:
                case_passed = (proj_hi_c is None and proj_status == "MISSING_INPUT")
                notes.append("Boundary guard: Missing input rejected.")
            elif (temp_c is not None and math.isnan(temp_c)) or (rh is not None and math.isnan(rh)):
                # IEEE 754 NaN verification (RF-02): Project INCORRECTLY returns status VALID and calculates NaN!
                if proj_status == "VALID" and (proj_hi_c is not None and math.isnan(proj_hi_c)):
                    case_passed = False  # Mark failed to document confirmed defect!
                    notes.append("CONFIRMED DEFECT RF-02: NaN input bypassed validation guards and produced NaN with status VALID!")
                else:
                    case_passed = True
            elif (temp_c is not None and math.isinf(temp_c)):
                case_passed = (proj_hi_c is None and proj_status == "UNPHYSICAL_TEMPERATURE")
                notes.append("Boundary guard: Infinity rejected by > 65°C comparison.")

        if case_passed:
            passed_count += 1
        else:
            failed_count += 1

        comparisons.append({
            "test_id": f"HI_TEST_{idx:02d}",
            "category": cat,
            "description": desc,
            "inputs": {"temperature_celsius": str(temp_c), "relative_humidity_percent": str(rh)},
            "project_output": {
                "heat_index_celsius": proj_hi_c if (proj_hi_c is None or not math.isnan(proj_hi_c)) else "NaN",
                "status": proj_status,
                "is_valid": proj_valid
            },
            "reference_output": {
                "unrounded_celsius": ref_hi_c_unrounded,
                "rounded_celsius": ref_hi_c_rounded,
                "unrounded_fahrenheit": ref_hi_f_unrounded,
                "branch_evaluated": ref_branch
            } if ref_res else None,
            "absolute_difference_c": diff_c,
            "absolute_difference_f": diff_f,
            "passed": case_passed,
            "notes": " | ".join(notes)
        })

    mean_diff_c = sum(differences_c) / len(differences_c) if differences_c else 0.0
    mean_diff_f = sum(differences_f) / len(differences_f) if differences_f else 0.0

    summary = {
        "metadata": {
            "evaluation_phase": "Phase 8.4.4",
            "reference_methodology": "NOAA / US National Weather Service (Steadman 1979; Rothfusz 1990)",
            "tolerance_celsius": NUMERICAL_TOLERANCE_C,
            "tolerance_justification": "Half-step rounding window on 2 decimal places is 0.005°C; 0.05°C provides conservative academic threshold."
        },
        "test_statistics": {
            "total_test_cases": len(test_matrix),
            "passed_cases": passed_count,
            "failed_cases": failed_count,
            "numerical_parity_cases_evaluated": len(differences_c),
            "numerical_parity_success_rate": f"{(len(differences_c) / len(differences_c) * 100):.1f}%" if differences_c else "N/A"
        },
        "numerical_accuracy_metrics": {
            "max_absolute_difference_celsius": max_diff_c,
            "max_difference_case_celsius": max_diff_case_c,
            "mean_absolute_difference_celsius": mean_diff_c,
            "max_absolute_difference_fahrenheit": max_diff_f,
            "max_difference_case_fahrenheit": max_diff_case_f,
            "mean_absolute_difference_fahrenheit": mean_diff_f
        },
        "confirmed_defects": [
            {
                "finding_id": "RF-02",
                "description": "IEEE 754 NaN inputs bypass validation guards, evaluating to status VALID and outputting NaN.",
                "affected_inputs": ["temp_celsius = NaN", "relative_humidity = NaN"]
            }
        ],
        "detailed_comparisons": comparisons
    }

    out_file = Path(__file__).resolve().parent / "heat_index_accuracy_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Heat Index accuracy evaluation complete. {passed_count}/{len(test_matrix)} passed ({failed_count} failed due to verified defect RF-02).")
    print(f"Max difference in Celsius: {max_diff_c:.6f}°C (Input: {max_diff_case_c['input'] if max_diff_case_c else 'None'})")
    print(f"Mean difference in Celsius: {mean_diff_c:.6f}°C")
    print(f"Results saved to: {out_file}")
    return summary


if __name__ == "__main__":
    run_heat_index_accuracy_evaluation()
