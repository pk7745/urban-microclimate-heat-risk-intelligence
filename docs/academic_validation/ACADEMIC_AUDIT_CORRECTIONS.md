# Academic Audit & Document Correction Log

**System:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Document:** `docs/academic_validation/ACADEMIC_AUDIT_CORRECTIONS.md`  
**Purpose:** Formal audit trail recording discrepancies identified across the academic validation documents, technical corrections applied, research paper verifications, and tests pending execution.  
**Audit Date:** November 2026 (Phase 8.4.2 Final Evidence Audit & Closure Edition)  
**Auditor:** Academic Technical Review Team  

---

## 1. Summary of Audit Scope & Objectives

The primary objective of Phase 7.3 is to uphold the highest standards of academic integrity, scientific accuracy, and technical truthfulness before formal college submission. Every statement across the academic validation package was cross-checked against:
1. An independent reference implementation of the official NWS Heat Index calculation (`verify_heat_index_reference.py`).
2. Actual execution evidence from offline non-mutating unit tests.
3. The live Python codebase (`app/`, `config/`, `tests/`).
4. The live Apache HBase 2.6.7 schema definitions and data states.
5. Official peer-reviewed journal publishers and permanent Digital Object Identifiers (DOIs).

---

## 2. Phase 7.3 Independent Verification Evidence & Execution Audit

### 2.1 Independent Heat-Index Formula Implementation Parity (Task 1)
- **Script Executed:** `docs/academic_validation/scripts/verify_heat_index_reference.py`
- **Methodology:** Implemented Steadman simple equation, averaging step, Rothfusz 9-term polynomial regression, and low/high-RH adjustments from first principles independently without importing application calculation functions.
- **Project Implementation Tolerance:** $|\Delta| \le 0.05^\circ\text{C}$ (project-defined verification threshold for floating-point agreement, not an official NWS standard).
- **Recorded Results:**
  - TC-HI-01 (25°C, 50% RH): Ref = 24.93°C, App = 24.93°C, $|\Delta| = 0.0000^\circ\text{C}$ (Branch: Steadman Simple) $\rightarrow$ **PASS**
  - TC-HI-02 (27°C, 60% RH): Ref = 28.08°C, App = 28.08°C, $|\Delta| = 0.0000^\circ\text{C}$ (Branch: Rothfusz Full) $\rightarrow$ **PASS**
  - TC-HI-03 (30°C, 70% RH): Ref = 35.04°C, App = 35.04°C, $|\Delta| = 0.0000^\circ\text{C}$ (Branch: Rothfusz Full) $\rightarrow$ **PASS**
  - TC-HI-04 (32°C, 80% RH): Ref = 44.37°C, App = 44.37°C, $|\Delta| = 0.0000^\circ\text{C}$ (Branch: Rothfusz Full) $\rightarrow$ **PASS**
  - TC-HI-05 (35°C, 50% RH): Ref = 40.68°C, App = 40.68°C, $|\Delta| = 0.0000^\circ\text{C}$ (Branch: Rothfusz Full) $\rightarrow$ **PASS**
  - TC-HI-06 (38°C, 10% RH): Ref = 34.73°C, App = 34.73°C, $|\Delta| = 0.0000^\circ\text{C}$ (Branch: Rothfusz Low-RH Adjusted) $\rightarrow$ **PASS**
  - TC-HI-07 (29°C, 90% RH): Ref = 37.23°C, App = 37.23°C, $|\Delta| = 0.0000^\circ\text{C}$ (Branch: Rothfusz High-RH Adjusted) $\rightarrow$ **PASS**
  - **Outcome:** **7 / 7 PASSED (100% agreement with 0.0000°C numerical difference)**.

---

### 2.2 Project-Specific Operational Policies & Safety Guards (Task 2)
- **Methodology:** Tested application operational policies separately from official NWS calculation rules.
- **Recorded Results:**
  - TC-POL-01 (Low Temp < 20°C): $T = 18.0^\circ\text{C}, RH = 50\% \rightarrow$ Returned `None`, Status `NOT_APPLICABLE_LOW_TEMPERATURE` $\rightarrow$ **PASS**
  - TC-POL-02 (Invalid RH < 0%): $T = 30.0^\circ\text{C}, RH = -5\% \rightarrow$ Returned `None`, Status `INVALID_HUMIDITY` $\rightarrow$ **PASS**
  - TC-POL-03 (Invalid RH > 100%): $T = 30.0^\circ\text{C}, RH = 105\% \rightarrow$ Returned `None`, Status `INVALID_HUMIDITY` $\rightarrow$ **PASS**
  - TC-POL-04 (Operational Upper Limit > 65°C): $T = 70.0^\circ\text{C}, RH = 50\% \rightarrow$ Returned `None`, Status `UNPHYSICAL_TEMPERATURE` $\rightarrow$ **PASS**
  - TC-POL-05 (Extreme Extrapolation Guard): $T = 45.0^\circ\text{C}$ (113°F), $RH = 50\% \rightarrow$ Returned `None`, Status `UNSUPPORTED_EXTRAPOLATION` $\rightarrow$ **PASS**
  - **Outcome:** **5 / 5 PASSED (100% policy compliance)**.

---

### 2.3 Safe Offline Unit Test Execution Evidence (Task 3)
- **Command Executed:**
  `python -m pytest tests/test_row_key.py tests/test_sensor_simulator.py tests/test_anomaly_detector.py`
  - Output: 18 passed in 1.48s (0 failed).
- **Command Executed:**
  `python -m pytest tests/test_heat_index_safeguards.py -k "not test_api_alert_presentation_and_provenance"`
  - Output: 12 passed, 1 deselected in 0.39s (0 failed).
- **Total Safe Automated Unit Tests:** **30 PASSED, 0 FAILED**.
- **Pending Tests:** 16 live integration tests in `test_api.py` and 2 mutating tests in `test_hbase_client.py` remain pending an active HBase REST gateway on port 8085.

---

### 2.4 Simulator Time-Alignment Discrepancy (Task 4)
- **Code Reality:** `SensorStation.generate_reading()` evaluates $2.5 \cdot \sin((h - 9.0)\pi / 12.0)$ where $h = \text{now.hour} + \text{now.minute} / 60.0$ and `now = datetime.now(timezone.utc)`.
- **Mathematical Reality:** Function reaches mathematical maximum (+2.5°C) at $h = 15.0\ \text{UTC}$ ($20:30\ \text{IST}$ in Bengaluru). At $h = 9.0\ \text{UTC}$ ($14:30\ \text{IST}$), the function evaluates to zero delta ($\sin(0) = 0.0$).
- **Comment Discrepancy:** The developer's inline comment states `# Diurnal solar cycle: peak at 14:00 UTC+5.30 (approx 08:30 UTC), minimum at 05:00 UTC+5.30`.
- **Action Taken:** Discrepancy documented without changing code. Recommend a future refactoring to introduce an explicit IST offset conversion (`(now_utc + timedelta(hours=5, minutes=30)).hour...`) once intended stakeholder behavior is verified.

---

### 2.5 Phase 7.4 Heat-Index Boundary-Value Verification Evidence & Discontinuity Analysis
- **Script Executed:** `docs/academic_validation/scripts/verify_heat_index_boundary_values.py`
- **Methodology:** Extended independent reference calculation with 31 targeted boundary test cases across 4 tasks:
  1. **Task 1: Preliminary Threshold Discontinuity:**
     - Evaluated $\text{HI}_{\text{avg}} = 79.99^\circ\text{F}, 80.00^\circ\text{F}, 80.01^\circ\text{F}$.
     - Confirmed mathematical step discontinuity of $+0.4344^\circ\text{C}$ ($+0.7819^\circ\text{F}$) between Steadman linear approximation ($26.6667^\circ\text{C}$) and Rothfusz 9-term polynomial ($27.1011^\circ\text{C}$) at $80.00^\circ\text{F}$ averaged preliminary HI.
     - Both application and reference implementation switch branches identically at `hi_avg < 80.0` vs. `hi_avg >= 80.0`. 3 / 3 passed.
  2. **Task 2: Relative Humidity Adjustment Inequalities:**
     - Verified low-RH adjustment condition $\text{RH} < 13.0\%$: active at $12.99\%$, deactivated at $13.00\%$ and $13.01\%$.
     - Verified high-RH adjustment condition $\text{RH} > 85.0\%$: inactive at $84.99\%$ and $85.00\%$, active at $85.01\%$.
     - Confirmed strict inequality logic in both directions. 6 / 6 passed.
  3. **Task 3: Temperature Adjustment Boundaries:**
     - Low-RH temp bounds: active at $111.99^\circ\text{F}$ and $112.00^\circ\text{F}$; inactive at $112.01^\circ\text{F}$.
     - High-RH temp bounds: inactive at $79.99^\circ\text{F}$; active at $80.00^\circ\text{F}$ with $+0.39^\circ\text{C}$ step jump; active at $86.99^\circ\text{F}$ and $87.00^\circ\text{F}$; inactive at $87.01^\circ\text{F}$.
     - Confirmed mathematical continuity at $87.00^\circ\text{F}$ because $(87.0 - T_F) / 5.0$ evaluates to $0.0$, making the adjustment vanish continuously. 9 / 9 passed.
  4. **Task 4: Project Operational & Physical Policy Boundaries:**
     - Low-temperature suppression ($T < 20^\circ\text{C}$): suppressed at $19.99^\circ\text{C}$; valid at $20.00^\circ\text{C}$ ($19.68^\circ\text{C}$) and $20.01^\circ\text{C}$ ($19.69^\circ\text{C}$).
     - Extreme divergence guard: valid at $110.00^\circ\text{F}$ ($61.91^\circ\text{C}$); rejected at $110.01^\circ\text{F}$ (`UNSUPPORTED_EXTRAPOLATION`).
     - Physical temperature limits: valid at $65.00^\circ\text{C}$ ($93.90^\circ\text{C}$); rejected at $65.01^\circ\text{C}$ (`UNPHYSICAL_TEMPERATURE`); suppressed at $-50.00^\circ\text{C}$ (`NOT_APPLICABLE_LOW_TEMPERATURE`); rejected at $-50.01^\circ\text{C}$ (`UNPHYSICAL_TEMPERATURE`).
     - Relative humidity bounds: valid at $0.00\%$ ($27.24^\circ\text{C}$) and $100.00\%$ ($44.36^\circ\text{C}$); rejected at $-0.01\%$ and $100.01\%$ (`INVALID_HUMIDITY`). 13 / 13 passed.
- **Outcome:** **31 / 31 PASSED (100% agreement, 0 failed, $|\Delta| \le 0.05^\circ\text{C}$ project tolerance met across all continuous cases)**.
- **Deliverable:** Detailed evidence recorded in `docs/academic_validation/PHASE_7_4_BOUNDARY_VALIDATION_REPORT.md`.

---

