# Accuracy Validation Plan & Verification Protocol

**System:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Document:** `docs/academic_validation/ACCURACY_VALIDATION_PLAN.md`  
**Purpose:** Formal academic testing protocol to verify numerical accuracy, computational correctness, ingestion latency, and anomaly detection fidelity across all system tiers.  
**Edition:** Phase 7.4.2 Verified & Evidence-Backed Edition  

---

## 1. Scope, Principles & Academic Honesty Disclosures

To maintain strict scientific integrity, this verification protocol establishes three fundamental distinctions:

```
+----------------------------------------------------------------------------------------------------+
|                                    VALIDATION TAXONOMY & REGIMES                                   |
+----------------------------------------------------------------------------------------------------+
|  LEVEL A: FORMULA IMPLEMENTATION VERIFICATION (EXECUTED & EVIDENCE-BACKED)                         |
|  - Independent reference calculation of official NWS Steadman & Rothfusz (1990) equations.       |
|  - Compares independent algorithm against application's assess_heat_index() function.              |
|  - Evaluates numerical parity using a project-defined tolerance (|Delta| <= 0.05 deg C).           |
|  - Phase 7.4 Boundary Verification: 31 exhaustive boundary-value and continuity test cases.         |
+----------------------------------------------------------------------------------------------------+
|  LEVEL B: PROJECT-SPECIFIC INPUT & SAFETY-POLICY VALIDATION (EXECUTED & VERIFIED)                  |
|  - Validates operational policies designed for this system (low-temp cutoff, boundary checks).      |
|  - Tests unphysical humidity ([0, 100]%), operational limits, and polynomial divergence guards.   |
|  - Explicitly separated from official NWS calculation requirements.                                |
+----------------------------------------------------------------------------------------------------+
|  LEVEL C: REAL-WORLD EMPIRICAL ACCURACY VALIDATION (UNPERFORMED / FUTURE SCOPE)                     |
|  - Physical field validation comparing IoT sensor hardware against calibrated reference stations. |
|  - REMAINS UNPERFORMED because current telemetry is generated via mathematical simulation.        |
+----------------------------------------------------------------------------------------------------+
```

### Four-Tier Verification Life-Cycle Status
Every verification item is classified into one of four states:
- **Category A: Proposed Experimental Targets** (Formal design specifications and acceptance thresholds).
- **Category B: Tests Implemented in Codebase** (Automated test functions written in `tests/` or validation scripts).
- **Category C: Tests Actually Executed with Recorded Results** (Tests run in the environment with recorded console output).
- **Category D: Tests Still Pending** (Tests requiring live cluster infrastructure or future physical deployments).

---

## 2. Experimental Verification Protocols

### Protocol 1: Independent Heat-Index Formula Verification (Level A)
* **Status:** **Category C — Executed with Recorded Console Evidence** (7 / 7 cases passed).
* **Objective:** Independently verify the numerical accuracy of `assess_heat_index()` in `app/services/sensor_simulator.py` by comparing it against an independent reference implementation constructed from first principles without importing application internals.
* **Ground Truth Source:** NOAA Technical Attachment SR 90-23 (Rothfusz, 1990) and Steadman (1979).
* **Evaluation Metric:**
  $$\text{Absolute Numerical Error: } |\Delta| = |\text{Application Result} - \text{Independent Reference Result}|$$
* **Project-Defined Numerical Implementation Tolerance:**
  $$|\Delta| \le 0.05^\circ\text{C}$$
  *(Note: This tolerance is a project-defined verification threshold for floating-point calculation agreement, NOT an official NWS accuracy standard).*

#### Executed Benchmark Test Matrix & Recorded Results:

