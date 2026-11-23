# Phase 7.4 / 7.4.2 / 7.4.3 — Heat-Index Boundary-Value Verification Report

**Project:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Document:** `docs/academic_validation/PHASE_7_4_BOUNDARY_VALIDATION_REPORT.md`  
**Execution Date:** November 2026 (Phase 7.4.3 High-Precision Verified Edition)  
**Auditor:** Academic Technical Review Team  
**Workspace:** `C:\Users\pky45\.gemini\antigravity\scratch\urban-microclimate-hbase`  
**Official Reference Specification:** [NOAA/NCEP Weather Prediction Center (WPC) The Heat Index Equation](https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml)  

---

## 1. Executive Summary & Verification Scope

In accordance with Phase 7.4, 7.4.1, and 7.4.2 requirements, this investigation evaluates the numerical precision, branch transitions, and operational safeguards of the National Weather Service (NWS) Heat Index calculation (`assess_heat_index`) with an exhaustive **boundary-value analysis**.

### Phase 7.4.2 Evolution & Scope Corrections:
1. **Full-Pipeline Branch Correction (TC-TB-11 & TC-TB-12):**  
   Under Phase 7.4.1, test cases TC-TB-11 ($80.00^\circ\text{F}$) and TC-TB-12 ($80.01^\circ\text{F}$) were initially marked as failures because the test harness expected `ROTHFUSZ_LOW_RH_ADJUSTED` based on the nominal sub-rule interval $80.0^\circ\text{F} \le T_F \le 112.0^\circ\text{F}$. Phase 7.4.2 corrects this expectation to `STEADMAN_PRELIMINARY_AVERAGE`. In the complete hierarchical NOAA/NWS calculation pipeline, the preliminary averaging condition ($\text{HI}_{\text{avg}} < 80.0^\circ\text{F}$) executes prior to the Rothfusz regression. Because $\text{HI}_{\text{avg}} \approx 79.09^\circ\text{F} < 80.0^\circ\text{F}$ for both cases, Steadman's linear preliminary equation is returned directly. TC-TB-11 and TC-TB-12 were therefore **test-expectation specification errors, not application calculation failures**.
2. **Effective Activation-Threshold Verification (TC-TB-13, TC-TB-14, TC-TB-15):**  
   To verify the exact ambient temperature where low-RH adjustment actually activates in the full pipeline, the threshold was derived from $\text{HI}_{\text{avg}} = 1.05 \cdot T_F - 5.15 + 0.0235 \cdot \text{RH} = 80.0^\circ\text{F}$. At $\text{RH} = 10.0\%$, the effective threshold is $T_{F,\text{thresh}} = 84.915 / 1.05 = 80.871429^\circ\text{F}$ ($T_C \approx 27.150794^\circ\text{C}$). Three cases were evaluated (just below, at, and just above threshold) to confirm pipeline branch switching.
3. **Formal Distinction of Engineering Guards vs. NOAA Rules:**  
   The project enforces explicit operational safeguards ($T < 20^\circ\text{C}$ suppression, $[-50, 65]^\circ\text{C}$ operational range, $[0, 100]\%$ humidity limits, and $T > 110^\circ\text{F}$ with $\text{RH} > 40\%$ divergence guards). These are documented as **project-specific engineering safety policies**, explicitly distinguished from official NOAA meteorological standards.

---

## 2. Independent Reference Boundary Implementation

The boundary verification test suite was executed using `docs/academic_validation/scripts/verify_heat_index_boundary_values.py`. The reference algorithm implements NOAA/NWS technical specifications (Steadman 1979; Rothfusz 1990; WPC 2014) strictly from first principles without importing or relying upon `app.services.sensor_simulator`:

```python
def independent_nws_heat_index(temp_celsius: float, relative_humidity: float) -> Tuple[float, float, str, float]:
    t_f = (temp_celsius * 9.0 / 5.0) + 32.0
    rh = relative_humidity

    # 1. Steadman preliminary simple equation
    hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))

    # 2. Steadman averaging step
    hi_avg = 0.5 * (hi_simple + t_f)

    # 3. Official NOAA Branching Condition at 80 deg F
    # If averaged preliminary calculation is below 80 deg F, it is used directly
    if hi_avg < 80.0:
        hi_c_unrounded = (hi_avg - 32.0) * 5.0 / 9.0
        return hi_c_unrounded, round(hi_c_unrounded, 2), "STEADMAN_PRELIMINARY_AVERAGE", hi_avg

    # 4. Full 9-term Rothfusz polynomial regression (executed only when hi_avg >= 80.0)
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

    # 5. Low-RH adjustment: rh < 13.0 and 80.0 <= t_f <= 112.0
    if rh < 13.0 and 80.0 <= t_f <= 112.0:
        adj = ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(t_f - 95.0)) / 17.0)
        hi_f -= adj
        branch = "ROTHFUSZ_LOW_RH_ADJUSTED"
    # 6. High-RH adjustment: rh > 85.0 and 80.0 <= t_f <= 87.0
    elif rh > 85.0 and 80.0 <= t_f <= 87.0:
        adj = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
        hi_f += adj
        branch = "ROTHFUSZ_HIGH_RH_ADJUSTED"

    hi_c_unrounded = (hi_f - 32.0) * 5.0 / 9.0
    return hi_c_unrounded, round(hi_c_unrounded, 2), branch, hi_avg
```

---

## 3. Actual Execution Log and Evidence

### Execution Command:
```powershell
cd 'C:\Users\pky45\.gemini\antigravity\scratch\urban-microclimate-hbase'
python docs/academic_validation/scripts/verify_heat_index_boundary_values.py
```