### 2.6 Phase 7.4.1 Supplementary Low-RH Lower Temperature Boundary Verification Log
- **Script Executed:** `docs/academic_validation/scripts/verify_heat_index_boundary_values.py`
- **Objective:** Evaluate the missing lower boundary ($80.0^\circ\text{F} \le T_F \le 112.0^\circ\text{F}$) for the NWS low-RH adjustment at $\text{RH} = 10.0\%$.
- **Recorded Results:**
  - **TC-TB-10** ($T_F = 79.99^\circ\text{F}, T_C = 26.6611^\circ\text{C}, \text{RH} = 10.0\%$):
    - Target: Inactive (`STEADMAN_PRELIMINARY_AVERAGE`).
    - Actual: Ref = `STEADMAN_PRELIMINARY_AVERAGE` ($26.15^\circ\text{C}$), App = `STEADMAN_PRELIMINARY_AVERAGE` ($26.15^\circ\text{C}$).
    - $|\Delta| = 0.002500^\circ\text{C} \le 0.05^\circ\text{C}$. Adj Active: NO. $\rightarrow$ **PASS**.
  - **TC-TB-11** ($T_F = 80.00^\circ\text{F}, T_C = 26.6667^\circ\text{C}, \text{RH} = 10.0\%$):
    - Target: Active (`ROTHFUSZ_LOW_RH_ADJUSTED`) per theoretical interval hypothesis.
    - Actual: Ref = `STEADMAN_PRELIMINARY_AVERAGE` ($26.16^\circ\text{C}$), App = `STEADMAN_PRELIMINARY_AVERAGE` ($26.16^\circ\text{C}$).
    - $|\Delta| = 0.001667^\circ\text{C} \le 0.05^\circ\text{C}$. Adj Active: NO. $\rightarrow$ **FAIL (Branch Expectation Mismatch)**.
  - **TC-TB-12** ($T_F = 80.01^\circ\text{F}, T_C = 26.6722^\circ\text{C}, \text{RH} = 10.0\%$):
    - Target: Active (`ROTHFUSZ_LOW_RH_ADJUSTED`) per theoretical interval hypothesis.
    - Actual: Ref = `STEADMAN_PRELIMINARY_AVERAGE` ($26.16^\circ\text{C}$), App = `STEADMAN_PRELIMINARY_AVERAGE` ($26.16^\circ\text{C}$).
    - $|\Delta| = 0.004167^\circ\text{C} \le 0.05^\circ\text{C}$. Adj Active: NO. $\rightarrow$ **FAIL (Branch Expectation Mismatch)**.
- **Scientific Audit Finding (Low-RH Lower Bound Shadowing Phenomenon):**
  - $\text{HI}_{\text{avg}} = 1.05 \cdot T_F - 5.15 + 0.0235 \cdot \text{RH} = 1.05(80.0) - 5.15 + 0.235 = 79.085^\circ\text{F} < 80.0^\circ\text{F}$.
  - Under official NOAA guidelines, $\text{HI}_{\text{avg}} < 80.0^\circ\text{F}$ branches directly to the preliminary Steadman average and never reaches the Rothfusz regression.
  - For $\text{RH} = 10.0\%$, the low-RH adjustment only becomes active when $T_F \ge 80.8714^\circ\text{F}$. The documented lower bound $80.0^\circ\text{F}$ is physically shadowed by the preliminary threshold.
  - Both the application code and the reference algorithm exhibit 100% numerical parity ($|\Delta| \le 0.0042^\circ\text{C}$).
- **Outcome:** **32 / 34 PASSED (2 test-expectation mismatches in Phase 7.4.1 resolved in Phase 7.4.2)**.

---

### 2.7 Phase 7.4.2 Test Expectation Correction & Low-RH Effective Activation Verification Log
- **Script Executed:** `docs/academic_validation/scripts/verify_heat_index_boundary_values.py`
- **Objective:** Correct the Phase 7.4.1 test expectations for TC-TB-11 and TC-TB-12 to align with the complete NOAA/NWS operational pipeline, and add test cases for the true effective activation threshold where the low-RH adjustment actually engages.
- **Root Cause of Prior Mismatch:**
  - In Phase 7.4.1, test expectations for TC-TB-11 ($80.00^\circ\text{F}$) and TC-TB-12 ($80.01^\circ\text{F}$) at $\text{RH} = 10.0\%$ assumed the isolated adjustment condition `80 <= T_F <= 112` would trigger `ROTHFUSZ_LOW_RH_ADJUSTED`.
  - However, the official [NOAA/NCEP WPC The Heat Index Equation](https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml) specification mandates that Rothfusz regression (and its associated low-RH adjustment) is nested inside the preliminary averaging check `hi_avg >= 80.0`.
  - For $T_F = 80.00^\circ\text{F}$ at $\text{RH} = 10.0\%$:
    $$\text{HI}_{\text{avg}} = 1.05(80.00) - 5.15 + 0.0235(10.00) = 79.085^\circ\text{F} < 80.0^\circ\text{F}$$
  - The pipeline immediately outputs the preliminary Steadman average without evaluating Rothfusz or its low-RH adjustment. The adjustment is **nominally eligible** (`Nom Elig: YES`) under its own temperature criteria, but **pipeline inactive** (`Pipe Act: NO`). The prior failures were test-expectation specification errors, not application defects.
- **Mathematical Derivation of Effective Activation Threshold:**
  - At $\text{RH} = 10.0\%$, the preliminary heat index reaches $80.00^\circ\text{F}$ when:
    $$T_{F,\text{thresh}} = \frac{80.00 + 5.15 - 0.0235(10.00)}{1.05} = \frac{84.915}{1.05} \approx 80.87142857^\circ\text{F} \quad (T_C = 27.150794^\circ\text{C})$$
- **Targeted Test Results:**
  - **TC-TB-10** ($T_F = 79.99^\circ\text{F}, \text{HI}_{\text{avg}} = 79.07^\circ\text{F}$): Ref = `STEADMAN_PRELIMINARY_AVERAGE` ($26.15^\circ\text{C}$), App = `STEADMAN_PRELIMINARY_AVERAGE` ($26.15^\circ\text{C}$), $|\Delta| = 0.002500^\circ\text{C}$ $\rightarrow$ **PASS**.
  - **TC-TB-11** ($T_F = 80.00^\circ\text{F}, \text{HI}_{\text{avg}} = 79.09^\circ\text{F}$): Ref = `STEADMAN_PRELIMINARY_AVERAGE` ($26.16^\circ\text{C}$), App = `STEADMAN_PRELIMINARY_AVERAGE` ($26.16^\circ\text{C}$), $|\Delta| = 0.001667^\circ\text{C}$ $\rightarrow$ **PASS**.
  - **TC-TB-12** ($T_F = 80.01^\circ\text{F}, \text{HI}_{\text{avg}} = 79.10^\circ\text{F}$): Ref = `STEADMAN_PRELIMINARY_AVERAGE` ($26.16^\circ\text{C}$), App = `STEADMAN_PRELIMINARY_AVERAGE` ($26.16^\circ\text{C}$), $|\Delta| = 0.004167^\circ\text{C}$ $\rightarrow$ **PASS**.
  - **TC-TB-13** ($T_F = 80.8614^\circ\text{F}, \text{HI}_{\text{avg}} = 79.9895^\circ\text{F}$): Ref = `STEADMAN_PRELIMINARY_AVERAGE` ($26.66^\circ\text{C}$), App = `STEADMAN_PRELIMINARY_AVERAGE` ($26.66^\circ\text{C}$), $|\Delta| = 0.003333^\circ\text{C}$ $\rightarrow$ **PASS**.
  - **TC-TB-14** ($T_F = 80.8714^\circ\text{F}, \text{HI}_{\text{avg}} = 80.0000^\circ\text{F}$): Ref = `ROTHFUSZ_LOW_RH_ADJUSTED` ($25.80^\circ\text{C}$), App = `ROTHFUSZ_LOW_RH_ADJUSTED` ($25.80^\circ\text{C}$), $|\Delta| = 0.002622^\circ\text{C}$ $\rightarrow$ **PASS**.
  - **TC-TB-15** ($T_F = 80.8814^\circ\text{F}, \text{HI}_{\text{avg}} = 80.0105^\circ\text{F}$): Ref = `ROTHFUSZ_LOW_RH_ADJUSTED` ($25.81^\circ\text{C}$), App = `ROTHFUSZ_LOW_RH_ADJUSTED` ($25.81^\circ\text{C}$), $|\Delta| = 0.002619^\circ\text{C}$ $\rightarrow$ **PASS**.
- **Quantification of Step Discontinuity at Activation:**
  - Transitioning from TC-TB-13 (`STEADMAN_PRELIMINARY_AVERAGE`, $26.66^\circ\text{C}$) to TC-TB-14 (`ROTHFUSZ_LOW_RH_ADJUSTED`, $25.80^\circ\text{C}$) produces a step discontinuity of $-0.86^\circ\text{C}$ ($-1.55^\circ\text{F}$) resulting from switching from Steadman linear averaging to Rothfusz polynomial minus the low-RH adjustment term.
- **Final Metrics:**
  - **Total Cases Executed:** **37**
  - **Total Passed:** **37 (100% agreement)**
  - **Total Failed:** **0**
  - **Maximum Observed $|\Delta|$:** **$0.004665^\circ\text{C}$** (TC-TB-06 at $80.01^\circ\text{F}, 90.0\%$ RH), well below the project tolerance of $0.05^\circ\text{C}$.
  - **Branch Agreement:** 37 / 37 exact pipeline branch matches.

---

### 2.8 Phase 7.4.3 High-Precision Floating-Point Threshold Audit Log
- **Script Executed:** `docs/academic_validation/scripts/verify_heat_index_boundary_values.py`
- **Objective:** Verify exact inputs ($\ge 12$ decimals), intermediate $\text{HI}_{\text{avg}}$ precision, difference vs. $80.0^\circ\text{F}$, comparison truth values, and confirm genuine routing to the Rothfusz regression at the mathematical threshold without reliance on display rounding.
- **Exact Threshold Formula:**
  $$T_{F,\text{thresh}} = \frac{80.0 + 5.15 - 0.0235 \times 10.0}{1.05} = 80.8714285714285808^\circ\text{F} \quad (T_C = 27.1507936507936556^\circ\text{C})$$
