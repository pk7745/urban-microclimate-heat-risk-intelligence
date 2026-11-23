# Phase 8.4.1 — Technical Evaluation Design & Baseline Audit

**Project:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Document:** `docs/academic_validation/PHASE_8_4_1_EVALUATION_DESIGN.md`  
**Evaluation Phase:** Phase 8.4 — Technical Evaluation (Subphase 8.4.1)  
**Creation Date:** November 2026  
**Auditor:** Academic Technical Review Team  
**Workspace:** `C:\Users\pky45\.gemini\antigravity\scratch\urban-microclimate-hbase`  
**Git Baseline Commit:** `f6823f6` (Working tree clean for all tracked files; untracked `docs/academic_validation/`)  
**Primary Input Baselines:**
- [`docs/academic_validation/PHASE_8_1_PROJECT_BASELINE.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/PHASE_8_1_PROJECT_BASELINE.md)
- [`docs/academic_validation/PHASE_8_2_LITERATURE_REVIEW.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/PHASE_8_2_LITERATURE_REVIEW.md)
- [`docs/academic_validation/PHASE_8_3_RESEARCH_COMPARISON.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/PHASE_8_3_RESEARCH_COMPARISON.md)
- [`docs/academic_validation/ACADEMIC_AUDIT_CORRECTIONS.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/ACADEMIC_AUDIT_CORRECTIONS.md)

---

## 1. Executive Summary & Evaluation Framework Objectives

This document establishes the formal scientific and engineering evaluation methodology for the **Urban Microclimate & Heat-Risk Intelligence System using Apache HBase**. The objective of Phase 8.4.1 is to design a rigorous, non-destructive evaluation protocol that audits the existing software implementation without rebuilding, redesigning, or prematurely altering application source code, configuration, or persistent HBase database records.

### Core Objectives:
1. **Define Objective Measurement Metrics:** Establish quantifiable, reproducible performance, reliability, numerical accuracy, and functional metrics across six core architectural dimensions.
2. **Classify Existing Evidence Base:** Map every existing test, verification report, and benchmark against a strict 6-tier evidence hierarchy to distinguish verified code reality from untested assumptions.
3. **Isolate Decoupled System Layers:** Strictly separate in-memory queue ingestion throughput from worker processing with mocked persistence and live Apache HBase network round-trip throughput.
4. **Preserve Academic Defensibility:** Enforce absolute scientific honesty by preserving known prototype limitations (synthetic simulation, single-node standalone HBase, lack of physical sensors, Python-side multi-date sorting) and avoiding unverified high-throughput claims.
5. **Establish Non-Destructive Safety Boundaries:** Guarantee that all proposed evaluation procedures operate safely without starting background simulators or executing mutating database writes unless authorized.

---

## 2. Evidence Classification Hierarchy

To ensure transparency and academic integrity across evaluation results, every capability, metric, and testable assertion is classified under one of the following six mutually exclusive categories:

```
+----------------------------------------------------------------------------------------------------+
|                                    EVIDENCE CLASSIFICATION SCHEME                                  |
+----------------------------------------------------------------------------------------------------+
| 1. IMPLEMENTED          | Feature/logic exists in codebase (syntax and execution structure).      |
| 2. UNIT-TESTED          | Verified via isolated automated tests with mocks/stubs.                  |
| 3. INTEGRATION-TESTED   | Interaction between multiple local application components verified.     |
| 4. LIVE-VERIFIED        | Verified against the running local service or single-node HBase instance.|
| 5. BENCHMARKED          | Quantified via rigorous, reproducible performance benchmark experiments.  |
| 6. NOT YET VERIFIED     | Lacks empirical test evidence or systematic benchmark confirmation.       |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Evaluation Design Across the Six Dimensions

### 3.1 Dimension A: Ingestion Performance

The ingestion architecture comprises three decoupled stages: (1) client submission into an in-memory queue, (2) worker thread consumption and analytical calculation, and (3) synchronous HTTP REST persistence into Apache HBase via the Stargate gateway.

```
+-------------------------+     Non-Blocking     +-------------------------+     Worker Thread     +-------------------------+     HTTP PUT (REST)     +-------------------------+
|     Sensor Producer     | -------------------> |    In-Memory Queue      | --------------------> | Ingestion Worker Loop   | --------------------> |    Apache HBase REST    |
| (sensor_simulator.py)   |   submit_reading()   | (queue.Queue, max=1000) |   _worker_loop()      | (_process_single_reading)|   put_row() (:8085)     | (microclimate:readings) |
+-------------------------+                      +-------------------------+                       +-------------------------+                           +-------------------------+
```

#### Critical Layer Distinctions:
1. **In-Memory Queue Throughput:** The maximum rate at which `IngestionService.submit_reading()` accepts Python dictionaries into `queue.Queue(maxsize=1000)` without blocking. This measures pure memory lock contention and pointer swapping (typically $10^4\text{--}10^5$ operations/sec).
2. **Worker Processing Throughput (Mocked Persistence):** The rate at which `_process_single_reading()` executes anomaly detection (`AnomalyDetector.analyze_reading`) and row-key construction (`RowKeyBuilder`) when `HBaseClient.put_row` is mocked in memory. This measures CPU-bound algorithmic throughput.
3. **End-to-End HBase Persistence Throughput:** The real-world rate at which records are serialized to JSON/XML, transmitted over TCP/HTTP to Stargate (`localhost:8085`), parsed by HBase REST servlets, written to the RegionServer Write-Ahead Log (WAL), and appended to MemStore.

> [!WARNING]
> **Re-Assessment of Phase 5.1 Evidence:**  
> The Phase 5.1 live integration test verified that a single reading (`ST001#20261118#8205027936173`) could be successfully persisted to `microclimate:readings` over HTTP REST. **This proved connectivity and schema validity, but does NOT constitute a throughput benchmark.** No throughput claims (records/second) may be cited from Phase 5.1.