### Actual Console Output (Verbatim):
```
========================================================================================================================
TASK 1: NWS PRELIMINARY THRESHOLD (80.0 deg F AVERAGED HI BOUNDARY)
Investigating Branch Selection and Mathematical Discontinuity Around Threshold
========================================================================================================================
Case ID    | Target HI_avg  | Temp (C)   | RH (%) | Ref Branch                   | App Branch                   | Ref Val  | App Val  | Diff (|Delta|) | Status
------------------------------------------------------------------------------------------------------------------------
TC-TH-01   | 79.99          | 26.6481    | 50.0   | STEADMAN_PRELIMINARY_AVERAGE | STEADMAN_PRELIMINARY_AVERAGE | 26.66    | 26.66    | 0.001111 C     | PASS
TC-TH-02   | 80.00          | 26.6534    | 50.0   | ROTHFUSZ_FULL_REGRESSION     | ROTHFUSZ_FULL_REGRESSION     | 27.10    | 27.10    | 0.001059 C     | PASS
TC-TH-03   | 80.01          | 26.6587    | 50.0   | ROTHFUSZ_FULL_REGRESSION     | ROTHFUSZ_FULL_REGRESSION     | 27.11    | 27.11    | 0.004279 C     | PASS
------------------------------------------------------------------------------------------------------------------------
DISCONTINUITY INVESTIGATION: Step change at 80.00 deg F threshold = +0.4344 deg C (+0.7819 deg F).
Steadman preliminary linear value at 80.00 deg F: 26.6667 C | Rothfusz 9-term polynomial value: 27.1011 C.

========================================================================================================================
TASK 2: RELATIVE HUMIDITY ADJUSTMENT BOUNDARIES
Verifying Exact Inequality Application for Low-RH (< 13.0%) and High-RH (> 85.0%)
========================================================================================================================
Case ID    | Condition Tested               | Temp (C)   | RH (%)   | Ref Branch                   | App Branch                   | Ref (C)  | App (C)  | Diff         | Status
------------------------------------------------------------------------------------------------------------------------
TC-RH-01   | Low-RH: 12.99% (< 13.0, adj active) | 35.0000    | 12.99    | ROTHFUSZ_LOW_RH_ADJUSTED     | ROTHFUSZ_LOW_RH_ADJUSTED     | 32.45    | 32.45    | 0.001333 C   | PASS
TC-RH-02   | Low-RH: 13.00% (= 13.0, adj inactive) | 35.0000    | 13.00    | ROTHFUSZ_FULL_REGRESSION     | ROTHFUSZ_FULL_REGRESSION     | 32.45    | 32.45    | 0.000585 C   | PASS
TC-RH-03   | Low-RH: 13.01% (> 13.0, adj inactive) | 35.0000    | 13.01    | ROTHFUSZ_FULL_REGRESSION     | ROTHFUSZ_FULL_REGRESSION     | 32.45    | 32.45    | 0.001114 C   | PASS
TC-RH-04   | High-RH: 84.99% (< 85.0, adj inactive) | 28.8889    | 84.99    | ROTHFUSZ_FULL_REGRESSION     | ROTHFUSZ_FULL_REGRESSION     | 35.52    | 35.52    | 0.001179 C   | PASS
TC-RH-05   | High-RH: 85.00% (= 85.0, adj inactive) | 28.8889    | 85.00    | ROTHFUSZ_FULL_REGRESSION     | ROTHFUSZ_FULL_REGRESSION     | 35.52    | 35.52    | 0.003436 C   | PASS
TC-RH-06   | High-RH: 85.01% (> 85.0, adj active) | 28.8889    | 85.01    | ROTHFUSZ_HIGH_RH_ADJUSTED    | ROTHFUSZ_HIGH_RH_ADJUSTED    | 35.53    | 35.53    | 0.003974 C   | PASS
------------------------------------------------------------------------------------------------------------------------
Task 2 Summary: All 6 RH adjustment boundary conditions evaluated successfully.

==========================================================================================================================================================================
TASK 3: TEMPERATURE ADJUSTMENT BOUNDARIES & EFFECTIVE ACTIVATION
Verifying Temperature Bounds, Nominal Eligibility vs. Pipeline Activation, and Effective Thresholds
==========================================================================================================================================================================
Case ID    | Condition Tested                   | Temp (F)  | Temp (C)  | RH%   | HI_avg (F) | Ref Branch                   | App Branch                   | Ref(C) | App(C) | Diff       | Nom Elig | Pipe Act | Status
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------
TC-TB-01   | Low-RH Temp: 111.99 F (<= 112, active) | 111.9900  | 44.4389   | 10.0  | 112.6745   | ROTHFUSZ_LOW_RH_ADJUSTED     | ROTHFUSZ_LOW_RH_ADJUSTED     | 41.51  | 41.51  | 0.002310 C | YES      | YES      | PASS
TC-TB-02   | Low-RH Temp: 112.00 F (<= 112, active) | 112.0000  | 44.4444   | 10.0  | 112.6850   | ROTHFUSZ_LOW_RH_ADJUSTED     | ROTHFUSZ_LOW_RH_ADJUSTED     | 41.53  | 41.53  | 0.001680 C | YES      | YES      | PASS
TC-TB-03   | Low-RH Temp: 112.01 F (> 112, inactive) | 112.0100  | 44.4500   | 10.0  | 112.6955   | ROTHFUSZ_FULL_REGRESSION     | ROTHFUSZ_FULL_REGRESSION     | 41.53  | 41.53  | 0.004225 C | NO       | NO       | PASS
TC-TB-04   | High-RH Temp: 79.99 F (< 80, inactive) | 79.9900   | 26.6611   | 90.0  | 80.9545    | ROTHFUSZ_FULL_REGRESSION     | ROTHFUSZ_FULL_REGRESSION     | 29.79  | 29.79  | 0.004220 C | NO       | NO       | PASS
TC-TB-05   | High-RH Temp: 80.00 F (>= 80, active) | 80.0000   | 26.6667   | 90.0  | 80.9650    | ROTHFUSZ_HIGH_RH_ADJUSTED    | ROTHFUSZ_HIGH_RH_ADJUSTED    | 30.19  | 30.19  | 0.000060 C | YES      | YES      | PASS
TC-TB-06   | High-RH Temp: 80.01 F (>= 80, active) | 80.0100   | 26.6722   | 90.0  | 80.9755    | ROTHFUSZ_HIGH_RH_ADJUSTED    | ROTHFUSZ_HIGH_RH_ADJUSTED    | 30.20  | 30.20  | 0.004665 C | YES      | YES      | PASS
TC-TB-07   | High-RH Temp: 86.99 F (<= 87, active) | 86.9900   | 30.5500   | 90.0  | 88.3045    | ROTHFUSZ_HIGH_RH_ADJUSTED    | ROTHFUSZ_HIGH_RH_ADJUSTED    | 42.86  | 42.86  | 0.001984 C | YES      | YES      | PASS
TC-TB-08   | High-RH Temp: 87.00 F (<= 87, active) | 87.0000   | 30.5556   | 90.0  | 88.3150    | ROTHFUSZ_HIGH_RH_ADJUSTED    | ROTHFUSZ_HIGH_RH_ADJUSTED    | 42.88  | 42.88  | 0.000453 C | YES      | YES      | PASS
TC-TB-09   | High-RH Temp: 87.01 F (> 87, inactive) | 87.0100   | 30.5611   | 90.0  | 88.3255    | ROTHFUSZ_FULL_REGRESSION     | ROTHFUSZ_FULL_REGRESSION     | 42.90  | 42.90  | 0.001644 C | NO       | NO       | PASS
TC-TB-10   | Low-RH Temp: 79.99 F (< 80, inactive) | 79.9900   | 26.6611   | 10.0  | 79.0745    | STEADMAN_PRELIMINARY_AVERAGE | STEADMAN_PRELIMINARY_AVERAGE | 26.15  | 26.15  | 0.002500 C | NO       | NO       | PASS
TC-TB-11   | Low-RH Temp: 80.00 F (>= 80, shadowed) | 80.0000   | 26.6667   | 10.0  | 79.0850    | STEADMAN_PRELIMINARY_AVERAGE | STEADMAN_PRELIMINARY_AVERAGE | 26.16  | 26.16  | 0.001667 C | YES      | NO       | PASS
TC-TB-12   | Low-RH Temp: 80.01 F (>= 80, shadowed) | 80.0100   | 26.6722   | 10.0  | 79.0955    | STEADMAN_PRELIMINARY_AVERAGE | STEADMAN_PRELIMINARY_AVERAGE | 26.16  | 26.16  | 0.004167 C | YES      | NO       | PASS
TC-TB-13   | Low-RH Eff Act: Below (HI_avg < 80) | 80.8614   | 27.1452   | 10.0  | 79.9895    | STEADMAN_PRELIMINARY_AVERAGE | STEADMAN_PRELIMINARY_AVERAGE | 26.66  | 26.66  | 0.000833 C | YES      | NO       | PASS
TC-TB-14   | Low-RH Eff Act: At Thresh (HI_avg = 80) | 80.8714   | 27.1508   | 10.0  | 80.0000    | ROTHFUSZ_LOW_RH_ADJUSTED     | ROTHFUSZ_LOW_RH_ADJUSTED     | 25.80  | 25.80  | 0.002682 C | YES      | YES      | PASS
TC-TB-15   | Low-RH Eff Act: Above (HI_avg > 80) | 80.8814   | 27.1563   | 10.0  | 80.0105    | ROTHFUSZ_LOW_RH_ADJUSTED     | ROTHFUSZ_LOW_RH_ADJUSTED     | 25.81  | 25.81  | 0.003527 C | YES      | YES      | PASS
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Task 3 Summary: 15 temperature adjustment boundary conditions evaluated.
SCIENTIFIC OBSERVATION & PHASE 7.4.2 CORRECTION (Low-RH Lower Bound Shadowing & Effective Activation):
  1. Nominal Sub-Rule vs Full Pipeline:
     The nominal lower bound (80.0 <= T_F <= 112.0) describes the regression adjustment envelope, but under
     official NOAA NWS methodology (https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml), the preliminary
     averaging check (HI_avg < 80.0 F) executes FIRST. If HI_avg < 80.0 F, Steadman is used directly.
  2. Shadowing at 80.0 F for Low RH:
     At RH = 10.0% and T_F = 80.00 F, HI_avg = 79.0850 F < 80.0 F. The flow branches to STEADMAN_PRELIMINARY_AVERAGE.
     Nominal adjustment condition is met (80 <= T_F <= 112), but actual pipeline activation is INACTIVE.
     TC-TB-11 and TC-TB-12 expected branches are corrected to STEADMAN_PRELIMINARY_AVERAGE (PASS).
  3. Effective Activation Threshold at RH = 10.0%:
     Derived mathematically: HI_avg = 1.05 * T_F - 4.915 = 80.0 F => T_F,thresh = 84.915 / 1.05 = 80.871429 F (27.150794 C).
     - Just below (T_F = 80.861429 F, HI_avg = 79.9895 F): STEADMAN_PRELIMINARY_AVERAGE (PASS)
     - At threshold (T_F = 80.871429 F, HI_avg = 80.0000 F): ROTHFUSZ_LOW_RH_ADJUSTED (PASS)
     - Just above (T_F = 80.881429 F, HI_avg = 80.0105 F): ROTHFUSZ_LOW_RH_ADJUSTED (PASS)

============================================================================================================================================
PHASE 7.4.3: HIGH-PRECISION FLOATING-POINT THRESHOLD & BRANCH AUDIT (TC-TB-13, TC-TB-14, TC-TB-15)
Verifying Exact Inputs (>= 12 decimals), Intermediate HI_avg, Threshold Comparison, and Routing Integrity
Exact Threshold Formula: (80.0 + 5.15 - 0.0235 * 10.0) / 1.05 = 80.8714285714285808 F
Documented Epsilon: +-0.01 F (+-0.005556 C)
============================================================================================================================================
[TC-TB-13] Scenario: Low-RH Eff Act: Below (HI_avg < 80)
  1. Actual Temp passed to Reference (C):        27.14523809523810
  2. Actual Temp passed to Application (C):      27.14523809523810
  3. Calculated Preliminary HI_avg (F):          79.98950000000001
  4. Difference vs 80.0 F Threshold (HI_avg-80): -1.04999999999933e-02
  5. Comparison 'HI_avg >= 80.0':                False  (HI_avg < 80.0: True)
  6. Reference and Application Inputs Equal:     True (Bitwise identical float)
     Application Returned Message:               'Calculated via NWS Steadman preliminary equation (hi_avg < 80°F).'
     Application Returned Heat Index (C):        26.66 C
     Reference Selected Branch:                  STEADMAN_PRELIMINARY_AVERAGE
  7. Genuine Rothfusz Routing Confirmed:         N/A (Correctly Routed to Steadman)
     Mechanism: In app/services/sensor_simulator.py:103, 'if hi_avg < 80.0' evaluates to True.
--------------------------------------------------------------------------------------------------------------------------------------------
[TC-TB-14] Scenario: Low-RH Eff Act: At Thresh (HI_avg = 80)
  1. Actual Temp passed to Reference (C):        27.15079365079366
  2. Actual Temp passed to Application (C):      27.15079365079366
  3. Calculated Preliminary HI_avg (F):          80.00000000000000
  4. Difference vs 80.0 F Threshold (HI_avg-80): +0.00000000000000e+00
  5. Comparison 'HI_avg >= 80.0':                True  (HI_avg < 80.0: False)
  6. Reference and Application Inputs Equal:     True (Bitwise identical float)
     Application Returned Message:               'Calculated via NWS Rothfusz regression polynomial (hi_avg >= 80°F).'
     Application Returned Heat Index (C):        25.8 C
     Reference Selected Branch:                  ROTHFUSZ_LOW_RH_ADJUSTED
  7. Genuine Rothfusz Routing Confirmed:         True
     Mechanism: In app/services/sensor_simulator.py:103, 'if hi_avg < 80.0' evaluates to False.
     CRITICAL CONFIRMATION: At exact threshold, hi_avg evaluates to exactly 80.00000000000000 in IEEE-754.
     Because 80.0 < 80.0 is False, the Steadman return block is bypassed BEFORE any display rounding.
     The code falls through to Rothfusz regression (line 112) and executes the low-RH adjustment (line 135).
     Therefore, TC-TB-14 reaches the Rothfusz branch genuinely by mathematical logic, NOT by rounded display.
--------------------------------------------------------------------------------------------------------------------------------------------
[TC-TB-15] Scenario: Low-RH Eff Act: Above (HI_avg > 80)
  1. Actual Temp passed to Reference (C):        27.15634920634922
  2. Actual Temp passed to Application (C):      27.15634920634922
  3. Calculated Preliminary HI_avg (F):          80.01050000000001
  4. Difference vs 80.0 F Threshold (HI_avg-80): +1.05000000000075e-02
  5. Comparison 'HI_avg >= 80.0':                True  (HI_avg < 80.0: False)
  6. Reference and Application Inputs Equal:     True (Bitwise identical float)
     Application Returned Message:               'Calculated via NWS Rothfusz regression polynomial (hi_avg >= 80°F).'
     Application Returned Heat Index (C):        25.81 C
     Reference Selected Branch:                  ROTHFUSZ_LOW_RH_ADJUSTED
  7. Genuine Rothfusz Routing Confirmed:         True
     Mechanism: In app/services/sensor_simulator.py:103, 'if hi_avg < 80.0' evaluates to False.
--------------------------------------------------------------------------------------------------------------------------------------------
Phase 7.4.3 Precision Audit Summary:
  - TC-TB-13 (tf = threshold - 0.01 F): HI_avg = 79.98950000000001 F < 80.0 F => Steadman Preliminary (Genuine)
  - TC-TB-14 (tf = exact threshold):    HI_avg = 80.00000000000000 F >= 80.0 F => Rothfusz Low-RH Adjusted (Genuine)
  - TC-TB-15 (tf = threshold + 0.01 F): HI_avg = 80.01050000000001 F > 80.0 F => Rothfusz Low-RH Adjusted (Genuine)
  - Floating-Point Limitation Note: Although exact threshold evaluation is clean and unambiguous (+0.0000e+00 diff),
    the bracketing cases TC-TB-13 (-0.01 F) and TC-TB-15 (+0.01 F) provide the definitive mathematical proof of
    branch transition across the 80.0 F threshold without depending on exact floating-point equality.

========================================================================================================================
TASK 4: PROJECT-SPECIFIC POLICY BOUNDARY VALUES
Verifying Operational Guard Cutoffs, Physical Boundaries, and Status Flags
========================================================================================================================
Case ID    | Test Scenario                        | Temp (C)   | RH (%)   | Exp Val  | Act Val  | Exp Status                     | Act Status                     | Result
------------------------------------------------------------------------------------------------------------------------
TC-PB-01   | Low-Temp: 19.99 C (67.98 F < 68.0 F) | 19.99      | 50.00    | None     | None     | NOT_APPLICABLE_LOW_TEMPERATURE | NOT_APPLICABLE_LOW_TEMPERATURE | PASS
TC-PB-02   | Low-Temp: 20.00 C (68.00 F >= 68.0 F | 20.00      | 50.00    | 19.68    | 19.68    | VALID                          | VALID                          | PASS
TC-PB-03   | Low-Temp: 20.01 C (68.02 F >= 68.0 F | 20.01      | 50.00    | 19.69    | 19.69    | VALID                          | VALID                          | PASS
TC-PB-04   | Divergence: 110.00 F at RH 45% (<= 1 | 43.33      | 45.00    | 61.91    | 61.91    | VALID                          | VALID                          | PASS
TC-PB-05   | Divergence: 110.01 F at RH 45% (> 11 | 43.34      | 45.00    | None     | None     | UNSUPPORTED_EXTRAPOLATION      | UNSUPPORTED_EXTRAPOLATION      | PASS
TC-PB-06   | Operational Max: 65.00 C (<= 65.0 C) | 65.00      | 20.00    | 93.90    | 93.9     | VALID                          | VALID                          | PASS
TC-PB-07   | Operational Max: 65.01 C (> 65.0 C)  | 65.01      | 20.00    | None     | None     | UNPHYSICAL_TEMPERATURE         | UNPHYSICAL_TEMPERATURE         | PASS
TC-PB-08   | Operational Min: -50.00 C (>= -50.0  | -50.00     | 50.00    | None     | None     | NOT_APPLICABLE_LOW_TEMPERATURE | NOT_APPLICABLE_LOW_TEMPERATURE | PASS
TC-PB-09   | Operational Min: -50.01 C (< -50.0 C | -50.01     | 50.00    | None     | None     | UNPHYSICAL_TEMPERATURE         | UNPHYSICAL_TEMPERATURE         | PASS
TC-PB-10   | Humidity Min: -0.01% (< 0.0%)        | 30.00      | -0.01    | None     | None     | INVALID_HUMIDITY               | INVALID_HUMIDITY               | PASS
TC-PB-11   | Humidity Min: 0.00% (>= 0.0%)        | 30.00      | 0.00     | 27.24    | 27.24    | VALID                          | VALID                          | PASS
TC-PB-12   | Humidity Max: 100.00% (<= 100.0%)    | 30.00      | 100.00   | 44.36    | 44.36    | VALID                          | VALID                          | PASS
TC-PB-13   | Humidity Max: 100.01% (> 100.0%)     | 30.00      | 100.01   | None     | None     | INVALID_HUMIDITY               | INVALID_HUMIDITY               | PASS
------------------------------------------------------------------------------------------------------------------------
Task 4 Summary: All 13 policy boundary conditions evaluated successfully.

========================================================================================================================
OVERALL BOUNDARY VALIDATION SUMMARY: 37 / 37 cases PASSED (0 FAILED).
MAXIMUM OBSERVED NUMERICAL DIFFERENCE (|Delta|): 0.004665 deg C (Project Tolerance: 0.05 deg C).
========================================================================================================================
```