- **Documented Epsilon:** $\epsilon = \pm 0.01^\circ\text{F}$ ($\pm 0.005556^\circ\text{C}$)
- **Audit Findings:**
  1. **TC-TB-13** ($T_F = T_{F,\text{thresh}} - 0.01^\circ\text{F}$):
     - Temp passed to Ref: `27.14523809523810` °C
     - Temp passed to App: `27.14523809523810` °C (Bitwise identical: True)
     - Calculated preliminary $\text{HI}_{\text{avg}}$: `79.98950000000001` °F
     - Difference ($\text{HI}_{\text{avg}} - 80.0$): `-1.04999999999933e-02` °F
     - Comparison `HI_avg >= 80.0`: `False` (`HI_avg < 80.0`: `True`)
     - Application routing: `VALID` / Steadman preliminary ($26.66^\circ\text{C}$).
  2. **TC-TB-14** ($T_F = T_{F,\text{thresh}}$):
     - Temp passed to Ref: `27.15079365079366` °C
     - Temp passed to App: `27.15079365079366` °C (Bitwise identical: True)
     - Calculated preliminary $\text{HI}_{\text{avg}}$: `80.00000000000000` °F
     - Difference ($\text{HI}_{\text{avg}} - 80.0$): `+0.00000000000000e+00` °F
     - Comparison `HI_avg >= 80.0`: `True` (`HI_avg < 80.0`: `False`)
     - Application routing: `VALID` / Rothfusz regression polynomial ($25.80^\circ\text{C}$).
     - **Genuine Routing Confirmed:** In `assess_heat_index` (`app/services/sensor_simulator.py:103`), `if hi_avg < 80.0:` strictly evaluates to `False`. Execution bypasses the preliminary Steadman return path **prior to and independent of any display rounding**. It proceeds to line 112 (Rothfusz regression) and line 135 (low-humidity adjustment). Genuine Rothfusz routing is mathematically confirmed.
  3. **TC-TB-15** ($T_F = T_{F,\text{thresh}} + 0.01^\circ\text{F}$):
     - Temp passed to Ref: `27.15634920634922` °C
     - Temp passed to App: `27.15634920634922` °C (Bitwise identical: True)
     - Calculated preliminary $\text{HI}_{\text{avg}}$: `80.01050000000001` °F
     - Difference ($\text{HI}_{\text{avg}} - 80.0$): `+1.05000000000075e-02` °F
     - Comparison `HI_avg >= 80.0`: `True` (`HI_avg < 80.0`: `False`)
     - Application routing: `VALID` / Rothfusz regression polynomial ($25.81^\circ\text{C}$).
  4. **Floating-Point Limitation Note:** Although exact threshold comparison in IEEE-754 evaluates with zero numerical error ($+0.0000\text{e}+00$), the bracketing cases TC-TB-13 and TC-TB-15 provide the definitive, architecture-independent mathematical proof of the branch transition across the boundary.

---

### 2.9 Phase 8.2.1 Literature Review Accuracy & Citation Audit Log
- **Document Audited:** `docs/academic_validation/PHASE_8_2_LITERATURE_REVIEW.md`
- **Audit Objective:** Correct technical overstatements regarding HBase row-key mechanics, audit heat-stress biometeorological interpretations, establish a 5-tier reference classification, verify complete bibliographic metadata, and enforce strict comparability boundaries on all numerical claims.

1. **HBase Row-Key Architecture & Hotspotting Correction (Task 1):**
   - *Identified Discrepancy:* Prior documentation asserted that reverse timestamps eliminate or prevent write hot-spotting in Apache HBase.
   - *Technical Correction:* Reverse timestamps (`MAX_REVERSE_EPOCH_MS - timestamp_ms`) strictly provide descending chronological ordering within a lexicographical range, enabling constant-time $O(1)$ scans for latest readings. However, they do **not** prevent write hotspots. In fact, monotonically decreasing reverse timestamps write sequentially into the exact same region range.
   - *Date Partitioning Role:* The inclusion of `#YYYYMMDD#` groups rows by UTC calendar date for bounded daily range scans.
   - *Actual Hotspot Prevention Mechanisms:* Distributing write load across RegionServers requires key salting (hash prefixing such as `hash(station_id) % N`), bucketing, or pre-split region boundaries.
   - *Codebase Audit (`app/services/hbase_client.py:25-57`):* Inspected `RowKeyBuilder.build_reading_key` (`STATION_ID#YYYYMMDD#REV_TS_MS`). Confirmed that with only 5 fixed stations (`ST001`–`ST005`), all keys cluster in a narrow lexicographical band and may target a single RegionServer unless the table is pre-split.
   - *Practitioner vs. Peer-Reviewed Literature:* Officially categorized HBase system manuals, OpenTSDB documentation, and George (2011) as technical documentation (Category D), not peer-reviewed academic research.

2. **Heat-Stress Research Interpretation Audit (Chakraborty et al., 2022) (Task 2):**
   - *Identified Discrepancy:* Prior review draft claimed Chakraborty et al. "proves NWS Heat Index is superior to air temperature alone" or "directly validates our pipeline".
   - *Technical Correction:* Corrected interpretation to accurately reflect the published study:
     - Analyzed $>40,000$ crowdsourced Netatmo stations across $\approx 600$ European urban clusters during the July 2019 heatwave.
     - Quantified the urban moisture deficit, demonstrating that lower daytime urban humidity moderates apparent heat stress by $1^\circ\text{C}$ to $2^\circ\text{C}$ relative to dry-bulb temperature alone.
     - Demonstrated that satellite Land Surface Temperature (LST) correlates poorly with human heat stress ($R^2 < 0.2$), proving remote sensing surface proxies cannot substitute for near-surface atmospheric sensing.
     - Evaluated multiple apparent heat-stress metrics (NWS Heat Index, Humidex, simplified WBGT), noting that citizen stations lack radiation and wind instrumentation required for full energy-balance indices (PET/UTCI).
     - Confirmed that this justifies measuring temperature and humidity concurrently, but does **not** prove NWS Heat Index is universally superior, nor does it empirically validate our synthetic 5-station software pipeline.

3. **5-Tier Reference Classification (Task 3):**
   - Reorganized all literature citations into 5 distinct categories:
     - **Category A:** Peer-Reviewed Research Articles (Chakraborty et al., 2022; Cureau et al., 2024; Eingrüber et al., 2025; Feigel et al., 2025; Lefevre et al., 2024; Lyu et al., 2022; Steadman, 1979).
     - **Category B:** Peer-Reviewed Review Articles (Wong et al., 2025).
     - **Category C:** Peer-Reviewed Database and Distributed-Systems Research (Wang et al., 2020 on Apache IoTDB in *PVLDB*).
     - **Category D:** Technical Books, Standards, and Documentation (Apache HBase Reference Guide, 2024; George, 2011; OpenTSDB Architecture Guide, 2014–2024; Rothfusz, 1990 NWS SR 90-23).
     - **Category E:** Unverified or Inaccessible Sources ("Platform urbanism...", 2025 excluded).

4. **Bibliographic Record Verification (Task 4):**
   - Completed author list for Wong et al. (2025): Carmen Hau Man Wong, Yu Ting Kwok, Yueyang He, Edward Ng.
   - Verified publisher DOI, journal, volume, and article/page numbers across all 7 candidate publications.

5. **Numerical Claim Audit & Comparability Analysis (Task 5):**
   - Constructed comprehensive numerical audit table in `PHASE_8_2_LITERATURE_REVIEW.md` Section 9.
   - Enforced explicit comparability rules:
     - Lyu et al. prediction MAE ($0.45^\circ\text{C}$) is empirical spatial cross-validation error across Chicago; it is **NOT comparable** to our software floating-point formula parity tolerance ($0.05^\circ\text{C}$).
     - Lefevre et al. physical sensor calibration ($R^2 > 0.98$) evaluates physical SHT35 sensor hardware against Class-A instruments; it is **NOT comparable** to our software implementation formula agreement ($|\Delta| \le 0.0047^\circ\text{C}$).
     - Cureau et al. urban thermal amplitudes ($3.3^\circ\text{C}$ summer midday, $4.3^\circ\text{C}$ winter morning) are empirical field transects in Florence; they are **NOT comparable** to synthetic parameters in our simulator.
     - Feigel et al. 42 stations at $2.5\ \text{m}$ height and Eingrüber et al. 12 stations / 59 sensors represent physical hardware networks; they are **NOT comparable** to our 5-station synthetic software model.

6. **Enforcement of the Six Project Distinction Boundaries (Task 6):**
   - Embedded six mandatory boundaries across all documentation:
     1. Physical sensor validation vs. simulated telemetry.
     2. Physical sensor calibration vs. software formula validation.
     3. Urban heat-island prediction vs. heat-index calculation.
     4. Machine learning prediction vs. rule-based anomaly detection.
     5. Continuous empirical monitoring vs. simulated ingestion.
     6. Spatial interpolation vs. discrete 5-station dashboard.
   - Zero research novelty or algorithmic superiority claims permitted.

---

### 2.10 Phase 8.2.2 Literature Review Precision Audit Log
- **Document Audited:** `docs/academic_validation/PHASE_8_2_LITERATURE_REVIEW.md`
- **Audit Objective:** Resolve remaining technical, numerical, and Git-status precision issues identified during Phase 8.2.1 review.

1. **HBase O(1) Statement & Multi-Date Query Correction (Task 1):**
   - *Identified Discrepancy:* Literature review stated that reverse timestamps provide "constant-time O(1) scans" or "global newest-first ordering".
   - *Codebase Audit (`app/services/hbase_client.py:25-57` & `app/services/telemetry_service.py:180-285`):*
     - Row-key layout: `STATION_ID#YYYYMMDD#REV_TS_MS`.
     - Reverse timestamps strictly place newer records before older records *within the same station and calendar date prefix*.
     - Scanning the first row of a station-date prefix does **not** establish $O(1)$ complexity for the scan operation or for the complete query pipeline across the HBase REST gateway.
     - Because calendar date (`YYYYMMDD`) precedes reverse timestamp in the key, dates sort in ascending order (`20261118` before `20261119`). Scanning solely by station prefix (`ST001#`) visits older calendar dates first and does **not** return the globally newest record across multiple dates.
     - Documented the actual query implementations:
       - `get_latest_telemetry` iterates backwards across UTC calendar dates up to 7 days, executes prefix scans for each date, and merges/sorts records in Python: `all_records.sort(key=lambda x: x["timestamp_ms"], reverse=True)`.
       - `get_station_telemetry` scans each intersecting date partition, filters rows by epoch bounds, and merges/sorts records in Python: `merged_rows.sort(key=lambda x: x["timestamp_ms"], reverse=reverse_sort)`.
     - All claims of "constant-time O(1) scans" and "global newest-first ordering" have been excised.

2. **RegionServer Distribution Claims Correction (Task 2):**
   - *Identified Discrepancy:* Prior text asserted that the five station prefixes necessarily reside on a single RegionServer.
   - *Technical Correction:*
     - The five station identifiers (`ST001`–`ST005`) create a limited number of leading key prefixes.
     - Actual region placement depends on region boundaries, pre-splitting, and cluster configuration; prefixes do not necessarily reside on one RegionServer, nor are they guaranteed to be balanced.
     - The current project operates on a single standalone HBase instance and has **not** demonstrated distributed write scaling or measured RegionServer hotspotting.
     - Reverse timestamps are a query-ordering technique, not a hotspot-prevention mechanism.
     - Confirmed that neither salting, bucketing, nor pre-splitting is implemented in the project codebase.