#### Proposed Ingestion Metrics:
* **Metric A.1: Queue Capacity & Drop Rate:** Maximum queue capacity ($N = 1000$) and verification of non-blocking rejection (`queue.Full` handling returning `False`, incrementing `dropped_due_to_queue_full`).
* **Metric A.2: In-Memory Submission Latency:** Time in microseconds ($\mu\text{s}$) required to execute `submit_reading()`.
* **Metric A.3: Worker Ingestion Throughput (Mocked):** Sustained throughput ($\text{rec/s}$) under simulated load with mocked HBase client.
* **Metric A.4: Live HBase Ingestion Latency (Write-Path):** Round-trip time ($\text{ms}$) per HTTP PUT request to Stargate for `microclimate:readings`, `microclimate:station_status`, and `microclimate:alerts`.
* **Metric A.5: Ingestion Failure Accounting:** Accurate incrementing of `total_failed` when HBase returns non-200 status or times out ($1.0\ \text{s}$).

---

### 3.2 Dimension B: Query Performance

Query operations in `TelemetryService` interact with HBase tables structured by the row-key format:
$$\text{RowKey} = \text{STATION\_ID} \mathbin{\#} \text{YYYYMMDD} \mathbin{\#} \text{REV\_TS\_MS}$$
where $\text{REV\_TS\_MS} = 9999999999999 - \text{timestamp\_ms}$.

#### Query Architectural Reality:
* **Intra-Date Ordering:** Within a single UTC date partition, the reverse timestamp ensures that newer records have lexicographically smaller row keys than older records. A prefix scan over `ST001#20261118#` retrieves the most recent records of that date first.
* **Inter-Date Partitioning & Sorting:** Because the date `YYYYMMDD` precedes the reverse timestamp, dates are ordered chronologically ascending. A scan spanning multiple dates cannot retrieve globally newest records directly from HBase.
* **Python-Side Merging:** `TelemetryService.get_station_telemetry()` computes all intersecting UTC dates, issues independent prefix scans per date partition, filters exact millisecond epochs, merges candidate records, and executes an in-memory sort in Python (`merged_rows.sort(...)`) before applying `limit`.
* **Complexity:** These queries are **not $O(1)$ constant-time operations**; their latency scales with the number of date partitions scanned, rows returned per partition, network round-trips to Stargate, and the sorting cost in Python.

#### Proposed Query Metrics:
* **Metric B.1: Single-Station Latest Telemetry Latency:** Response time ($\text{ms}$) of `get_latest_telemetry(station_id="ST001", limit=1)`.
* **Metric B.2: Multi-Station Global Latest Telemetry Latency:** Response time ($\text{ms}$) of `get_latest_telemetry(limit=50)` inspecting 5 stations across lookback days.
* **Metric B.3: Historical Single-Date Telemetry Latency:** Response time ($\text{ms}$) of `get_station_telemetry()` within a single 24-hour UTC partition.
* **Metric B.4: Historical Multi-Date Telemetry Latency:** Response time ($\text{ms}$) of `get_station_telemetry()` across 7-day and 30-day boundaries.
* **Metric B.5: Alert Retrieval & Filtering Latency:** Latency ($\text{ms}$) of `get_alerts()` with severity and acknowledgment filters.
* **Metric B.6: API End-to-End Latency:** HTTP response time ($\text{ms}$) measured from client request to response payload delivery over Flask test client and local socket.

---

### 3.3 Dimension C: Reliability and Fault Handling

Reliability evaluation examines how gracefully the system handles edge cases, infrastructure dropouts, invalid data, and operational saturation.

```
+------------------------------------+---------------------------------------------------+-----------------------------------+
| Fault Scenario                     | Implemented Mitigation Mechanism                  | Verification State                |
+------------------------------------+---------------------------------------------------+-----------------------------------+
| 1. Queue Saturation                | Non-blocking put, increments drop counter, logged | UNIT-TESTED (test_failure_scen_3) |
| 2. Unphysical / Invalid Telemetry  | AnomalyDetector catches [-10, 65]°C, flags CRIT   | UNIT-TESTED (test_failure_scen_2) |
| 3. HBase Gateway Disconnection     | Returns False, increments failed count, 503 error | UNIT-TESTED (test_failure_scen_1) |
| 4. HBase REST Write Timeout (1.0s) | Catches requests.Timeout, logs error, returns F   | UNIT-TESTED (test_failure_scen_4) |
| 5. Malformed API Query Parameters  | Explicit 400 Bad Request with standardized JSON   | UNIT-TESTED (test_api_scen_13_14) |
| 6. Empty Historical Query Result   | Returns HTTP 200 with empty list [] and count: 0  | UNIT-TESTED (test_failure_scen_6) |
| 7. Missing Heat-Index Inputs       | Returns None, is_valid: False, status: MISSING    | UNIT-TESTED (test_failure_scen_7) |
| 8. Worker Loop Exception Isolation | Top-level try-except blocks protect thread life   | IMPLEMENTED (ingestion_service.py)|
| 9. Multi-Date Partition Overflow   | Bounds queries to 30-day maximum window           | UNIT-TESTED (telemetry_service.py)|
| 10. Data Type / Float Parse Fault  | Safe casting helper `to_float` suppresses crashes | IMPLEMENTED (telemetry_service.py)|
+------------------------------------+---------------------------------------------------+-----------------------------------+
```

#### Tested Behavior vs. Untested Operational Assumptions:
- **Tested:** Isolated exception handling, HTTP status codes on mocked failure, queue drop counters, and input validation.
- **Untested Assumptions:** Long-term memory consumption under multi-hour network partition; thread starvation if Stargate hangs without socket timeout; automated reconnect recovery after prolonged HBase container restart.

---

### 3.4 Dimension D: Heat-Index Numerical Accuracy

Numerical accuracy validation evaluates whether the Python implementation of the NOAA/NWS Heat Index matches official meteorological reference calculations.

#### Existing Verified Evidence Base (Phase 7.3 & Phase 7.4):
* **Verification Scripts:**
  - `docs/academic_validation/scripts/verify_heat_index_reference.py` (Independent 7-case reference verification).
  - `docs/academic_validation/scripts/verify_heat_index_boundary_values.py` (37-case boundary value and transition verification).
* **Boundary Validation Results (from `PHASE_7_4_BOUNDARY_VALIDATION_REPORT.md`):**
  - **RH Boundary Verification:** 6 / 6 cases PASSED ($RH = 12.99\%, 13.00\%, 13.01\%, 84.99\%, 85.00\%, 85.01\%$).
  - **Temperature Adjustment & Effective Activation:** 15 / 15 cases PASSED (covering nominal and effective activation thresholds).
  - **Policy Boundary Verification:** 13 / 13 cases PASSED (evaluating low-temperature suppression, unphysical bounds, and extrapolation guards).
  - **Phase 7.4.3 Precision Audit:** Floating-point comparison evaluated to 12 decimal places; mathematical transition threshold confirmed at $T_F \approx 80.0095238^\circ\text{F}$.
  - **Total Verification Parity:** **37 / 37 test cases PASSED (100% conformance)**.
  - **Maximum Absolute Numerical Difference ($|\Delta|$):** **$0.004665^\circ\text{C}$**, fully within the project-defined tolerance ($0.05^\circ\text{C}$).

#### Methodological Formulation:
1. **Steadman Preliminary Equation & Averaging:**
   $$\text{HI}_{\text{simple}} = 0.5 \cdot \left( T_F + 61.0 + (T_F - 68.0) \cdot 1.2 + RH \cdot 0.094 \right)$$
   $$\text{HI}_{\text{avg}} = 0.5 \cdot (\text{HI}_{\text{simple}} + T_F)$$
   If $\text{HI}_{\text{avg}} < 80.0^\circ\text{F}$, $\text{HI} = \text{HI}_{\text{avg}}$.
2. **Rothfusz 9-Term Polynomial Regression ($\text{HI}_{\text{avg}} \ge 80.0^\circ\text{F}$):**
   $$\text{HI}_F = c_1 + c_2 T_F + c_3 RH + c_4 T_F RH + c_5 T_F^2 + c_6 RH^2 + c_7 T_F^2 RH + c_8 T_F RH^2 + c_9 T_F^2 RH^2$$
3. **Low-Relative-Humidity Adjustment ($RH < 13\%$ and $80^\circ\text{F} \le T_F \le 112^\circ\text{F}$):**
   $$\text{Adj}_{\text{low}} = \frac{13 - RH}{4} \sqrt{\frac{17 - |T_F - 95|}{17}}, \quad \text{HI} \leftarrow \text{HI}_F - \text{Adj}_{\text{low}}$$
4. **High-Relative-Humidity Adjustment ($RH > 85\%$ and $80^\circ\text{F} \le T_F \le 87^\circ\text{F}$):**
   $$\text{Adj}_{\text{high}} = \frac{RH - 85}{10} \cdot \frac{87 - T_F}{5}, \quad \text{HI} \leftarrow \text{HI}_F + \text{Adj}_{\text{high}}$$
5. **Project Operational Safeguards:**
   - *Low-Temperature Suppression:* $T < 20.0^\circ\text{C}$ ($68.0^\circ\text{F}$) returns `None`, status `NOT_APPLICABLE_LOW_TEMPERATURE`.
   - *Humidity Validation:* $RH \notin [0.0, 100.0]\%$ returns `None`, status `INVALID_HUMIDITY`.
   - *Polynomial Divergence Guard:* $T_F > 110.0^\circ\text{F}$ and $RH > 40.0\%$ returns `None`, status `UNSUPPORTED_EXTRAPOLATION`.

> [!NOTE]
> **Defensibility Boundary:** This Level A formula verification proves numerical agreement against an independent calculation across tested cases. It does **not** validate whether the NWS Heat Index accurately represents human physiological heat strain in Bengaluru, nor does it demonstrate physical sensor hardware accuracy.

---

### 3.5 Dimension E: Anomaly Detection and Alert Behaviour

The rule-based anomaly detection engine (`AnomalyDetector`) monitors streaming telemetry against static environmental health thresholds, filters hardware faults, and manages stateful alert deduplication.

#### Monitored Conditions & Thresholds:
1. **High Temperature (`HIGH_TEMPERATURE`):**
   - Warning: $T \ge 35.0^\circ\text{C}$
   - Critical: $T \ge 40.0^\circ\text{C}$
2. **Elevated Fine Particulate Matter (`ELEVATED_PM25`):**
   - Warning: $PM_{2.5} \ge 60.0\ \mu\text{g/m}^3$
   - Critical: $PM_{2.5} \ge 120.0\ \mu\text{g/m}^3$ (Indicative category based on Indian NAQI breakpoints)
3. **Elevated Coarse Particulate Matter (`ELEVATED_PM10`):**
   - Warning: $PM_{10} \ge 100.0\ \mu\text{g/m}^3$
   - Critical: $PM_{10} \ge 200.0\ \mu\text{g/m}^3$ (Indicative category based on Indian NAQI breakpoints)
4. **High Heat Index (`HIGH_HEAT_INDEX`):**
   - Caution / Warning: $HI \ge 38.0^\circ\text{C}$
   - Danger / Critical: $HI \ge 44.0^\circ\text{C}$ (Evaluated only when $HI$ calculation is valid and verified)
5. **Hardware / Station Offline (`SENSOR_OFFLINE`):** Triggered when `sensor_status == "OFFLINE"`.
6. **Unphysical Sensor Readings (`INVALID_READING`):** Triggered when values violate physical atmospheric bounds ($T \notin [-10, 65]^\circ\text{C}$, $RH \notin [0, 100]\%$, $PM_{2.5} \notin [0, 1500]$, $PM_{10} \notin [0, 2500]$).

#### Stateful Deduplication & Lifecycle Engine:
- **In-Memory Tracking:** Maintains active alert state keyed by `(station_id, alert_type) -> {"severity": str, "last_alert_time": float}`.
- **Deduplication Cooldown:** Configured to $60.0\ \text{s}$ (`ALERT_COOLDOWN_SECONDS`). Ongoing violations at the same severity within cooldown are suppressed from re-alerting.
- **Immediate Escalation Bypass:** When an active violation escalates (e.g., $T$ rises from $36^\circ\text{C}$ `WARNING` to $41^\circ\text{C}$ `CRITICAL`), the cooldown is immediately bypassed, firing an escalated alert.
- **Automatic Recovery:** When readings normalize below warning thresholds, `_clear_condition_if_recovered()` clears in-memory state, allowing future violations to trigger anew.
- **Alert Persistence & Acknowledgement:** Alerts are persisted to `microclimate:alerts` with row key `STATION_ID#REVERSE_TIMESTAMP#ALERT_TYPE`. Operators can acknowledge alerts via `POST /api/v1/alerts/<alert_id>/acknowledge` with an optional note, updating columns in HBase.

---

### 3.6 Dimension F: API and Dashboard Functionality

#### REST API Evaluation Scope:
The Flask application provides 16 verified endpoints adhering to a standardized JSON response envelope:
$$\text{Response} = \{\text{"status"}: \text{"success"}\mid\text{"error"}, \text{"data"}: \dots, \text{"message"}: \dots, \text{"timestamp"}: \dots\}$$

* **Health & System Routes:** `GET /`, `GET /api/v1/health`
* **Station Information:** `GET /api/v1/stations`, `GET /api/v1/stations/<id>`
* **Telemetry Queries:** `GET /api/v1/telemetry/latest`, `GET /api/v1/telemetry/<id>` (with `start`, `end`, `order`, `measurement`, `limit`)
* **Alert Lifecycle:** `GET /api/v1/alerts` (with `station_id`, `severity`, `acknowledged`, `limit`), `POST /api/v1/alerts/<id>/acknowledge`
* **Analytics Services:** `GET /api/v1/analytics/temperature`, `GET /api/v1/analytics/air-quality`, `GET /api/v1/analytics/station-comparison`
* **Simulator Control:** `POST /api/v1/simulator/start`, `POST /api/v1/simulator/stop`, `GET /api/v1/simulator/status`

#### Dashboard UI Evaluation Scope:
* **Framework & Assets:** Flask Jinja2 template (`dashboard.html`), modular vanilla JavaScript (`api.js`, `charts.js`, `map.js`, `alerts.js`, `simulator.js`, `app.js`), and responsive CSS (`dashboard.css`).
* **Interactive Elements:**
  - Leaflet map rendering 5 station markers with color-coded operational statuses.
  - Chart.js dynamic time-series charts rendering multi-metric trends ($T$, $RH$, $PM_{2.5}$, $PM_{10}$, $HI$).
  - Live alerts table with interactive acknowledgement modal dialog.
  - Station comparison ranking cards with explicit `None` handling for missing thermal index values.
  - Content negotiation: Root path `/` serves HTML to web browsers and JSON to API clients.
* **Evidence Distinction:** Historical Playwright UI testing (Phase 4, Phase 5) verified visual layout, DOM landmark presence, and zero JavaScript console errors (`final_step_*.png`). This historical QA evidence confirms UI structural readiness, distinct from newly executed runtime benchmarks.

---

## 4. Comprehensive Technical Evaluation Matrix

The matrix below maps every evaluated metric against its measurement method, existing evidence, classification tier, required additional testing, and known constraints:

| Dimension | Specific Metric | Measurement Method | Existing Evidence Base | Evidence Classification | Additional Testing Required | Known Limitations / Constraints |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Ingestion** | In-Memory Queue Throughput | Time micro-benchmark submitting 10,000 dicts | `test_scenario_3_queue_full` | **UNIT-TESTED** | Measure $\mu\text{s}$ per call with synthetic batch | Pure memory queue; excludes database writes |
| **A. Ingestion** | Queue Drop Policy | Saturate queue ($N=1000$) and assert drop count | `test_scenario_3_queue_full` | **UNIT-TESTED** | Verify high-frequency burst drop logging | Drops occur silently to protected producer |
| **A. Ingestion** | Worker Algorithmic Throughput | Run worker with mocked HBase; measure rec/s | `IngestionService._worker_loop` | **IMPLEMENTED** | Execute 1,000-record mocked benchmark | CPU-bound; excludes network round trips |
| **A. Ingestion** | Live HBase Write Latency | Measure HTTP PUT round-trip to `:8085` | Single insert in Phase 5.1 | **NOT YET VERIFIED** | Requires live benchmark authorization | Mutates database; cannot run in read-only audit |
| **A. Ingestion** | Failure Accounting | Mock HBase write error; verify `total_failed` | `test_scenario_4_hbase_write_timeout` | **UNIT-TESTED** | Verify error counter persistence | In-memory counter resets on restart |
| **B. Query** | Latest Telemetry Latency | Measure execution time of `get_latest_telemetry` | `test_latest_telemetry_retrieval` | **UNIT-TESTED** | Measure latency over 100 repetitions | Depends on existing row count in HBase |
| **B. Query** | Multi-Date Partition Merging | Query spanning 2 dates; verify chronological merge | `test_historical_telemetry_multi_date` | **UNIT-TESTED** | Benchmark multi-partition merge scaling | Multi-date sort performed in Python memory |
| **B. Query** | Historical Query Ordering | Query with `order=desc` and `order=asc` | `test_historical_ordering_desc_asc` | **UNIT-TESTED** | Measure sort overhead for 1,000 records | Python `list.sort()` overhead on large limits |
| **B. Query** | Alert Query Latency | Measure execution time of `get_alerts()` | `test_alert_retrieval_and_filtering` | **UNIT-TESTED** | Measure latency under varying alert limits | Depends on number of rows in `alerts` table |
| **C. Reliability**| Gateway Disconnection (503) | Mock gateway down; assert 503 DEGRADED | `test_scenario_1_hbase_gateway_unavailable` | **UNIT-TESTED** | None (fully verified in unit suite) | Validates API envelope, not TCP timeout |
| **C. Reliability**| Write Timeout (1.0s) | Mock socket timeout; verify graceful False | `test_scenario_4_hbase_write_timeout` | **UNIT-TESTED** | None (fully verified in unit suite) | Relies on `requests` timeout configuration |
| **C. Reliability**| Unphysical Reading Handling | Feed $T = -999^\circ\text{C}$; verify INVALID_READING | `test_scenario_2_invalid_sensor_reading` | **UNIT-TESTED** | None (fully verified in unit suite) | Static rule; no dynamic rate-of-change check |
| **C. Reliability**| Malformed Parameters (400) | Request invalid parameters; verify 400 error | `test_scenario_5_malformed_api_parameters` | **UNIT-TESTED** | None (fully verified in unit suite) | Input validation at controller boundary |
| **D. Heat Index** | Formula Parity (Steadman) | Compare application vs. reference for $T < 80^\circ\text{F}$ | `verify_heat_index_reference.py` | **BENCHMARKED** | None (Phase 7.3 established $0.0000^\circ\text{C}$) | Mathematical parity; not sensor calibration |
| **D. Heat Index** | Formula Parity (Rothfusz) | Compare application vs. reference for $T \ge 80^\circ\text{F}$ | `verify_heat_index_reference.py` | **BENCHMARKED** | None (Phase 7.3 established $0.0000^\circ\text{C}$) | Mathematical parity; not physiological strain |
| **D. Heat Index** | Boundary Values & Adjustments | Test 37 boundary cases across RH and Temp | `PHASE_7_4_BOUNDARY_VALIDATION_REPORT.md` | **BENCHMARKED** | None (37/37 PASSED, $|\Delta| \le 0.004665^\circ\text{C}$) | Bounded test envelope; not all possible floats |
| **D. Heat Index** | Low-Temp Suppression Policy | Assert $T < 20^\circ\text{C}$ returns `None` | `test_heat_index_safeguards.py` | **UNIT-TESTED** | None (fully verified in unit suite) | Operational project guard; not NWS rule |
| **D. Heat Index** | Divergence Guard Policy | Assert $T > 110^\circ\text{F}, RH > 40\%$ returns `None` | `test_heat_index_safeguards.py` | **UNIT-TESTED** | None (fully verified in unit suite) | Operational project guard; not NWS rule |
| **E. Anomaly** | Temperature Thresholds | Test $T = 36.5^\circ\text{C}$ (WARN) and $41.2^\circ\text{C}$ (CRIT) | `test_temperature_warning_and_critical` | **UNIT-TESTED** | None (verified in unit suite) | Fixed static thresholds; no contextual tuning |
| **E. Anomaly** | PM Thresholds (Indicative) | Test $PM_{2.5} = 75$ (WARN) and $PM_{10} = 220$ (CRIT)| `test_particulate_matter_thresholds` | **UNIT-TESTED** | None (verified in unit suite) | Instantaneous value; not 24-hr composite NAQI |
| **E. Anomaly** | Alert Deduplication Cooldown| Emit continuous violation; assert 2nd suppressed | `test_alert_deduplication` | **UNIT-TESTED** | Measure exact 60s cooldown expiration | In-memory state resets on process restart |
| **E. Anomaly** | Severity Escalation Bypass | Elevate WARN to CRIT; assert immediate alert | `AnomalyDetector._evaluate_condition` | **IMPLEMENTED** | Explicit test for escalation bypass | State held in memory per station/alert type |
| **E. Anomaly** | Alert Acknowledgement | Post acknowledgement; verify HBase columns | `test_alert_acknowledgement` | **UNIT-TESTED** | Measure live acknowledgement latency | Unit test mocks HBase `put_row` |
| **F. API & UI** | API Route Conformance | Verify status code and JSON schema on 16 routes | `test_api.py` (Tests 1–16) | **UNIT-TESTED** | Measure end-to-end HTTP latency distribution | Tested via Flask test client |
| **F. API & UI** | Dashboard Route & Layout | Verify HTML rendering and DOM landmarks | `test_dashboard_route_renders_html` | **UNIT-TESTED** | None (verified in unit suite) | Verifies server-side HTML template rendering |
| **F. API & UI** | Static Asset Accessibility | Verify 200 OK on CSS and all JS modules | `test_static_assets_served_correctly` | **UNIT-TESTED** | None (verified in unit suite) | Verifies asset paths and MIME types |
| **F. API & UI** | Visual Map & Chart Rendering | Verify Leaflet tiles and Chart.js canvases | Historical Playwright QA (Phase 4 & 5) | **LIVE-VERIFIED** | Browser automated interaction benchmark | Historical evidence; not executed in 8.4.1 |

---

## 5. Performance Measurement Protocols & Benchmark Principles

To ensure that any subsequent performance measurements meet academic standards of reproducibility, the following experimental protocols are specified:

### 5.1 Protocol 1: In-Memory Ingestion Queue Micro-Benchmark
* **Objective:** Quantify the raw ingestion throughput of the in-memory queue interface without database I/O.
* **Environment:** Python 3.14 on Windows, local single-thread producer.
* **Dataset:** 10,000 synthetic reading dictionaries conforming to the schema.
* **Repetitions:** 5 independent runs of 10,000 submissions each.
* **Warm-Up:** 1,000 unmeasured submissions to warm Python memory allocator and JIT/bytecode paths.
* **Measurements:** High-resolution wall-clock timer (`time.perf_counter_ns()`).
* **Reported Statistics:** Median latency ($\mu\text{s}$), 95th percentile latency (p95), minimum, maximum, and throughput ($\text{records/sec} = 10,000 / \Delta t$).

### 5.2 Protocol 2: Worker Processing Micro-Benchmark (Mocked Persistence)
* **Objective:** Quantify the CPU processing throughput of the ingestion worker thread (anomaly evaluation, row-key generation, dictionary serialization) in isolation.
* **Environment:** Python 3.14, single worker thread consuming from queue with `HBaseClient.put_row` mocked to return `True`.
* **Dataset:** 5,000 telemetry records containing balanced normal and anomalous readings.
* **Repetitions:** 5 runs.
* **Warm-Up:** 500 records.
* **Reported Statistics:** Median processing time per record ($\mu\text{s}$), p95 latency, aggregate processing throughput ($\text{rec/s}$).

### 5.3 Protocol 3: Read-Only Query Latency Benchmark (Existing HBase Data)
* **Objective:** Measure response latency for non-mutating telemetry queries against existing HBase data.
* **Target Endpoints:**
  1. `GET /api/v1/telemetry/latest?limit=10`
  2. `GET /api/v1/telemetry/ST001?limit=50&order=desc`
  3. `GET /api/v1/alerts?limit=20`
* **Dataset:** Existing rows present in HBase tables from prior non-mutating verification runs.
* **Repetitions:** 50 consecutive HTTP requests per endpoint.
* **Warm-Up:** 5 initial requests discarded to prime socket connections and HBase REST servlets.
* **Reported Statistics:** Median latency ($\text{ms}$), p95 latency, minimum, maximum.
* **Safety:** Strictly read-only (`GET` requests only; zero writes or table modifications).

### 5.4 Protocol 4: Live Ingestion Throughput Benchmark (PENDING AUTHORIZATION)
* **Status:** **RESERVED / REQUIRES SEPARATE AUTHORIZATION**
* **Reason:** Measuring live HBase ingestion throughput requires writing thousands of new rows into `microclimate:readings`.
* **Safety Restriction:** This protocol **cannot be executed** under the read-only constraints of Phase 8.4.1. It is documented here for future evaluation planning only.

---

## 6. Non-Destructive Testing Rules & Authorization Gates

To prevent accidental modification of application state, database records, or Git history, the following rules govern Phase 8.4 execution:

```
+----------------------------------------------------------------------------------------------------+
|                                    TEST AUTHORIZATION MATRIX                                       |
+----------------------------------------------------------------------------------------------------+
| Permitted in Phase 8.4 (Safe & Read-Only):                                                         |
| [X] Execution of offline pytest unit test suites (tests/test_*.py) with mocked backends.          |
| [X] Execution of in-memory queue and worker micro-benchmarks (Protocols 1 and 2).                  |
| [X] Read-only HTTP GET queries against existing HBase records (Protocol 3).                       |
| [X] Formula verification script execution (verify_heat_index_reference.py).                        |
|                                                                                                    |
| Strictly Prohibited (Requires Explicit Separate Authorization):                                    |
| [!] Starting the background sensor simulator daemon (`sensor_simulator.py`).                       |
| [!] Starting background ingestion worker threads connected to live HBase.                          |
| [!] Executing live mutating PUT/POST tests inserting synthetic telemetry into HBase tables.        |
| [!] Modifying application source code (`app/`), configuration (`config/`), or tests (`tests/`).    |
| [!] Modifying or deleting HBase tables, column families, or records.                               |
| [!] Staging, committing, pushing, or resetting Git files.                                          |
+----------------------------------------------------------------------------------------------------+
```

---

## 7. Project-Specific Baseline Limitations & Defensibility Boundaries

In all subsequent evaluation reports, the following verified system limitations must be strictly maintained:

1. **Simulated Telemetry:** The system operates entirely on synthetic data generated by `SensorStation` in `sensor_simulator.py` (diurnal sine curve + $AR(1)$ drift + Gaussian perturbations). No physical sensors exist.
2. **Discrete Point Siting:** Telemetry is generated for five static geographic coordinates in Bengaluru. No spatial interpolation (e.g., Kriging) or continuous microclimate field modeling is implemented.
3. **Single-Node Standalone HBase:** The database runs as a standalone HBase 2.6.7 instance on Hadoop 3.3.6 substrate. Distributed cluster features (multi-RegionServer rebalancing, HDFS replication failover, cross-region splitting) are unverified.
4. **Python-Side Multi-Date Query Sorting:** Because row keys partition by date first (`STATION_ID#YYYYMMDD#REV_TS_MS`), historical queries spanning multiple UTC dates require independent partition scans and in-memory Python sorting. Scans are not constant-time $O(1)$ operations.
5. **No Production Throughput Benchmark:** Previous single-row insertion verification (Phase 5.1) does not constitute a reproducible throughput benchmark. High-throughput performance is not claimed.
6. **Formula Verification vs. Physiological Accuracy:** Algorithmic parity with NOAA/NWS regression formulas ($|\Delta| \le 0.004665^\circ\text{C}$) validates software implementation correctness; it does not validate sensor measurement accuracy or the physiological validity of the Heat Index in tropical climates.
7. **System Classification:** The system is an **Architectural Engineering Prototype / Proof-of-Concept**, not an operational municipal monitoring system.

---

## 8. Summary of Evaluation Readiness & Conclusion

The evaluation framework established in this document provides a complete, scientifically defensible foundation for Phase 8.4:
- Six evaluation dimensions are formally structured with quantifiable metrics.
- All existing evidence is rigorously classified across the 6-tier hierarchy.
- Safe, non-mutating micro-benchmarks are clearly separated from live database write tests requiring authorization.
- Academic defensibility boundaries are preserved without overstatement.

**Phase 8.4.1 is complete. No application code, database records, or Git history have been modified.**