---

## 4. In-Depth Boundary Analysis & Scientific Findings

### 4.1 Task 1: NWS Preliminary Averaged Threshold & Mathematical Discontinuity

The NWS protocol dictates that if $\text{HI}_{\text{avg}} < 80.0^\circ\text{F}$, the heat index is reported directly as $\text{HI}_{\text{avg}}$ (derived from the linear Steadman equation). If $\text{HI}_{\text{avg}} \ge 80.0^\circ\text{F}$, the system switches to the 9-term second-order Rothfusz polynomial regression.

#### Numerical Findings:
At $\text{RH} = 50.0\%$, the threshold condition $\text{HI}_{\text{avg}} = 80.00^\circ\text{F}$ occurs at ambient temperature $T_F = (80.00 + 3.975) / 1.05 = 79.9762^\circ\text{F}$ ($T_C \approx 26.6534^\circ\text{C}$).

| Test Case | $\text{HI}_{\text{avg}}$ ($^\circ\text{F}$) | Ambient $T_C$ ($^\circ\text{C}$) | Executed Branch | Reference Unrounded ($^\circ\text{C}$) | Application Output ($^\circ\text{C}$) | Full-Precision Absolute Error ($|\Delta|$) | Status |
|:---|:---:|:---:|:---|:---:|:---:|:---:|:---:|
| **TC-TH-01** | 79.99 | 26.6481 | `STEADMAN_PRELIMINARY_AVERAGE` | 26.6611 | 26.66 | 0.001111°C | **PASS** |
| **TC-TH-02** | 80.00 | 26.6534 | `ROTHFUSZ_FULL_REGRESSION` | 27.1011 | 27.10 | 0.001059°C | **PASS** |
| **TC-TH-03** | 80.01 | 26.6587 | `ROTHFUSZ_FULL_REGRESSION` | 27.1143 | 27.11 | 0.004279°C | **PASS** |