3. **Recheck of Chakraborty et al. (2022) Numerical Claims (Task 3):**
   - *Source Inspected:* Publisher full paper (*AGU Advances*, 3(5), e2022AV000729) and supporting information.
   - *Verified Scale & Metrics:* $>40,000$ crowdsourced Netatmo weather stations across $\approx 600$ European urban clusters during July 2019 heatwave. Metrics evaluated: Heat Index ($HI_0$), Humidex, Apparent Temperature ($AT$), Wet-Bulb Temperature ($T_w$).
   - *Verified Quantitative Differentials:* 5th to 95th percentile ranges documented in article results:
     - Surface temperature differential ($\Delta T_s$): $-1.3^\circ\text{C}$ to $5.25^\circ\text{C}$
     - Air temperature differential ($\Delta T_a$): $-1.91^\circ\text{C}$ to $2.19^\circ\text{C}$
     - Wet-bulb temperature differential ($\Delta T_w$): $-1.27^\circ\text{C}$ to $1.43^\circ\text{C}$
   - *Verified Satellite Proxy Correlation:* Cross-cluster coefficient of determination between urban–rural differences in satellite surface temperature ($\Delta T_s$) and heat index ($\Delta HI_0$) yields $r^2 = 0.04$ (Figure 7c). Cross-cluster association between urban–rural differences in vegetation ($\Delta NDVI$) and $\Delta HI_0$ yields $r^2 = 0.02$ (Figure 7h).
   - *Correction Applied:* Removed the unverified loose "1–2°C" claim and "R² < 0.2" generalization. Retained exact verified percentile distributions and exact $r^2$ values, explaining the daytime moisture deficit moderation as a qualitative partial offset, and distinguishing Figure 7's cross-cluster analysis from within-cluster analyses.

4. **Recheck of Feigel et al. (2025) (Task 4):**
   - *Source Inspected:* Publisher paper (*Sustainable Cities and Society*, 119, 105991).
   - *Verified Authors:* Gregor Feigel, Marvin Plein, Matthias Zeeman, Swen Metzger, Andreas Matzarakis, Dirk Schindler, Andreas Christen.
   - *Verified Parameters:*
     - Network scale: 13 Tier-I custom modular biometeorological stations installed in Freiburg; 42 stations total across the combined Tier-I and Tier-II network (not 42–44 newly installed AWS).
     - Mounting height: Standardized at $3\ \text{m} \pm 200\ \text{mm}$ on public street lighting posts within the urban canopy layer.
     - Variables: Air temperature, relative humidity, wind speed, solar radiation fluxes / black-globe temperature.
     - Biometeorological index computed: The study specifically selected and calculated Physiological Equivalent Temperature (PET) for its thermal-comfort analysis.
     - Location & duration: Freiburg im Breisgau, Germany; continuous 30-second logging.

5. **Recheck of Cureau et al. (2024) (Task 5):**
   - *Source Inspected:* Publisher paper (*Environmental Research*, 262(Part 1), 119795).
   - *Verified Authors:* Roberta Jacoby Cureau, Carla Balocco, Ilaria Pigliautile, Cristina Piselli, Claudia Fabiani, Franco Cotana, Cristina Carletti, Fabio Sciurpi, Anna Laura Pisello.
   - *Verified Findings:* Integrated 3 permanent reference stations with mobile vehicles and wearable sensor backpacks in Florence, Italy; analyzed via Ordinary Kriging interpolation; maximum air temperature amplitudes detected via the wearable sensing system reached $3.3^\circ\text{C}$ at summer midday and $4.3^\circ\text{C}$ on winter mornings.

6. **Git Integrity Audit (Task 6):**
   - Commands executed:
     - `git status --short` $\rightarrow$ `?? docs/academic_validation/`
     - `git status` $\rightarrow$ On branch main, untracked files present (`docs/academic_validation/`)
     - `git log -1 --oneline` $\rightarrow$ `f6823f6 Initial release: Urban Microclimate & Heat-Risk Intelligence System`
   - Determination: The academic documents are **untracked**. The Git working tree contains untracked files and is not technically clean, but all tracked repository files are completely unmodified. No commits or pushes performed.

---

### 2.11 Phase 8.2.3 Feigel and Chakraborty Study Interpretations Audit Log
- **Documents Audited:** `docs/academic_validation/PHASE_8_2_LITERATURE_REVIEW.md` and `docs/academic_validation/ACADEMIC_AUDIT_CORRECTIONS.md`
- **Audit Objective:** Correct study interpretations for Feigel et al. (2025) and Chakraborty et al. (2022) to adhere strictly to the published full text.

1. **Feigel et al. (2025) Network & Biometeorology Precision Corrections:**
   - *Network Architecture:* Clarified that 13 Tier-I custom modular monitoring stations were installed in Freiburg, Germany, which operate alongside 29 Tier-II stations (derived by arithmetic inference: 42 total minus 13 Tier-I; not separately designated as commercial stations by publisher text) to form a combined network of 42 stations total. Removed prior loose phrasing of "42 to 44 newly installed AWS stations."
   - *Mounting Height:* Standardized mounting height explicitly documented as $3\ \text{m} \pm 200\ \text{mm}$ on public street lighting posts within the urban canopy layer.
   - *Thermal Comfort Metric:* Confirmed that the study specifically selected and calculated Physiological Equivalent Temperature (PET) for its thermal-comfort analysis. Removed uncorroborated assertions that the study calculated both UTCI and PET.
   - *Tier Distinction:* Enforced clear distinction between the 13 custom-developed Tier-I stations and the overall 42-station two-tier network across all summary narratives and comparison tables.

2. **Chakraborty et al. (2022) Figure 7 Cross-Cluster Interpretation Corrections:**
   - *Figure 7(c) Association:* Verified that the reported $r^2 = 0.04$ describes the cross-cluster association between urban–rural surface temperature differences ($\Delta T_s$) and urban–rural heat index differences ($\Delta HI_0$) across European urban clusters.
   - *Figure 7(h) Association:* Verified that the reported $r^2 = 0.02$ describes the cross-cluster association between urban–rural differences in NDVI ($\Delta NDVI$) and urban–rural heat index differences ($\Delta HI_0$) across urban clusters.
   - *Correction of Association Domain:* Corrected prior descriptions that conflated Figure 7(h) with an intra-urban vegetation association. Confirmed that Figure 7 presents cross-cluster associations of urban–rural differentials, which are methodologically distinct from the paper's separate within-cluster (intra-urban) spatial analyses.

3. **Global Audit of Related References:**
   - Scanned all academic documentation files for potential contradictions regarding station counts (13 Tier-I vs. 42 total), mounting heights ($3\ \text{m} \pm 200\ \text{mm}$), biometeorological metrics (PET selected), and cross-cluster $r^2$ values ($0.04$ and $0.02$).
   - Ensured 100% internal consistency across both audited documents.

---

### 2.12 Final Source-Precision Audit Log
- **Documents Audited:** `docs/academic_validation/PHASE_8_2_LITERATURE_REVIEW.md` and `docs/academic_validation/ACADEMIC_AUDIT_CORRECTIONS.md`
- **Audit Objective:** Apply final source-precision edits for Feigel et al. (2025) and Chakraborty et al. (2022).

1. **Feigel et al. (2025) Precision Revisions:**
   - Retained the verified counts of 13 Tier-I stations installed in Freiburg and 42 total stations across the two-tier network.
   - Clarified that the Tier-II station count of 29 is derived by arithmetic inference (42 total stations minus 13 Tier-I stations) rather than a separately stated publisher figure.
   - Removed all references labeling Tier-II stations as "commercial weather stations" or inventing unverified sensor capabilities, adhering strictly to author descriptions.

2. **Chakraborty et al. (2022) Scope & Proxy Precision Revisions:**
   - Replaced all generalized assertions that the study "proves satellite LST is an inadequate proxy" with the strictly bounded statement:
     *"Provides empirical evidence that satellite-derived surface temperature was a poor proxy for heat-index variability within and across the European urban clusters examined during the July 2019 heatwave."*
   - Strictly preserved the geographic (European urban clusters), temporal (July 2019 heatwave), and metric (heat index) boundaries. Avoided generalizing the findings to all climates, cities, or applications of satellite LST.
   - Maintained the Figure 7(h) cross-cluster description strictly aligned with the author's caption: evaluating cross-cluster associations between urban–rural differences ($\Delta NDVI$ vs. $\Delta HI_0$, $r^2 = 0.02$).

3. **Consistency Verification:**
   - Completed global search across the academic validation documents. Zero contradictory statements remain.

---

### 2.13 Phase 8.3 Research-to-Project Comparative Analysis Audit Log
- **Documents Created/Audited:** `docs/academic_validation/PHASE_8_3_RESEARCH_COMPARISON.md` and `docs/academic_validation/ACADEMIC_AUDIT_CORRECTIONS.md`
- **Audit Objective:** Complete rigorous academic comparative analysis between the verified project baseline (`PHASE_8_1_PROJECT_BASELINE.md`) and the verified 7 peer-reviewed studies (`PHASE_8_2_LITERATURE_REVIEW.md`).

1. **Comparative Framework Construction:**
   - Evaluated the project baseline against all 7 peer-reviewed studies across 15 structured dimensions in a unified comparative matrix.
   - Contrasted what each empirical study actually demonstrates against what our software system actually implements.
   - Strictly cited verified authors, venues, article numbers, and permanent DOIs for all studies.

2. **The Seven Core Distinction Dimensions Formalized:**
   - Rigorously separated (1) physical sensor calibration vs. synthetic stochastic simulation, (2) empirical field validation vs. algorithmic software formula parity, (3) UHI spatial prediction vs. deterministic point heat-index calculation, (4) ML model prediction vs. rule-based threshold anomaly detection, (5) continuous geostatistical interpolation vs. discrete multi-point dashboard visualization, (6) distributed production HBase cluster vs. single-node standalone deployment, and (7) physical environmental monitoring vs. synthesized REST stream ingestion.
   - Formulated academic explanations showing why conflating these distinct regimes produces epistemic errors and invalidates academic defense.

3. **Research Gaps & Future Trajectory:**
   - Identified 5 critical capabilities present in literature but absent in our baseline (physical hardware/LoRaWAN, radiation flux/PET biometeorology, spatial Kriging interpolation, ML spatial forecasting, multi-stage physical QA).
   - Identified 4 engineering capabilities implemented in our baseline unaddressed in literature (NoSQL wide-column HBase architecture, concurrent PM2.5/PM10 air quality surveillance, stateful alert lifecycle with operator acknowledgment, bounded-queue resilient ingestion).
   - Specified required future validation activities (hardware deployment, field co-location with IMD stations, distributed cluster benchmarking).