| Case ID | Input Temp ($T_C$) | Input Humidity ($RH$) | Reference Result ($^\circ\text{C}$) | Application Result ($^\circ\text{C}$) | Absolute Error $|\Delta|$ | Branch Exercised | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-HI-01** | $25.0^\circ\text{C}$ | $50.0\%$ | $24.93^\circ\text{C}$ | $24.93^\circ\text{C}$ | $0.0000^\circ\text{C}$ | `STEADMAN_PRELIMINARY_AVERAGE` | **PASS** |
| **TC-HI-02** | $27.0^\circ\text{C}$ | $60.0\%$ | $28.08^\circ\text{C}$ | $28.08^\circ\text{C}$ | $0.0000^\circ\text{C}$ | `ROTHFUSZ_FULL_REGRESSION` | **PASS** |
| **TC-HI-03** | $30.0^\circ\text{C}$ | $70.0\%$ | $35.04^\circ\text{C}$ | $35.04^\circ\text{C}$ | $0.0000^\circ\text{C}$ | `ROTHFUSZ_FULL_REGRESSION` | **PASS** |
| **TC-HI-04** | $32.0^\circ\text{C}$ | $80.0\%$ | $44.37^\circ\text{C}$ | $44.37^\circ\text{C}$ | $0.0000^\circ\text{C}$ | `ROTHFUSZ_FULL_REGRESSION` | **PASS** |
| **TC-HI-05** | $35.0^\circ\text{C}$ | $50.0\%$ | $40.68^\circ\text{C}$ | $40.68^\circ\text{C}$ | $0.0000^\circ\text{C}$ | `ROTHFUSZ_FULL_REGRESSION` | **PASS** |
| **TC-HI-06** | $38.0^\circ\text{C}$ | $10.0\%$ | $34.73^\circ\text{C}$ | $34.73^\circ\text{C}$ | $0.0000^\circ\text{C}$ | `ROTHFUSZ_LOW_RH_ADJUSTED` | **PASS** |
| **TC-HI-07** | $29.0^\circ\text{C}$ | $90.0\%$ | $37.23^\circ\text{C}$ | $37.23^\circ\text{C}$ | $0.0000^\circ\text{C}$ | `ROTHFUSZ_HIGH_RH_ADJUSTED` | **PASS** |

*Execution Evidence: Executed via `docs/academic_validation/scripts/verify_heat_index_reference.py` on Python 3.14.6. All 7 test cases exhibited exact numerical parity ($|\Delta| = 0.0000^\circ\text{C}$).*

---

### Protocol 1B: Heat-Index Boundary-Value Verification (Level A & B)
* **Status:** **Category C — Executed with Recorded Console Evidence** (37 / 37 cases passed; 100% agreement).
* **Objective:** Verify mathematical continuity, branch transitions, strict inequalities, low-RH effective activation thresholds, and policy cutoffs at boundary edges.
* **Execution Evidence:** Executed via `docs/academic_validation/scripts/verify_heat_index_boundary_values.py`.
* **Official Reference Specification:** [NOAA/NCEP WPC The Heat Index Equation](https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml).
* **Summary of Boundary Test Results:**
  - **Task 1: NWS Preliminary Threshold (80.0°F Averaged HI):** 3 / 3 PASSED. Confirmed mathematical step discontinuity of $+0.4344^\circ\text{C}$ ($+0.7819^\circ\text{F}$) between Steadman linear approximation ($26.6667^\circ\text{C}$) and Rothfusz polynomial ($27.1011^\circ\text{C}$) at $80.00^\circ\text{F}$ averaged preliminary HI. Both application and reference branch identically at `hi_avg < 80.0`.
  - **Task 2: RH Adjustment Strict Inequalities:** 6 / 6 PASSED. Verified low-RH adjustment active at $12.99\%$ and inactive at $13.00\%$; high-RH adjustment inactive at $85.00\%$ and active at $85.01\%$.
  - **Task 3: Temperature Adjustment Boundaries & Effective Activation (Phase 7.4 + 7.4.2):** 15 / 15 PASSED.
    - Low-RH temp upper bounds verified at $111.99^\circ\text{F}$, $112.00^\circ\text{F}$ (active), and $112.01^\circ\text{F}$ (inactive).
    - High-RH temp bounds verified at $79.99^\circ\text{F}$ (inactive), $80.00^\circ\text{F}$ (active with $+0.39^\circ\text{C}$ step), and $87.00^\circ\text{F}$ (active, smoothly vanishing to zero at upper bound).
    - Low-RH nominal lower bounds (Phase 7.4.2 corrected): TC-TB-10 ($79.99^\circ\text{F}$), TC-TB-11 ($80.00^\circ\text{F}$), and TC-TB-12 ($80.01^\circ\text{F}$) evaluate to `STEADMAN_PRELIMINARY_AVERAGE` because under the complete NOAA pipeline, $\text{HI}_{\text{avg}} < 80.0^\circ\text{F}$ intercepts execution before Rothfusz regression is reached. Both reference and application evaluate identically ($|\Delta| \le 0.004167^\circ\text{C}$).
    - Low-RH effective activation threshold at $\text{RH} = 10.0\%$ ($T_{F,\text{thresh}} = 80.871429^\circ\text{F}$): TC-TB-13 ($80.8614^\circ\text{F}$, below) evaluates to `STEADMAN_PRELIMINARY_AVERAGE`; TC-TB-14 ($80.8714^\circ\text{F}$, at threshold) switches to `ROTHFUSZ_LOW_RH_ADJUSTED`; TC-TB-15 ($80.8814^\circ\text{F}$, above) continues on `ROTHFUSZ_LOW_RH_ADJUSTED`. All three pass.
  - **Task 4: Policy & Physical Limits:** 13 / 13 PASSED. Verified low-temp suppression cutoff at $20.00^\circ\text{C}$, divergence guard at $110.00^\circ\text{F}$ with $\text{RH} = 45\%$, physical temperature bounds $[-50.0, 65.0]^\circ\text{C}$, and relative humidity limits $[0.0, 100.0]\%$.
  - **Numerical Error:** All continuous calculation cases evaluated within project tolerance $|\Delta| \le 0.05^\circ\text{C}$ (maximum observed difference was $0.004665^\circ\text{C}$). Detailed evidence documented in `docs/academic_validation/PHASE_7_4_BOUNDARY_VALIDATION_REPORT.md`.