#### Discovery of Step Discontinuity:
A mathematical step discontinuity of **$+0.4344^\circ\text{C}$ ($+0.7819^\circ\text{F}$)** exists at the $80.00^\circ\text{F}$ boundary:
- Evaluating Steadman's preliminary equation at $\text{HI}_{\text{avg}} = 80.00^\circ\text{F}$:  
  $$\text{HI}_{\text{Steadman}} = 80.0000^\circ\text{F} = 26.6667^\circ\text{C}$$
- Evaluating Rothfusz's 9-term polynomial at the exact same conditions ($T_F = 79.9762^\circ\text{F}, \text{RH} = 50.0\%$):  
  $$\text{HI}_{\text{Rothfusz}} = 80.7819^\circ\text{F} = 27.1011^\circ\text{C}$$
- Step Change:  
  $$\Delta \text{HI} = 27.1011^\circ\text{C} - 26.6667^\circ\text{C} = +0.4344^\circ\text{C}$$

**Significance:** This step change is an inherent mathematical artifact of NOAA's piecewise empirical fit (connecting Steadman's 1979 linear table approximation with Rothfusz's 1990 multivariate regression). Both the application code and the independent reference implementation faithfully adhere to NOAA's exact branching threshold (`hi_avg < 80.0` vs `hi_avg >= 80.0`).