4. **Honest System Classification & Lecturer Briefing:**
   - Formally classified the system as a **Research Engineering Prototype / Proof-of-Concept (PoC)**, rejecting both "conceptual proposal" and "operational municipal system" classifications.
   - Formulated a 6-part lecturer-facing briefing: concise summary, 5 strongest similarities, 5 most important differences, 5 key lessons learned, 5 realistic future improvements, and a balanced concluding assessment.

---

### 2.14 Phase 8.3.1 Academic Accuracy and Claim-Precision Audit Log
- **Documents Audited:** `docs/academic_validation/PHASE_8_3_RESEARCH_COMPARISON.md` and `docs/academic_validation/ACADEMIC_AUDIT_CORRECTIONS.md`
- **Audit Objective:** Audit and correct claims across `PHASE_8_3_RESEARCH_COMPARISON.md` to ensure rigorous academic precision, verifiable paper evidence, and complete epistemic honesty.

1. **Corrections Made:**
   - *Software Formula Parity Scope:* Replaced the claim that formula parity proves "zero software bugs" with a precise statement that the implementation agrees with an independent reference calculation across the tested cases (maximum observed difference approximately 0.0047°C), validating the tested numerical implementation rather than every possible input or real-world physiological accuracy.
   - *Lyu et al. Description & AoT Node Count:* Removed unverified node count figures (">100 AoT nodes") and replaced with publisher-supported "Array of Things (AoT) urban sensor nodes on traffic light poles (node count not specified in reviewed publication)". Accurately described the Random Forest-based UHI prediction fusing in-situ AoT measurements, Landsat-8 thermal rasters, and spatial covariates.
   - *HBase Storage & Ingestion Claim:* Replaced all unverified "High-Throughput NoSQL Column-Store" phrases with "Apache HBase wide-column data store with a bounded in-memory ingestion queue", explicitly acknowledging that high throughput is not claimed without reproducible benchmark evidence.
   - *Compared Studies Backend Characterization:* Removed blanket statements asserting that comparison studies relied on SQL, flat files, or supercomputing scratch storage. Documented actual storage/backends only where supported (Eingrüber et al.: relational database and server storage; Lyu et al.: CyberGIS-Jupyter on ROGER supercomputer; Lefevre et al.: local SD cards and LoRa gateway logs; Chakraborty et al.: Netatmo API archives) and explicitly designated others as "not specified in the reviewed publication".
   - *Particulate Matter Categorization:* Clarified that our project displays indicative instantaneous categories based on Indian NAQI breakpoints from simulated telemetry, and explicitly does not implement or claim official 24-hour composite Indian NAQI regulatory reporting.
   - *Station Siting Similarity:* Replaced "Multi-zone morphological station siting" with "Multiple Spatially Separated Monitoring Points", explicitly noting that our five Bengaluru points are simulated coordinates rather than physically deployed sensor stations.
   - *Architecture Similarity:* Replaced broad "decoupled four-tier architecture" with the narrower and defensible "Decoupled Pipeline Architecture", matching the decoupled stages (ingestion, processing, storage, presentation) identified in Wong et al. (2025).
   - *Chakraborty et al. Lesson Precision:* Bounded the lesson regarding $r^2 = 0.04$ strictly to the cross-cluster association between urban–rural differences in surface temperature and heat index within the European urban clusters examined during the July 2019 heatwave, explaining that it cautions against treating satellite LST as a direct substitute for measured air temperature and humidity in that study's context.
   - *Feigel et al. Station Count:* Verified that 13 Tier-I stations and 42 total stations in the combined network are publisher-supported, and explicitly labeled the 29 Tier-II stations as an arithmetic inference (42 minus 13).
   - *Cureau et al. Thermal Metric:* Removed unverified assertions that Cureau et al. calculated PET; stated that the paper's microclimate monitoring and spatial Kriging analysis are the focus of comparison, and thermal comfort index calculation was not specified in the reviewed publication.
   - *Lefevre et al. $R^2 > 0.98$ Context:* Qualified the $R^2 > 0.98$ metric strictly to its verified context: controlled climate-chamber air temperature calibration against Class-A certified reference instrumentation under laboratory conditions.

2. **Claims Removed or Qualified:**
   - Removed: "Zero software bugs" assertion.
   - Removed: Unverified ">100 AoT nodes" count for Lyu et al.
   - Removed: Unbenchmarked "High-Throughput" descriptor for HBase.
   - Removed: Blanket assertion of SQL/flat-file storage for studies without publisher-documented backends.
   - Removed: Unverified claim that Cureau et al. calculated PET.
   - Qualified: PM category display as indicative instantaneous rather than official 24-hour NAQI.
   - Qualified: Station siting as simulated coordinates rather than physical morphological deployments.
   - Qualified: Satellite LST proxy limitation strictly scoped to Chakraborty et al.'s European cluster study.
   - Qualified: Lefevre et al. $R^2 > 0.98$ strictly scoped to laboratory chamber temperature calibration.

3. **Unresolved Source Details:**
   - Specific database engine/storage backend utilized in Feigel et al. (2025) and Cureau et al. (2024) (not specified in reviewed publications; labeled accordingly).
   - Exact physical Array of Things node count utilized in Lyu et al. (2022) training subset (not stated in the reviewed publication; labeled accordingly).

4. **Document Sections Affected:**
   - `docs/academic_validation/PHASE_8_3_RESEARCH_COMPARISON.md`: Section 1 (Key Principles), Section 2 (Comparison Matrix), Section 3 (Study Comparisons 3.1, 3.2, 3.3, 3.4, 3.5, 3.6), Section 4 (Distinction Dimensions 4.1, 4.2), Section 5 (Gaps 5.1, 5.2), Section 6 (Demonstrations 6.1), Section 7 (Lecturer Briefing 7.1, 7.2, 7.3, 7.4, 7.5, 7.6).

---

### 2.15 Phase 8.4.1 Technical Evaluation Design & Baseline Audit Log
- **Document Created:** `docs/academic_validation/PHASE_8_4_1_EVALUATION_DESIGN.md`
- **Audit Objective:** Establish a scientifically defensible evaluation design across performance, reliability, numerical accuracy, and functional metrics for the existing implementation without modifying source code, configuration, or HBase data.

1. **Framework Construction:**
   - Established the 6-tier Evidence Classification Scheme (IMPLEMENTED, UNIT-TESTED, INTEGRATION-TESTED, LIVE-VERIFIED, BENCHMARKED, NOT YET VERIFIED).
   - Structured evaluation across six core dimensions: Ingestion Performance, Query Performance, Reliability and Fault Handling, Heat-Index Numerical Accuracy, Anomaly Detection and Alert Behaviour, and API and Dashboard Functionality.

2. **Ingestion & Query Distinction Enforced:**
   - Strictly isolated in-memory queue throughput (`queue.Queue`, maxsize=1000) from worker CPU processing throughput (mocked persistence) and end-to-end HBase HTTP REST persistence throughput.
   - Clarified that the Phase 5.1 test demonstrated a single live insertion, which verified connectivity and schema validity, but does not constitute a throughput benchmark.
   - Accurately characterized query performance: row keys partition by date first (`STATION_ID#YYYYMMDD#REV_TS_MS`), requiring independent date-partition scans and Python-side sorting in memory for multi-date queries; confirmed queries are not constant-time $O(1)$ operations.

3. **Reliability & Safeguard Audit:**
   - Cataloged tested failure scenarios (queue full non-blocking drop, unphysical readings, gateway unavailable 503, write timeout 1s, malformed parameters 400, empty history 200, missing inputs) vs. untested operational assumptions.
   - Documented Level A numerical verification evidence (37/37 boundary cases passed, max $|\Delta| \le 0.004665^\circ\text{C}$ against independent calculation), emphasizing that formula parity does not equal physical sensor calibration or physiological heat strain validity.
   - Cataloged rule-based anomaly thresholds (temperature, PM2.5, PM10, heat index), 60-second cooldown deduplication, immediate severity escalation bypass, and HBase alert persistence.
   - Cataloged API routes (16 endpoints) and dashboard frontend components (Leaflet map, Chart.js time series, alert modal dialog, content negotiation).

4. **Benchmarking Protocols & Authorization Gates:**
   - Defined four formal benchmark protocols (In-memory queue, worker processing with mocked persistence, read-only HBase query latency, and live HBase write benchmark).
   - Formally designated live HBase ingestion writes as **RESERVED / REQUIRES SEPARATE AUTHORIZATION** to protect persistent data from unapproved mutation during audit phases.

---

### 2.16 Phase 8.4.2 Safe Performance Benchmarks & Evidence Audit Log
- **Document Created & Audited:** `docs/academic_validation/PHASE_8_4_2_PERFORMANCE_RESULTS.md`
- **Execution Script Created & Cleaned:** `docs/academic_validation/scripts/run_safe_benchmarks.py`
- **Results File Generated:** `docs/academic_validation/scripts/benchmark_results.json`
- **Audit Objective:** Execute safe, isolated, non-mutating performance benchmarks, reconcile baseline route definitions, document multi-layer throughput metrics without modifying application source code, configuration, or HBase data, and perform a rigorous final evidence audit resolving all benchmark mechanics and technical wording.

1. **Baseline Inconsistencies Audited & Reconciled:**
   - *Route Count Reconciliation:* Verified ground-truth route definitions: exactly 12 REST API routes are defined on `api_bp` (`/api/v1/...`), 2 top-level routes on Flask `app` (`/` and `/dashboard`), totaling 14 HTTP route handlers. Reconciled with the historical "16" count, which represented the 16 test requirement specifications covered in `tests/test_api.py`.
   - *Temperature Range Distinctions:* Verified that `AnomalyDetector` evaluates physical validity for alerting in Bengaluru ($[-10.0, 65.0]^\circ\text{C}$ in `_is_reading_unphysical()`), while `assess_heat_index` evaluates input numerical validity ($[-50.0, 65.0]^\circ\text{C}$), with low-temperature suppression below $20.0^\circ\text{C}$ ($68.0^\circ\text{F}$) under project operational policy.
   - *Technical Wording Corrections:*
     * Formally defined $[-10.0, 65.0]^\circ\text{C}$ as the project's *configured anomaly-detection sanity envelope* for Bengaluru's monitoring context, removing claims that temperatures outside represent universal physical impossibilities.
     * Formally defined $[-50.0, 65.0]^\circ\text{C}$ as the *configured heat-index input guard*, removing uncorroborated Sensirion datasheet references.
     * Preserved the explicit distinction between project-specific heat-index suppression below $20.0^\circ\text{C}$ (operational policy) and the official NWS Rothfusz regression equation (mathematical evaluation).
     * Preserved the explicit distinction between 12 REST API endpoints, 14 total Flask route handlers, and 16 test requirement specifications.
   - *Benchmark Isolation:* Verified that benchmark execution used dedicated queues and mocked clients with zero connection to application worker daemons.