---

### Protocol 2: Project-Specific Operational Policies & Safety Guards (Level B)
* **Status:** **Category C — Executed with Recorded Console Evidence** (5 / 5 cases passed).
* **Objective:** Test the application's explicit operational safeguards, input boundary filters, and conservative polynomial divergence guards.
* **Distinction:** These checks represent project-defined engineering policies, distinct from official NWS meteorological calculation formulas.

#### Executed Policy Test Matrix & Recorded Results:

| Case ID | Test Scenario | Input $T_C$ | Input $RH$ | Expected Value | Actual Value | Expected Status Flag | Actual Status Flag | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-POL-01** | Low-temperature suppression ($T < 20^\circ\text{C}$) | $18.0^\circ\text{C}$ | $50.0\%$ | `None` | `None` | `NOT_APPLICABLE_LOW_TEMPERATURE` | `NOT_APPLICABLE_LOW_TEMPERATURE` | **PASS** |
| **TC-POL-02** | Invalid relative humidity ($RH < 0\%$) | $30.0^\circ\text{C}$ | $-5.0\%$ | `None` | `None` | `INVALID_HUMIDITY` | `INVALID_HUMIDITY` | **PASS** |
| **TC-POL-03** | Invalid relative humidity ($RH > 100\%$) | $30.0^\circ\text{C}$ | $105.0\%$ | `None` | `None` | `INVALID_HUMIDITY` | `INVALID_HUMIDITY` | **PASS** |
| **TC-POL-04** | Operational sensor limit ($T > 65^\circ\text{C}$) | $70.0^\circ\text{C}$ | $50.0\%$ | `None` | `None` | `UNPHYSICAL_TEMPERATURE` | `UNPHYSICAL_TEMPERATURE` | **PASS** |
| **TC-POL-05** | Divergence guard ($T > 110^\circ\text{F}, RH > 40\%$) | $45.0^\circ\text{C}$ | $50.0\%$ | `None` | `None` | `UNSUPPORTED_EXTRAPOLATION` | `UNSUPPORTED_EXTRAPOLATION` | **PASS** |

---

### Protocol 3: Anomaly Detection Performance & Deduplication Cooldown
* **Status:** **Category C — Executed with Recorded Console Evidence** (6 unit tests passed).
* **Objective:** Verify rule-based threshold evaluation, alert deduplication cooldown ($\tau = 60\ \text{seconds}$), and severity escalation bypass.
* **Execution Evidence:** Executed via `pytest tests/test_anomaly_detector.py`. 6 passing tests:
  - `test_normal_reading_no_alert`: True negative verification.
  - `test_high_temperature_alert`: Temperature warning and critical threshold evaluation.
  - `test_elevated_pm25_alert`: Particulate matter threshold evaluation.
  - `test_sensor_offline_alert`: Hardware status evaluation.
  - `test_alert_cooldown_deduplication`: Verified suppression of duplicate alerts within 60 seconds.
  - `test_alert_escalation_bypasses_cooldown`: Verified immediate dispatch when severity escalates from Warning to Critical.