---

### 4.2 Task 2: Relative Humidity Adjustment Boundaries

The NWS specification defines two conditional corrections to the Rothfusz regression:
1. **Low-RH Adjustment:** Applied when $\text{RH} < 13.0\%$ and $80.0^\circ\text{F} \le T_F \le 112.0^\circ\text{F}$.
2. **High-RH Adjustment:** Applied when $\text{RH} > 85.0\%$ and $80.0^\circ\text{F} \le T_F \le 87.0^\circ\text{F}$.

#### Strict Inequality Verification:
- **Low-RH Boundary:**
  - $\text{RH} = 12.99\%$: Branch selected was `ROTHFUSZ_LOW_RH_ADJUSTED`. Adjustment active.
  - $\text{RH} = 13.00\%$: Branch selected was `ROTHFUSZ_FULL_REGRESSION`. Adjustment inactive.
  - $\text{RH} = 13.01\%$: Branch selected was `ROTHFUSZ_FULL_REGRESSION`. Adjustment inactive.
  - **Conclusion:** The low-RH condition is strictly enforced as $\text{RH} < 13.0$, rejecting $\text{RH} \le 13.0$.
- **High-RH Boundary:**
  - $\text{RH} = 84.99\%$: Branch selected was `ROTHFUSZ_FULL_REGRESSION`. Adjustment inactive.
  - $\text{RH} = 85.00\%$: Branch selected was `ROTHFUSZ_FULL_REGRESSION`. Adjustment inactive.
  - $\text{RH} = 85.01\%$: Branch selected was `ROTHFUSZ_HIGH_RH_ADJUSTED`. Adjustment active.
  - **Conclusion:** The high-RH condition is strictly enforced as $\text{RH} > 85.0$, rejecting $\text{RH} \ge 85.0$.