2. **Benchmark A (In-Memory Queue) Execution & Evidence Audit:**
   - *Mode 1 (Saturated Burst Concurrency Reconciliation):* 10,000 unthrottled submissions into `queue.Queue(maxsize=1000)`; exactly 2,000 accepted, 8,000 rejected via non-blocking saturation; queue drained to 0.
     - *Audit of 2,000 Accepted vs. 1,000 Capacity:* The concurrent consumer thread (`burst_consumer_loop`) ran simultaneously during the 0.0130 s producer submission window. During that interval, the consumer successfully drained 1,000 items, dynamically replenishing 1,000 slots ($1000\ \text{initial} + 1000\ \text{freed} = 2000$). The remaining 8,000 non-blocking attempts encountered `queue.Full` and were rejected without stalling. Total items consumed equaled 2,000, and final queue was verified empty (`qsize == 0`).
     - *Throughput Intervals:* Producer submission window ($0.0130\ \text{s}$) $\rightarrow$ Attempted submission rate $769,082.87\ \text{rec/s}$, successful rate $153,816.57\ \text{rec/s}$; Total drain duration ($0.0342\ \text{s}$) $\rightarrow$ Effective drain throughput $58,479.53\ \text{rec/s}$.
     - *Latency Distribution (all 10,000 calls):* Median $0.800\ \mu\text{s}$, p95 $1.400\ \mu\text{s}$, max $1,210.600\ \mu\text{s}$.
     - *Warm-Up & Initial Emptiness:* 1,000 warm-up records executed in an isolated throwaway queue; initial benchmark queue verified empty prior to measurement.
   - *Mode 2 (Controlled Batched Flow):* Genuinely submitted 10 batches of 1,000 records ($10 \times 1,000 = 10,000$); 10,000 accepted (100%), 0 rejected; each batch synchronized and drained via `.join()` before the next started; queue drained to 0; sustained throughput $217,829.81\ \text{rec/s}$; median latency $0.900\ \mu\text{s}$ (p95: $1.300\ \mu\text{s}$); mean batch drain wait $1.211\ \text{ms}$.

3. **Benchmark B (Worker Processing with Mocked Persistence) Audit:**
   - 5,000 synthetic records processed through `_process_single_reading()` with mocked HBase client; 0 failures; warm-up (500 records) strictly excluded from timing and totals.
   - Intercepted 10,000 total put calls (5,000 readings + 5,000 status updates) with zero network HTTP calls to `localhost:8085`.
   - CPU-bound worker processing throughput: $31,765.25\ \text{rec/s}$ ($0.1574\ \text{s}$ measured duration); median latency $23.600\ \mu\text{s}$ (p95: $51.000\ \mu\text{s}$).
   - Separable latency: Anomaly detection median $6.100\ \mu\text{s}$ (p95: $13.700\ \mu\text{s}$); Row-key construction median $3.300\ \mu\text{s}$ (p95: $7.000\ \mu\text{s}$).
   - Strictly labeled as mocked-persistence CPU worker performance, not HBase write throughput.

4. **Benchmark C (Read-Only Query Performance) Audit:**
   - Probed port 8085 (HBase REST) and port 5000 (Flask Web Server); both confirmed CLOSED / UNAVAILABLE.
   - In accordance with safety rules, servers were not started automatically. Benchmark C formally documented as **BLOCKED / SERVICES OFFLINE**.

5. **Benchmark Script Maintenance:**
   - Cleaned up unreachable dead code (duplicate print/return block) in `run_safe_benchmarks.py`.

---

### 2.17 Phase 8.4.3.1 Reliability & Fault-Handling Evaluation Audit Log
- **Document Created:** `docs/academic_validation/PHASE_8_4_3_1_RELIABILITY_RESULTS.md`
- **Execution Script Created:** `docs/academic_validation/scripts/run_reliability_evaluation.py`
- **Results File Generated:** `docs/academic_validation/scripts/reliability_results.json`
- **Audit Objective:** Execute non-destructive, isolated experiments across failure scenarios A–F (Queue saturation, invalid telemetry, persistence failure, worker exception handling, recovery behavior, API degraded-state behavior).

1. **Scenario A (Queue Saturation) Verified:**
   - Evaluated isolated queue with capacity 1,000. Verified initial emptiness, 1,000 accepted on fill, 500 rejected on overflow via non-blocking `queue.put(block=False)`, incrementing `dropped_due_to_queue_full` to 500 without producer blocking.
   - Verified strict FIFO ordering across 200 drained items ($t_0 = 1794940000000$, $t_{199} = 1794940000199$).
   - Verified buffer accepted 100 new submissions into freed capacity. Verified final emptiness (1,100 total consumed, 0 remaining, `task_done` complete).

2. **Scenario B (Invalid & Malformed Telemetry) Verified:**
   - Evaluated 12 distinct edge cases. Missing `station_id` or `timestamp_ms` caught as `KeyError`; non-numeric types caught as `TypeError`.
   - Identified architectural gaps:
     * Ingestion pipeline lacks station whitelist validation (`ST999` is persisted without error).
     * IEEE 754 `NaN` comparisons evaluate to `False`, bypassing sanity checks and persisting `"nan"` to HBase.
     * Unphysical readings ($70.0^\circ\text{C}$, $-20.0^\circ\text{C}$) trigger `INVALID_READING` alerts but are still written to HBase tables rather than quarantined.

3. **Scenario C (Persistence Failure & Multi-Table Semantics) Verified:**
   - Evaluated 6 failure modes (`ConnectionError`, `RuntimeError`, `Timeout`, reading table failure, status table failure, alert table failure).
   - Confirmed sequential non-atomic HBase writes: if status or alert table writes fail after reading persistence, partial writes occur.
   - Identified critical defect: `IngestionService` ignores the boolean return value of `put_row(TABLE_STATION_STATUS)`, failing to increment `total_failed` when status writes fail.
   - Confirmed absence of Dead-Letter Queue (DLQ); failed records are permanently dropped.

4. **Scenario D (Worker Exception Handling) Verified:**
   - Confirmed that crashing records do not kill the worker thread (`_worker_loop` catches `Exception`, increments `total_failed`, calls `task_done()`, and continues to the next item).

5. **Scenario E (Transient Failure Recovery) Verified:**
   - Injected 5 consecutive persistence failures followed by 5 successful writes. Ingestion worker resumed automatically without manual intervention or daemon restart. Outage records were permanently lost.

6. **Scenario F (Flask API Degraded-State) Verified:**
   - Verified HTTP 503 on degraded backend health; verified HTTP 404 on unknown station; verified HTTP 400 on malformed parameters.
   - Confirmed that HTTP 500 internal errors expose raw Python exception strings (`{str(e)}`), leaking internal socket error traces to clients.
   - Verified that the Flask WSGI application remains completely responsive after internal errors.

---

### 2.18 Phase 8.4.3.2 Reliability Finding Verification & Retry Semantics Audit Log
- **Document Created:** `docs/academic_validation/PHASE_8_4_3_2_RELIABILITY_FINDING_VERIFICATION.md`
- **Execution Script Created:** `docs/academic_validation/scripts/run_reliability_verification.py`
- **Results File Generated:** `docs/academic_validation/scripts/reliability_verification_results.json`
- **Audit Objective:** Independently verify reliability findings, evaluate real HBase HTTP session retries without mocking `put_row()`, evaluate multi-table failure semantics, analyze IEEE 754 non-finite value handling, determine station whitelist discrepancy, evaluate API exception leakage, and reclassify findings into defects, design limitations, intentional behaviors, and validation gaps.

1. **HBase HTTP Retry Layer Verified:**
   - Real `urllib3.util.Retry` in `HBaseClient._create_session()` verified to execute up to 4 total attempts (1 initial + 3 retries) across HTTP 500, 502, 503, 504 and connection errors with exponential backoff ($0.0\text{s}, 0.6\text{s}, 1.2\text{s}$, total $\approx 1.8\text{s}$). Verified in-flight recovery on attempt 3.

2. **Multi-Table Failure Semantics Verified:**
   - Confirmed that when `TABLE_STATION_STATUS` fails, `IngestionService` ignores the boolean return value of `put_row()` (line 164), failing to increment `total_failed` and misreporting complete success in `total_ingested`. Reclassified as **CONFIRMED DEFECT**.
   - Reclassified multi-table sequential non-atomicity across HBase as a **DESIGN LIMITATION** of Apache HBase REST.

3. **IEEE 754 NaN & Non-Finite Values Verified:**
   - Confirmed that `float('nan')` bypasses `_is_reading_unphysical()` because relational comparisons evaluate to `False`. Propagates to `assess_heat_index()` which returns `status: "VALID"` with `NaN`, and persists to HBase. Reclassified as **CONFIRMED DEFECT**.
   - Confirmed that `\pm\infty` and temperatures $>65^\circ\text{C}$ trigger `INVALID_READING` alerts and are persisted to `microclimate:readings`. Reclassified as **INTENTIONAL BEHAVIOUR** (meteorological raw data preservation).

4. **Station Whitelist Inconsistency Verified:**
   - Confirmed that Flask API strictly enforces `VALID_STATION_IDS` (HTTP 400/404), while `IngestionService` accepts arbitrary station strings (`ST999`). Reclassified as **VALIDATION GAP**.

5. **API Information Disclosure Verified:**
   - Confirmed that HTTP 500 error messages concatenate `{str(e)}`, leaking internal Windows socket error codes (`[WinError 10061]`) and internal URLs to HTTP clients. Reclassified as **VALIDATION GAP / SECURITY RISK**.

6. **Absence of Dead-Letter Queue (DLQ) Verified:**
   - Reclassified from defect to **DESIGN LIMITATION** reflecting the prototype scope of in-memory buffering.

---

### 2.19 Phase 8.4.3.3 Reliability Evaluation Synthesis Audit Log
- **Document Created:** `docs/academic_validation/PHASE_8_4_3_3_RELIABILITY_SYNTHESIS.md`
- **Summary JSON Created:** `docs/academic_validation/scripts/reliability_synthesis_summary.json`
- **Audit Objective:** Consolidate, reconcile, and synthesize reliability findings from Phase 8.4.3.1 and Phase 8.4.3.2 across the six reliability dimensions, document quantitative baselines, establish strict remediation priorities, and define scientific evaluation boundaries without mutating application source code, configuration, or HBase tables.