---

### Protocol 4: Row-Key Ordering & Multi-Date Partitioning
* **Status:** **Category C — Executed with Recorded Console Evidence** (5 unit tests passed).
* **Objective:** Verify row-key construction and intra-date reverse timestamp monotonicity.
* **Execution Evidence:** Executed via `pytest tests/test_row_key.py`. 5 passing tests:
  - `test_reading_key_construction_and_parsing`: Key component extraction.
  - `test_reading_key_ordering`: Verified newer timestamps produce lexicographically smaller row keys within a single calendar date.
  - `test_alert_key_construction_and_parsing`: Alert row-key formatting.
  - `test_status_key_construction`: Station status row-key formatting.
  - `test_invalid_reading_key`: Error handling on malformed keys.

---

## 3. Current Test Execution Summary & Verification State

```
+----------------------------------------------------------------------------------------------------+
|                                    TEST EXECUTION AUDIT SUMMARY                                    |
+----------------------------------------------------------------------------------------------------+
|  A. INDEPENDENT SCRIPT EXECUTION:                                                                  |
|     - verify_heat_index_reference.py:                                                              |
|       * Task 1 Formula Parity: 7 / 7 PASSED (|Delta| <= 0.05 deg C tolerance)                      |
|       * Task 2 Operational Policies: 5 / 5 PASSED (exact value and status code matches)             |
|     - verify_heat_index_boundary_values.py (Phase 7.4 + 7.4.2):                                     |
|       * Task 1 NWS Preliminary Threshold (80 deg F): 3 / 3 PASSED (+0.4344 C step quantified)       |
|       * Task 2 RH Adjustment Boundaries (< 13%, > 85%): 6 / 6 PASSED (strict inequalities verified)  |
|       * Task 3 Temperature Adjustment Boundaries (80-112 F, 80-87 F): 15 / 15 PASSED (all verified) |
|       * Task 4 Policy & Physical Bounds: 13 / 13 PASSED (status flags and reference parity)         |
|       * Total Boundary Test Cases: 37 / 37 PASSED (0 FAILED, max |Delta| = 0.004665 deg C)          |
|                                                                                                    |
|  B. SAFE PYTEST EXECUTION (Offline, Non-Mutating):                                                 |
|     - tests/test_row_key.py: 5 PASSED                                                             |
|     - tests/test_sensor_simulator.py: 7 PASSED                                                     |
|     - tests/test_anomaly_detector.py: 6 PASSED                                                     |
|     - tests/test_heat_index_safeguards.py: 12 PASSED (1 deselected: live HBase connection)        |
|     - Subtotal Safe Automated Tests: 30 PASSED, 0 FAILED                                           |
|                                                                                                    |
|  C. TESTS PENDING LIVE ENVIRONMENT (Category D):                                                   |
|     - tests/test_api.py (16 integration tests): Pending live HBase REST socket on port 8085       |
|     - tests/test_hbase_client.py (2 integration tests): Deselected to preserve historical data     |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Real-World Empirical Accuracy Validation Protocol (Level C — Future Scope)

Because the current system generates synthetic data streams, **real-world physical sensor accuracy has NOT been evaluated**. When migrating to physical hardware, the following protocol must be conducted:

1. **Co-Location Calibration:** Place physical IoT nodes adjacent to an official IMD (India Meteorological Department) Class-A automatic weather station for 14 continuous days.
2. **Transfer Function Estimation:** Derive sensor-specific linear regression calibration:
   $$T_{\text{calibrated}} = m \cdot T_{\text{raw}} + c$$
3. **Humidity Correction for Optical Particulate Counters:**
   Correct for hygroscopic growth of aerosol particles in humid environments:
   $$PM_{2.5,\text{corrected}} = \frac{PM_{2.5,\text{raw}}}{1 + \gamma \cdot \frac{RH^2}{1 - RH}}$$