All 6 test cases passed with absolute numerical errors between $0.000585^\circ\text{C}$ and $0.003974^\circ\text{C}$.

---

### 4.3 Task 3: Temperature Adjustment Boundaries & Phase 7.4.2 Corrected Activation Analysis

Task 3 tested the temperature bounds governing the activation of the RH adjustments across both upper and lower operational limits, and verified the effective pipeline activation threshold:

#### 1. Low-RH Temperature Upper Bounds ($112.0^\circ\text{F}$ at $\text{RH} = 10.0\%$):
- $T_F = 111.99^\circ\text{F}$: Active (`ROTHFUSZ_LOW_RH_ADJUSTED`, Pipe Act: YES) $\rightarrow 41.51^\circ\text{C}$ (Diff: $0.002310^\circ\text{C}$). (**PASS**)
- $T_F = 112.00^\circ\text{F}$: Active (`ROTHFUSZ_LOW_RH_ADJUSTED`, Pipe Act: YES) $\rightarrow 41.53^\circ\text{C}$ (Diff: $0.001680^\circ\text{C}$). (**PASS**)
- $T_F = 112.01^\circ\text{F}$: Inactive (`ROTHFUSZ_FULL_REGRESSION`, Pipe Act: NO) $\rightarrow 41.53^\circ\text{C}$ (Diff: $0.004225^\circ\text{C}$). (**PASS**)

#### 2. High-RH Temperature Bounds ($80.0^\circ\text{F} \le T_F \le 87.0^\circ\text{F}$ at $\text{RH} = 90.0\%$):
- **Lower bound at $80.0^\circ\text{F}$:**
  - $T_F = 79.99^\circ\text{F}$: Inactive (`ROTHFUSZ_FULL_REGRESSION`, Pipe Act: NO) $\rightarrow 29.79^\circ\text{C}$. (**PASS**)
  - $T_F = 80.00^\circ\text{F}$: Active (`ROTHFUSZ_HIGH_RH_ADJUSTED`, Pipe Act: YES) $\rightarrow 30.19^\circ\text{C}$ ($+0.39^\circ\text{C}$ step jump). (**PASS**)
  - $T_F = 80.01^\circ\text{F}$: Active (`ROTHFUSZ_HIGH_RH_ADJUSTED`, Pipe Act: YES) $\rightarrow 30.20^\circ\text{C}$. (**PASS**)
- **Upper bound at $87.0^\circ\text{F}$:**
  - $T_F = 86.99^\circ\text{F}$: Active (`ROTHFUSZ_HIGH_RH_ADJUSTED`, Pipe Act: YES) $\rightarrow 42.86^\circ\text{C}$. (**PASS**)
  - $T_F = 87.00^\circ\text{F}$: Active (`ROTHFUSZ_HIGH_RH_ADJUSTED`, Pipe Act: YES) $\rightarrow 42.88^\circ\text{C}$. (**PASS**)
  - $T_F = 87.01^\circ\text{F}$: Inactive (`ROTHFUSZ_FULL_REGRESSION`, Pipe Act: NO) $\rightarrow 42.90^\circ\text{C}$. (**PASS**)
  - *Continuity Confirmation:* At $T_F = 87.0^\circ\text{F}$, the adjustment term evaluates to $((90 - 85)/10) \times ((87.0 - 87.0)/5) = 0.5 \times 0.0 = 0.0^\circ\text{F}$, guaranteeing mathematical continuity across the upper boundary.

#### 3. Low-RH Temperature Nominal Lower Bounds & Shadowing (TC-TB-10, TC-TB-11, TC-TB-12 at $\text{RH} = 10.0\%$):
- **Nominal Sub-Rule Eligibility vs. Full Pipeline Activation:**  
  The clause `if rh < 13.0 and 80.0 <= t_f <= 112.0:` describes the nominal adjustment domain of the Rothfusz regression. However, per NOAA/NWS operational specifications ([WPC Heat Index Equation](https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml)), the preliminary check $\text{HI}_{\text{avg}} < 80.0^\circ\text{F}$ executes **before** entering the Rothfusz regression.
- At $T_F = 80.00^\circ\text{F}$ and $\text{RH} = 10.0\%$:
  $$\text{HI}_{\text{avg}} = 1.05 \cdot (80.0) - 5.15 + 0.0235 \cdot (10.0) = 84.00 - 5.15 + 0.235 = 79.0850^\circ\text{F} < 80.0^\circ\text{F}$$
- Because $\text{HI}_{\text{avg}} < 80.0^\circ\text{F}$, the system returns Steadman's preliminary calculation directly ($26.16^\circ\text{C}$). The low-RH adjustment is **nominally eligible** (`Nom Elig: YES`), but **pipeline inactive** (`Pipe Act: NO`).
- Correcting the test expectation to `STEADMAN_PRELIMINARY_AVERAGE` yields 100% agreement between the independent reference implementation and the application code ($|\Delta| = 0.001667^\circ\text{C} \le 0.05^\circ\text{C}$).