1. **Reconciliation of Consolidated Findings (RF-01 to RF-08):**
   - Verified that all eight findings are consistently classified:
     * RF-01 (Station-Status Masking): **CONFIRMED DEFECT** (Remediation Priority: Critical).
     * RF-02 (IEEE 754 NaN Bypass): **CONFIRMED DEFECT** (Remediation Priority: Critical).
     * RF-03 (Sequential Multi-Table Non-Atomicity): **DESIGN LIMITATION** (Remediation Priority: Architectural).
     * RF-04 (Absence of DLQ): **DESIGN LIMITATION** (Remediation Priority: Architectural).
     * RF-05 (Persistence of Flagged Raw Telemetry): **INTENTIONAL BEHAVIOUR** (Remediation Priority: None / Preserve).
     * RF-06 (Missing Ingestion Station Whitelist): **VALIDATION GAP** (Remediation Priority: Medium).
     * RF-07 (Internal Exception Disclosure on HTTP 500): **SECURITY RISK** (Remediation Priority: High).
     * RF-08 (HBase Client HTTP Session Retry): **VERIFIED DESIGN** (Remediation Priority: None / Verified).

2. **Synthesis of Quantitative Baseline:**
   - Consolidated verified empirical metrics: Ingestion buffer capacity (1,000); tested burst overflow (500 attempted, 0 accepted, 500 rejected); strict FIFO order verified across 200 drained items; HTTP session retry (3 retries, 4 total attempts, backoff schedule `[0.0s, 0.6s, 1.2s]`, total exhaustion time 1.804s); in-flight recovery on attempt 3 (0.603s).
   - Re-affirmed strict epistemic distinction: Worker processing throughput ($31,765\ \text{rec/s}$) reflects CPU-bound ingestion logic with mocked persistence and is not live database write throughput.

3. **Academic Evaluation Limitations Re-Affirmed:**
   - Documented explicit academic boundaries: evaluation utilized isolated test harnesses and transport-level mocks; live distributed RegionServer crashes, ZooKeeper quorum partitions, physical sensor hardware errors, and production network outages were not evaluated under non-destructive audit rules.

---

### 2.20 Phase 8.4.4 Heat-Index and Anomaly Accuracy Evaluation Audit Log
- **Document Created:** [`docs/academic_validation/PHASE_8_4_4_HEAT_INDEX_ANOMALY_ACCURACY.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/PHASE_8_4_4_HEAT_INDEX_ANOMALY_ACCURACY.md)
- **Execution Scripts Created:**
  - [`docs/academic_validation/scripts/run_heat_index_accuracy_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_heat_index_accuracy_evaluation.py)
  - [`docs/academic_validation/scripts/run_anomaly_accuracy_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_anomaly_accuracy_evaluation.py)
- **Results Files Generated:**
  - [`docs/academic_validation/scripts/heat_index_accuracy_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/heat_index_accuracy_results.json)
  - [`docs/academic_validation/scripts/anomaly_accuracy_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/anomaly_accuracy_results.json)
- **Audit Objective:** Scientifically evaluate numerical accuracy of heat-index calculations against an independent first-principles implementation of official US National Weather Service (NWS) Steadman & Rothfusz (1990) equations; evaluate boundary behavior, invalid inputs, and numerical stability (including re-verification of confirmed defect RF-02); evaluate environmental telemetry anomaly detection rules across ambient temperature, relative humidity, particulate matter ($\text{PM}_{2.5}$, $\text{PM}_{10}$), apparent heat index, and hardware status; and evaluate alert lifecycle state machine and provenance tracking (`calculation_status`, `origin_temp`, `origin_humidity`, `LEGACY_UNVERIFIED`).

1. **Heat-Index Numerical Accuracy & Formula Parity Verified:**
   - Evaluated across 42 atmospheric test conditions. 40 passed; 2 failed due to confirmed defect RF-02 (`float('nan')` inputs).
   - Numerical parity evaluated across 25 valid cases against independent reference: **100.0% parity** ($|\Delta| \le 0.05^\circ\text{C}$).
   - Maximum absolute difference: **$0.004647^\circ\text{C}$** ($0.008365^\circ\text{F}$) at $30.0^\circ\text{C}, 90.0\%\ \text{RH}$ (Project output: $40.77^\circ\text{C}$; Reference unrounded: $40.774647^\circ\text{C}$).
   - Mean absolute difference: **$0.002212^\circ\text{C}$** ($0.003982^\circ\text{F}$).
   - Discrepancy strictly attributable to standard floating-point display rounding to two decimal places (maximum half-step rounding error $\le 0.005^\circ\text{C}$).

2. **Official NWS Boundaries vs Project Operational Policies Verified:**
   - 80°F preliminary average boundary: $HI_{\text{avg}} = 79.9^\circ\text{F}$ branches to Steadman preliminary equation; $HI_{\text{avg}} = 80.0^\circ\text{F}$ branches to Rothfusz 9-term polynomial regression. Discontinuous jump of $\approx 0.59^\circ\text{C}$ ($1.06^\circ\text{F}$) confirmed as an inherent property of published NWS equations.
   - Low-humidity adjustment ($RH < 13\%$ and $80 \le T_F \le 112^\circ\text{F}$) and high-humidity adjustment ($RH > 85\%$ and $80 \le T_F \le 87^\circ\text{F}$) verified accurate.
   - Project operational guards: Low-temperature suppression ($T < 20^\circ\text{C} \rightarrow$ `NOT_APPLICABLE_LOW_TEMPERATURE`) and divergence extrapolation guard ($T_F > 110^\circ\text{F}$ and $RH > 40\% \rightarrow$ `UNSUPPORTED_EXTRAPOLATION`) verified conforming to project safety policy.

3. **Confirmed Defect RF-02 Re-verified (IEEE 754 NaN Bypass):**
   - Python IEEE 754 float relational comparisons with `float('nan')` evaluate to `False`, bypassing range guards. `assess_heat_index()` returns `status: "VALID"` and `heat_index_celsius: NaN`. Confirmed defect RF-02 re-verified.

4. **Environmental Anomaly Detection Accuracy & State Machine Verified:**
   - All 37 individual rule tests passed (100.0% accuracy across temperature, PM2.5, PM10, heat index, and hardware status).
   - Alert lifecycle state machine verified across 8 sequential steps: initial emission, cooldown deduplication (60s suppression), immediate severity escalation (Warning $\rightarrow$ Critical), cooldown suppression of Critical, cooldown expiration re-emission (65s), recovery condition clearing, fresh re-emission, and simultaneous multi-metric alerts (Temp, PM2.5, PM10, Heat Index all emitted independently in a single pass).

5. **Alert Provenance & Legacy Formatting Verified:**
   - Verified that emitted alerts persist and format `calculation_status: "VALID"`, `origin_temp`, `origin_humidity`, and `data_source: "SIMULATED"`.
   - Legacy alerts missing calculation metadata return `is_valid: null` and `status: "LEGACY_UNVERIFIED"`, distinguishing `HISTORICAL_ACKNOWLEDGED` vs `HISTORICAL_UNACKNOWLEDGED`.

6. **Academic & Epistemic Distinctions Re-Affirmed:**
   - Confirmed formula parity ($|\Delta| \le 0.0047^\circ\text{C}$) proves algorithm implementation correctness under tested cases, not physical microclimate accuracy or real-world sensor calibration.
   - Project alerting thresholds are operational engineering triggers, not epidemiological public-health risk models.
   - NWS methodology implementation does not imply certification or endorsement by US NWS / NOAA.

---

### 2.21 Phase 8.4.5 REST API and Dashboard Evaluation Audit Log
- **Document Created:** [`docs/academic_validation/PHASE_8_4_5_API_DASHBOARD_EVALUATION.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/PHASE_8_4_5_API_DASHBOARD_EVALUATION.md)
- **Execution Scripts Created:**
  - [`docs/academic_validation/scripts/run_api_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_api_evaluation.py)
  - [`docs/academic_validation/scripts/run_dashboard_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_dashboard_evaluation.py)
- **Results Files Generated:**
  - [`docs/academic_validation/scripts/api_evaluation_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/api_evaluation_results.json)
  - [`docs/academic_validation/scripts/dashboard_evaluation_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/dashboard_evaluation_results.json)
- **Audit Objective:** Evaluate the REST API and interactive command-center dashboard as an integrated operational system layer: assess route correctness, response structures, parameter validation, error handling, security disclosure, data consistency, dashboard rendering, visualization integrity, failure resilience, and responsive layout under non-destructive testing conditions.

1. **Route & Endpoint Reconciliation Verified:**
   - Reconciled previously ambiguous route counts:
     * **12 REST API Endpoints:** Defined in `app/routes/api.py` under Blueprint `api_bp` (`url_prefix="/api/v1"`).
     * **2 Application Routes:** Defined in `app/__init__.py` (`GET /` with content negotiation, `GET /dashboard` rendering template).
     * **16 Test Specifications:** Defined in Phase 3.8 and implemented in `tests/test_api.py`.
   - Complete inventory confirmed: 14 total Flask route handlers.

2. **REST API Functional & Validation Correctness:**
   - Evaluated 56 total test cases with 100.0% pass rate:
     * Functional Endpoints: 16 / 16 passed across all 12 API endpoints and 2 app routes.
     * Input Validation & Errors: 27 / 27 passed across unknown station IDs (404), invalid limits (400), invalid order (400), invalid measurements (400), inverted date ranges (400), missing simulator actions (400), and unsupported HTTP methods (405).
     * Security Exception Handlers: 6 / 6 passed.
     * Data Consistency Assertions: 7 / 7 passed.

3. **Re-Verification of Confirmed Defect RF-07 (Security Risk):**
   - Verified that route exception handlers format user-facing messages by directly concatenating Python exception strings (`f"...: {str(e)}"`).
   - Injected failures confirmed disclosure of internal OS error codes (`[WinError 10061]`), internal hostnames, and loopback URLs (`http://localhost:8085`) across all 6 route exception blocks. Confirmed as **SECURITY RISK (RF-07)**.

4. **Architectural Finding RF-09 (Row-Key Hash Fragment Truncation):**
   - HBase row keys containing `#` characters (e.g. `ST001#8205058153242#HIGH_TEMPERATURE`) trigger URI fragment truncation if clients submit requests without percent-encoding (`%23`), returning HTTP 404 `NOT_FOUND`.
   - Verified that frontend `api.js` correctly applies `encodeURIComponent()`, but direct external REST access requires explicit URL encoding. Classified as **DESIGN LIMITATION (RF-09)**.

5. **Dashboard Presentation & Governance Verified (100%):**
   - Verified presence of all 8 functional sections, 6 summary KPI cards, 5 Chart.js canvases, Leaflet mapping container (`#station-map`), and stateful modals (`#stationDetailModal`, `#acknowledgeModal`).
   - Verified academic disclosures: `SIMULATED DATA` topbar badge, `SIMULATED STATIONS` map badge, CPCB NAQI instantaneous indicative disclaimer, and NWS Rothfusz methodology notes.
   - Verified `spanGaps: false` across all 5 charts to prevent drawing missing or null heat-index values as zero.