#### 4. Low-RH Effective Activation-Threshold Verification (TC-TB-13, TC-TB-14, TC-TB-15 at $\text{RH} = 10.0\%$):
To determine the actual temperature at which low-RH adjustment activates in the complete NWS pipeline, we solve:
$$\text{HI}_{\text{avg}} = 1.05 \cdot T_F - 5.15 + 0.0235 \cdot (10.0) = 80.0^\circ\text{F}$$
$$1.05 \cdot T_F - 4.915 = 80.0 \implies T_F = \frac{84.915}{1.05} = 80.87142857^\circ\text{F} \quad (T_C = 27.150794^\circ\text{C})$$

Testing three values around this threshold:
- **TC-TB-13 (Just Below, $T_F = 80.861429^\circ\text{F}$, $\text{HI}_{\text{avg}} = 79.9895^\circ\text{F}$):**  
  Branches to `STEADMAN_PRELIMINARY_AVERAGE` ($26.66^\circ\text{C}$). $|\Delta| = 0.000833^\circ\text{C}$. (**PASS**)
- **TC-TB-14 (At Threshold, $T_F = 80.871429^\circ\text{F}$, $\text{HI}_{\text{avg}} = 80.0000^\circ\text{F}$):**  
  Switches to `ROTHFUSZ_LOW_RH_ADJUSTED` ($25.80^\circ\text{C}$). Low-RH adjustment active! $|\Delta| = 0.002682^\circ\text{C}$. (**PASS**)
- **TC-TB-15 (Just Above, $T_F = 80.881429^\circ\text{F}$, $\text{HI}_{\text{avg}} = 80.0105^\circ\text{F}$):**  
  Continues on `ROTHFUSZ_LOW_RH_ADJUSTED` ($25.81^\circ\text{C}$). Low-RH adjustment active! $|\Delta| = 0.003527^\circ\text{C}$. (**PASS**)

#### 5. Phase 7.4.3 High-Precision Floating-Point Threshold & Routing Audit:
To confirm mathematical rigor and rule out any artifact of rounded display or altered expectations, a full precision audit was performed on TC-TB-13, TC-TB-14, and TC-TB-15:

* **Exact Threshold Definition:**
  $$T_{F,\text{thresh}} = \frac{80.0 + 5.15 - 0.0235 \times 10.0}{1.05} = \frac{84.915}{1.05} = 80.8714285714285808^\circ\text{F} \quad (T_C = 27.1507936507936556^\circ\text{C})$$
* **Documented Epsilon:** $\epsilon = \pm 0.01^\circ\text{F}$ ($\pm 0.005556^\circ\text{C}$), placing the below-threshold and above-threshold cases unambiguously on opposite sides of the mathematical boundary.

| Metric / Audit Field | TC-TB-13 (Below Threshold) | TC-TB-14 (At Exact Threshold) | TC-TB-15 (Above Threshold) |
| :--- | :--- | :--- | :--- |
| **Input $T_F$ (Nominal)** | $80.86142857142858^\circ\text{F}$ | $80.87142857142858^\circ\text{F}$ | $80.88142857142858^\circ\text{F}$ |
| **1. Temp passed to Ref ($T_C$)** | `27.14523809523810` | `27.15079365079366` | `27.15634920634922` |
| **2. Temp passed to App ($T_C$)** | `27.14523809523810` | `27.15079365079366` | `27.15634920634922` |
| **3. Calculated $\text{HI}_{\text{avg}}$ ($^\circ\text{F}$)** | `79.98950000000001` | `80.00000000000000` | `80.01050000000001` |
| **4. Difference ($\text{HI}_{\text{avg}} - 80.0^\circ\text{F}$)** | `-1.04999999999933e-02` | `+0.00000000000000e+00` | `+1.05000000000075e-02` |
| **5. Comparison `HI_avg >= 80.0`** | `False` (`HI_avg < 80.0`: `True`) | `True` (`HI_avg < 80.0`: `False`) | `True` (`HI_avg < 80.0`: `False`) |
| **6. Inputs Equivalent (`tc_ref == tc_app`)** | `True` (Bitwise identical float) | `True` (Bitwise identical float) | `True` (Bitwise identical float) |
| **Application Status & Message** | `VALID` / Steadman preliminary | `VALID` / Rothfusz regression | `VALID` / Rothfusz regression |
| **Application Heat Index ($T_C$)** | `26.66°C` | `25.80°C` | `25.81°C` |
| **Reference Executed Branch** | `STEADMAN_PRELIMINARY_AVERAGE` | `ROTHFUSZ_LOW_RH_ADJUSTED` | `ROTHFUSZ_LOW_RH_ADJUSTED` |
| **7. Genuine Rothfusz Routing Confirmed** | N/A (Correctly routed to Steadman) | **CONFIRMED GENUINE** | **CONFIRMED GENUINE** |

* **Verification of Genuine Routing for TC-TB-14:**  
  In `app/services/sensor_simulator.py:103`:
  ```python
  if hi_avg < 80.0:
      hi_c = round((hi_avg - 32.0) * 5.0 / 9.0, 2)
      return { ... }
  ```
  At TC-TB-14, the unrounded `hi_avg` evaluates in IEEE-754 double precision to exactly `80.00000000000000` (difference: `0.00000000000000e+00`). The expression `hi_avg < 80.0` strictly evaluates to `False`. Therefore, the preliminary Steadman return path is bypassed **prior to and independent of any display rounding**. Execution naturally falls through to the 9-term polynomial regression (line 124) and engages the low-humidity adjustment (line 135). TC-TB-14 genuinely reaches the Rothfusz branch through authentic mathematical execution.