6. **Frontend Failure Handling & Responsive CSS Verified:**
   - `api.js` handles network and gateway failures cleanly (`status: 0`).
   - `app.js` updates cluster status badge to "HBase Degraded" upon receiving HTTP 503 from `/health`.
   - Auto-refresh loop (10s) verified to enforce `isRefreshing` execution lock, preventing burst overlap.
   - Responsive CSS breakpoints (`@media (max-width: 992px)`, `@media (max-width: 768px)`, `@media (max-width: 576px)`) and horizontal table scrolling (`.table-responsive-custom`) verified.

7. **Phase 8.4.4 Audit Reconciliation Notes:**
   - *Full-Precision vs Rounded Heat Index:* In `sensor_simulator.py`, Celsius heat index is explicitly rounded to two decimal places. Rounding the independent reference calculation to two decimal places yields exactly $0.000000^\circ\text{C}$ difference across all tested cases. Observed differences ($|\Delta| \le 0.0047^\circ\text{C}$) are strictly attributable to display rounding.
   - *Exact 80°F Discontinuity Evidence:* The preliminary-average equation $HI_{\text{avg}} = 0.5 \times (HI_{\text{simple}} + T_F) = 1.05\,T_F - 5.15 + 0.0235\,RH$. At $T_F = 80.0^\circ\text{F}$, the threshold $HI_{\text{avg}} = 80.0^\circ\text{F}$ occurs at $RH = 48.93617\%$. Immediately below ($RH = 48.936\%$), the Steadman branch yields $26.67^\circ\text{C}$ ($80.00^\circ\text{F}$); at and above ($RH = 48.940\%$), the Rothfusz regression yields $27.06^\circ\text{C}$ ($80.71^\circ\text{F}$), producing a verified step jump of $+0.39^\circ\text{C}$ ($+0.71^\circ\text{F}$) (or $+0.4344^\circ\text{C}$ / $+0.7819^\circ\text{F}$ at fixed $RH = 50.0\%$ across temperature at $T_F = 79.976^\circ\text{F}$ in Phase 7.4), confirming that piecewise jump discontinuity is an inherent mathematical property of published NOAA WPC equations.
   - *Standalone RH Anomaly Rule Verification:* Source inspection of `AnomalyDetector.analyze_reading()` confirms there is **no standalone Relative Humidity threshold alert rule** (e.g. `HIGH_HUMIDITY`). Relative humidity is checked solely for physical sensor boundary compliance ($[0.0, 100.0]\%$ in `_is_reading_unphysical()`), triggering `INVALID_READING`, while influencing alerts indirectly through `HIGH_HEAT_INDEX`.

---

### 2.22 Phase 8.4.6 Final Technical Evaluation & Evidence Synthesis Audit Log
- **Document Created:** [`docs/academic_validation/PHASE_8_4_6_FINAL_TECHNICAL_EVALUATION.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/PHASE_8_4_6_FINAL_TECHNICAL_EVALUATION.md)
- **Reconciliation Script Executed:** [`docs/academic_validation/scripts/check_boundary_reconciliation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/check_boundary_reconciliation.py)
- **Audit Objective:** Synthesize and reconcile all technical evaluation evidence from Phases 8.1 through 8.4.5 into a final, academically defensible assessment. Resolve all identified evidence gaps and numerical discrepancies, establish clear epistemic boundaries between mock testing and live HBase operations, and consolidate prioritized remediation actions.

1. **Source Material Reconciled:**
   - Synthesized evidence from: `PHASE_8_1_PROJECT_BASELINE.md`, `PHASE_8_2_LITERATURE_REVIEW.md`, `PHASE_8_3_RESEARCH_COMPARISON.md`, `PHASE_8_4_1_EVALUATION_DESIGN.md`, `PHASE_8_4_2_PERFORMANCE_RESULTS.md`, `PHASE_8_4_3_1_RELIABILITY_RESULTS.md`, `PHASE_8_4_3_2_RELIABILITY_FINDING_VERIFICATION.md`, `PHASE_8_4_3_3_RELIABILITY_SYNTHESIS.md`, `PHASE_8_4_4_HEAT_INDEX_ANOMALY_ACCURACY.md`, and `PHASE_8_4_5_API_DASHBOARD_EVALUATION.md`.

2. **Heat-Index Boundary Discontinuity Reconciled (Check A):**
   - Corrected Phase 8.4.5 narrative which erroneously claimed $RH = 40\%$ and $42\%$ at $T_F = 80.0^\circ\text{F}$ switched branches.
   - Evaluated exact equation $HI_{\text{avg}} = 1.05\,T_F - 5.15 + 0.0235\,RH$. At $T_F = 80.0^\circ\text{F}$, the threshold occurs at $RH = 48.93617\%$.
   - Verified that immediately below ($RH = 48.936\%$), Steadman preliminary equation evaluates to $26.67^\circ\text{C}$ ($80.00^\circ\text{F}$), while at and above ($RH = 48.940\%$), Rothfusz regression evaluates to $27.06^\circ\text{C}$ ($80.71^\circ\text{F}$).
   - Confirmed a verified mathematical step jump of $+0.39^\circ\text{C}$ ($+0.71^\circ\text{F}$) across the threshold at $T_F = 80.0^\circ\text{F}$ (and $+0.4344^\circ\text{C}$ / $+0.7819^\circ\text{F}$ at fixed $RH = 50.0\%$ across temperature at $T_F = 79.976^\circ\text{F}$ in Phase 7.4), validating that piecewise discontinuity is an inherent property of published NOAA WPC equations.

3. **Heat-Index Numerical Precision Reconciled (Check B):**
   - Verified that Phase 8.4.4's reported maximum difference of $0.004647^\circ\text{C}$ at ($30^\circ\text{C}, 90\%\ \text{RH}$) is strictly attributable to two-decimal output rounding ($40.77^\circ\text{C}$ vs $40.774647^\circ\text{C}$). Rounding the reference calculation to two decimal places yields $0.000000^\circ\text{C}$ difference across all 25 tested cases ($100\%$ parity).

4. **API Evaluation Counts Reconciled (Check C):**
   - Formally accounted for all 56 API evaluation test cases evidenced in `api_evaluation_results.json`:
     * 16 Functional Operations
     * 27 Input Validation & Error Handling Checks
     * 6 Security Exception Disclosures (RF-07)
     * 7 Data Consistency Assertions
     * Total: $16 + 27 + 6 + 7 = 56$ (100% accounted for).
   - Re-affirmed strict route counts: 12 REST API endpoints (`/api/v1/*`), 2 top-level application routes (`/` and `/dashboard`), 14 total Flask route handlers, and 16 Phase 3.8 test specifications.

5. **Dashboard Evidence Disentangled (Check D):**
   - Clearly separated static DOM/JS inspection (15/15 fields aligned, $spanGaps: false$ enforced, CPCB NAQI instantaneous disclaimer present) and responsive CSS breakpoint audit (992px, 768px, 576px) from previously executed Chromium Playwright browser QA screenshots (`dashboard_overview.png`, `heat_risk_intelligence.png`, `station_infrastructure.png`). Live browser execution was not repeated during this audit.

6. **Consolidated Findings & Epistemic Boundaries Re-Affirmed (Checks E, F, G):**
   - Re-affirmed classifications:
     * RF-01 (Critical Defect): Ignores return values of `put_row()` for `microclimate:station_status` and `microclimate:alerts`, falsely counting incomplete multi-table persistence as complete ingestion success. Remediation must inspect both secondary write returns and increment `total_failed` on failure.
     * RF-02 (Critical Defect): IEEE 754 NaN values bypass relational range checks in `_is_reading_unphysical()`, writing `status: VALID` with NaN heat index to HBase.
     * RF-07 (High Security Risk): Route 500 error handlers format user messages via `{str(e)}`, leaking internal Windows socket codes.
     * RF-06 (Validation Gap): Maintained strictly as a validation gap between components; no documented requirement establishes that ingestion must reject unmanaged station strings.
     * RF-09 (Design Limitation): Unencoded `#` in alert row keys triggers URI fragment truncation.
     * RF-03 and RF-04 (Architectural Limitations): Multi-table write non-atomicity and in-memory queue drop-on-full without an on-disk Dead-Letter Queue (DLQ).
     * RF-05 (Project Policy): Retention of flagged raw telemetry ($\pm\infty$) in readings table is an application design policy; without a documented requirement, it is not presented as an established scientific standard.
     * RF-08, RF-10 to RF-13 (Verified Designs): HTTP session retry (3 retries, exponential backoff), clean content negotiation, uniform JSON envelope, `spanGaps: false`, and polling overlap locks.
   - In-memory queue benchmarks ($31,765\ \text{rec/s}$) explicitly distinguished from live database throughput.
   - All research comparative boundaries and literature corrections preserved.

7. **Non-Destructive Safety Confirmation:**
   - 0 application files (`app/`, `config/`, `tests/`) modified.
   - 0 Apache HBase tables, schemas, or rows modified.
   - Daemons and services remained stopped.

---

## 3. Literature Corrections Summary (Retained from Phase 7.1 & 7.2)

1. **Eingrüber et al. (2025):** Corrected description to **12 weather station locations (PU01–PU12) linking 59 Netatmo sensor modules**, not 59 separate stations. Corrected pagination to `13–26`.
2. **Unsupported Nocturnal Differential Removed:** Removed the speculative 6.5°C nocturnal temperature differential claim from all documents.
3. **Lyu et al. (2022):** Corrected metrics to **1-km spatial resolution, 10-minute frequency, Random Forest MAE 0.45°C (2020) and 0.80°C (2018–2019)**. Removed erroneous 30m continuous raster and $R^2 = 0.94$ claims.
4. **Paper 1 (Platform Urbanism):** Excluded from peer-reviewed comparisons; classified as **UNVERIFIED / CONCEPTUAL TOPIC BENCHMARK**.

---

## 4. Distinction of Validation Regimes

1. **Level A (Formula Implementation Verification):** Verified through independent reference calculation script. 100% numerical parity achieved ($|\Delta| = 0.0000^\circ\text{C} \le 0.05^\circ\text{C}$).
2. **Level B (Project-Specific Safety Policy Validation):** Verified through input boundary checks and operational status flags. 100% policy conformance achieved.
3. **Level C (Real-World Empirical Accuracy Validation):** **Remains unperformed** because current data is generated via mathematical simulation. No physical sensor accuracy is claimed.

---

## 5. Non-Destructive Safety Confirmation

- **Application Source Code:** Untouched (`app/`, `config/`, and `tests/` have zero modifications).
- **Apache HBase Tables & Schemas:** Untouched (no alters, truncates, or data deletions).
- **Phase 5.1 Verification Anchor:** Preserved (`ST001#20261118#8205027936173`, provenance `SIMULATED_TEST_VERIFICATION`).
- **Simulator Daemon:** Stopped (zero active generation running).
- **Modifications Confined Exclusively To:** [`docs/academic_validation/`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation).