* **Floating-Point Precision Limitations & Bracketing Proof:**  
  Although IEEE-754 arithmetic cleanly yields `0.0000e+00` error at the exact threshold, exact floating-point equality comparisons can theoretically be fragile across different hardware architectures or compiler optimizations. For this reason, the bracketing cases **TC-TB-13** ($\text{HI}_{\text{avg}} = 79.9895^\circ\text{F} < 80.0^\circ\text{F}$, $\Delta = -0.0105^\circ\text{F}$) and **TC-TB-15** ($\text{HI}_{\text{avg}} = 80.0105^\circ\text{F} > 80.0^\circ\text{F}$, $\Delta = +0.0105^\circ\text{F}$), separated by the documented epsilon $\epsilon = \pm 0.01^\circ\text{F}$, provide the **definitive, architecture-independent mathematical proof** of the branch transition across the boundary.

---

### 4.4 Task 4: Project-Specific Operational and Policy Boundaries

Task 4 evaluated the application's operational guards, physical range clamps, and error statuses:

1. **Low-Temperature Suppression ($T_C < 20.0^\circ\text{C}$ / $T_F < 68.0^\circ\text{F}$):**
   - $T_C = 19.99^\circ\text{C}$: Status `NOT_APPLICABLE_LOW_TEMPERATURE`, `heat_index_celsius: None`. (**PASS**)
   - $T_C = 20.00^\circ\text{C}$: Status `VALID`, `heat_index_celsius: 19.68°C` (matches reference $19.68^\circ\text{C}$). (**PASS**)
   - $T_C = 20.01^\circ\text{C}$: Status `VALID`, `heat_index_celsius: 19.69°C` (matches reference $19.69^\circ\text{C}$). (**PASS**)
2. **Extreme Divergence Guard ($T_F > 110.0^\circ\text{F}$ at $\text{RH} > 40.0\%$):**
   - $T_F = 110.00^\circ\text{F}$ at $45\%$: Status `VALID`, `heat_index_celsius: 61.91°C` (matches reference $61.91^\circ\text{C}$). (**PASS**)
   - $T_F = 110.01^\circ\text{F}$ at $45\%$: Status `UNSUPPORTED_EXTRAPOLATION`, `heat_index_celsius: None`. (**PASS**)
3. **Operational Temperature Domain Limits ($[-50.0^\circ\text{C}, 65.0^\circ\text{C}]$):**
   - $T_C = 65.00^\circ\text{C}$: Status `VALID`, `heat_index_celsius: 93.90°C` (matches reference $93.90^\circ\text{C}$). (**PASS**)
   - $T_C = 65.01^\circ\text{C}$: Status `UNPHYSICAL_TEMPERATURE`, `heat_index_celsius: None`. (**PASS**)
   - $T_C = -50.00^\circ\text{C}$: Status `NOT_APPLICABLE_LOW_TEMPERATURE`, `heat_index_celsius: None`. (**PASS**)
   - $T_C = -50.01^\circ\text{C}$: Status `UNPHYSICAL_TEMPERATURE`, `heat_index_celsius: None`. (**PASS**)
4. **Physical Relative Humidity Range ($[0.0\%, 100.0\%]$):**
   - $\text{RH} = -0.01\%$: Status `INVALID_HUMIDITY`, `heat_index_celsius: None`. (**PASS**)
   - $\text{RH} = 0.00\%$: Status `VALID`, `heat_index_celsius: 27.24°C` (matches reference $27.24^\circ\text{C}$). (**PASS**)
   - $\text{RH} = 100.00\%$: Status `VALID`, `heat_index_celsius: 44.36°C` (matches reference $44.36^\circ\text{C}$). (**PASS**)
   - $\text{RH} = 100.01\%$: Status `INVALID_HUMIDITY`, `heat_index_celsius: None`. (**PASS**)

All 13 policy boundary test cases passed with 100% agreement on status classifications and reference numerical outputs.

---

## 5. Summary of Boundary-Value Verification Metrics

| Category | Cases Tested | Passed | Failed | Maximum Absolute Difference ($|\Delta|$) | Project Parity Tolerance | Verification Result |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Task 1: NWS Preliminary Threshold** | 3 | 3 | 0 | $0.004279^\circ\text{C}$ | $0.05^\circ\text{C}$ | **CONFIRMED** |
| **Task 2: RH Adjustment Bounds** | 6 | 6 | 0 | $0.003974^\circ\text{C}$ | $0.05^\circ\text{C}$ | **CONFIRMED** |
| **Task 3: Temp Adjustment & Effective Activation** | 15 | 15 | 0 | $0.004665^\circ\text{C}$ | $0.05^\circ\text{C}$ | **CONFIRMED** |
| **Task 4: Policy & Physical Bounds** | 13 | 13 | 0 | $0.001680^\circ\text{C}$ | $0.05^\circ\text{C}$ | **CONFIRMED** |
| **TOTAL** | **37** | **37** | **0** | **$0.004665^\circ\text{C}$** | **$0.05^\circ\text{C}$** | **100% PASS** |

---

## 6. Scientific Limitations & Untested Conditions

1. **Synthetic Telemetry Constraint:**
   Boundary testing confirms exact algorithmic and policy fidelity under controlled inputs. However, because the ingestion pipeline currently runs on synthetic telemetry generated by `sensor_simulator.py`, this verification does not represent real-world physical sensor accuracy.
2. **Field Sensor Noise & Transients:**
   In real IoT deployments, physical capacitive humidity sensors (e.g., DHT22, BME280) exhibit measurement noise ($\pm 2\text{--}3\%$) and thermal lag. Near the $80.00^\circ\text{F}$ boundary, noise could trigger rapid toggling between the Steadman and Rothfusz branches, generating artificial $\approx 0.43^\circ\text{C}$ volatility.
3. **Future Hardware Recommendations:**
   For physical deployment, a small hysteresis band ($\pm 0.2^\circ\text{F}$) or moving-average filter is recommended around the $80.00^\circ\text{F}$ threshold to suppress branch-toggling jitter.

---

## 7. Safety & Integrity Confirmation

- **Application Source Code:** Unmodified.
- **HBase Tables & Schemas:** Unmodified.
- **Simulator Daemon:** Stopped.
- **Git Tree:** Working directory clean for all tracked files. All deliverables isolated to `docs/academic_validation/`.
