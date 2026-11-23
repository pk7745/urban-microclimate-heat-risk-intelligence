# Phase 8.4.6 — Final Technical Evaluation, Evidence Reconciliation & Academic Report

**Project:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Document:** `docs/academic_validation/PHASE_8_4_6_FINAL_TECHNICAL_EVALUATION.md`  
**Evaluation Date:** November 2026  
**Auditor:** Academic Technical Review Team  
**Evaluation Status:** **COMPLETED, RECONCILED & DEFENDED**  

---

## 1. Executive Summary

This report establishes the final, academically defensible technical evaluation of the Urban Microclimate & Heat-Risk Intelligence System. Synthesizing evidence across Phases 8.1 through 8.4.5, this evaluation reconciles all empirical benchmarks, unit tests, mock-based failure injections, mathematical boundary evaluations, and static architectural inspections into a unified, evidence-based academic assessment.

### Key Synthesized Findings:
1. **Mathematical Implementation Parity ($100.0\%$):** Across 25 valid atmospheric conditions, the project's heat-index implementation matches an independent, first-principles derivation of the official US National Weather Service (NWS) Steadman & Rothfusz (1990) specification with a maximum difference of **$0.004647^\circ\text{C}$** ($0.008365^\circ\text{F}$) and a mean difference of **$0.002212^\circ\text{C}$**. The observed difference is consistent with the project's two-decimal output rounding ($\le 0.005^\circ\text{C}$ half-step error window; rounding the reference calculation to two decimal places yields $0.000000^\circ\text{C}$ difference across all tested cases).
2. **Reconciled Preliminary Average Discontinuity:** The official NOAA WPC preliminary-average threshold ($HI_{\text{avg}} = 80.0^\circ\text{F}$) was mathematically re-derived. At $T_F = 80.0^\circ\text{F}$, the branch transition occurs at **$RH = 48.93617\%$**. Immediately below ($RH = 48.936\%$), the Steadman preliminary equation evaluates to $26.67^\circ\text{C}$ ($80.00^\circ\text{F}$). At and above ($RH = 48.940\%$), the formula switches to the 9-term Rothfusz polynomial regression evaluating to $27.06^\circ\text{C}$ ($80.71^\circ\text{F}$). A verified mathematical step jump of **$+0.39^\circ\text{C}$ ($+0.71^\circ\text{F}$)** occurs across the threshold (or $+0.4344^\circ\text{C}$ / $+0.7819^\circ\text{F}$ at fixed $RH = 50.0\%$ across temperature at $T_F = 79.976^\circ\text{F}$), proving that piecewise discontinuity is an inherent property of the published NWS formula rather than an implementation flaw.
3. **Confirmed Defects & Security Risks:** Three high-priority findings were independently verified:
   - **RF-01 (Critical Persistence Accounting Defect):** `IngestionService` ignores the boolean return value of `put_row()` for `microclimate:station_status` (line 164) and does not verify individual alert write success to `microclimate:alerts` (lines 173–178), causing incomplete multi-table persistence to be falsely counted as complete ingestion success in `total_ingested`.
   - **RF-02 (Critical IEEE 754 NaN Defect):** `float('nan')` inputs bypass relational range comparisons in `_is_reading_unphysical()`, propagating `status: "VALID"` with `NaN` heat index to HBase.
   - **RF-07 (High Security Risk):** Unhandled API route exceptions concatenate raw Python exception text (`f"...: {str(e)}"`), leaking internal Windows socket error codes (`[WinError 10061]`), internal hostnames, and loopback URLs.
4. **Architectural REST Limitation (RF-09):** HBase row keys formatted with `#` delimiters (e.g. `STATION#REV_TS#ALERT_TYPE`) trigger URI fragment truncation in standard HTTP parsers unless percent-encoded as `%23`.
5. **Epistemic Evaluation Boundaries:** High-throughput in-memory queue benchmarks ($31,765\ \text{rec/s}$) reflect CPU-bound ingestion logic with mocked persistence and must not be cited as live Apache HBase write throughput. The system operates on synthetic telemetry from 5 virtual Bengaluru stations; no claims of physical urban canopy accuracy, sensor calibration, or official meteorological certification are made.

---

## 2. Project Objective, Scope and System Architecture

### 2.1 Project Mission
The system is designed as an end-to-end Big Data telemetry ingestion, anomaly detection, biometeorological heat-stress intelligence, and decision-support command center tailored for urban microclimate monitoring.

```
+----------------------------------------------------------------------------------------------------+
|                                    SYSTEM ARCHITECTURAL DATA FLOW                                  |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [Virtual Sensor Stations (5)]                                                                     |
|       |                                                                                            |
|       | Real-time Telemetry (Diurnal Solar Sine + Morphology Offsets + Noise)                      |
|       v                                                                                            |
|  [In-Memory Bounded Queue (1,000 capacity, FIFO, Drop-on-Full)]                                    |
|       |                                                                                            |
|       v                                                                                            |
|  [Background Ingestion Worker (Daemon Thread)]                                                     |
|       |                                                                                            |
|       +---> [NWS Heat Index Engine (Steadman & Rothfusz Polynomial + Guards)]                      |
|       |                                                                                            |
|       +---> [Rule-Based Anomaly Detector (Temperature, PM2.5, PM10, Heat Index, Hardware)]         |
|       |                                                                                            |
|       +---> Sequential Multi-Table Persistence via urllib3 HTTP Session Retries                     |
|                 |                                                                                  |
|                 +---> microclimate:readings       (Row: STATION#YYYYMMDD#REV_TS)                   |
|                 +---> microclimate:station_status (Row: STATION_ID)                                |
|                 +---> microclimate:alerts         (Row: STATION#REV_TS#ALERT_TYPE)                 |
|                                                                                                    |
|  [Apache HBase 2.6.7 (Standalone Mode) via Stargate REST Gateway (:8085)]                          |
|       ^                                                                                            |
|       | HTTP REST / XML / JSON Queries                                                             |
|       v                                                                                            |
|  [Flask REST API Layer (12 Endpoints, Port 5000)]                                                  |
|       ^                                                                                            |
|       | JSON Responses / Content Negotiation                                                       |
|       v                                                                                            |
|  [Interactive Web Dashboard (HTML5 / Bootstrap 5 / Leaflet.js / Chart.js / Vanilla ES6)]           |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 2.2 Operational Scope & Boundary Definitions
* **Data Nature:** Strictly synthetic data generated by deterministic diurnal mathematical models with Gaussian noise and scheduled anomaly scenario injection.
* **Geographical Anchors:** Five representative urban morphology stations in the Bengaluru metropolitan grid:
  - `ST001` (Bengaluru Central): Commercial / Urban Core (`12.9716, 77.5946`)
  - `ST002` (Bengaluru East): Tech Corridor / Dense Traffic (`12.9784, 77.6408`)
  - `ST003` (Bengaluru South): Residential / Green Canopy (`12.9250, 77.5938`)
  - `ST004` (Bengaluru West): Industrial / Transit Interchange (`12.9750, 77.5350`)
  - `ST005` (Bengaluru North): Highway / Peri-urban (`13.0358, 77.5970`)
* **Datastore:** Apache HBase 2.6.7 in standalone mode (single-process JVM running embedded ZooKeeper and Master/RegionServer) interfaced via the Stargate REST gateway on port 8085.

---

## 3. Implemented Components and Technical Design

| Subsystem | Implemented Files | Responsibilities | Evaluated Status |
| :--- | :--- | :--- | :--- |
| **Sensor Simulator** | `app/services/sensor_simulator.py` | Virtual station generation, diurnal solar cycles, NWS heat index calculation. | Implemented and inspected |
| **Ingestion Engine** | `app/services/ingestion_service.py` | Thread-safe queue buffer, worker loop, multi-table persistence. | Tested using isolated mocks |
| **Anomaly Detector** | `app/services/anomaly_detector.py` | Threshold rules, unphysical bounds checking, alert state machine (cooldown/escalation). | Tested using isolated mocks |
| **HBase Client** | `app/services/hbase_client.py` | Stargate REST HTTP wrapper, connection pooling, `urllib3` retry logic, row key builder. | Tested using isolated mocks |
| **Telemetry Service** | `app/services/telemetry_service.py` | Multi-date prefix scanning, time-series sorting, statistical aggregations, alert queries. | Tested using isolated mocks |
| **REST API** | `app/routes/api.py`, `app/__init__.py` | 12 `/api/v1` endpoints, 2 app routes, standardized JSON envelopes, parameter validation. | Tested using isolated mocks |
| **Command Dashboard**| `app/templates/index.html`, `app/static/js/*.js` | 8-section dark SPA, Chart.js time series, Leaflet map, alert acknowledgement modal. | Inspected & Browser Evidence |

---

## 4. HBase Schema, Row-Key Design and Retrieval Limitations

### 4.1 Schema Definition
The system persists data across three tables in the `microclimate` namespace:
1. `microclimate:readings`: Column families `metrics` (environmental values) and `metadata` (station ID, timestamps, data source).
2. `microclimate:station_status`: Column families `status` (live telemetry snapshot) and `metadata` (connectivity, last update).
3. `microclimate:alerts`: Column families `alert` (severity, measurement, threshold, message, calculation provenance) and `metadata` (station ID, timestamps, acknowledgement).

### 4.2 Row-Key Design Analysis
* **Readings Table Row Key:** `STATION_ID#YYYYMMDD#REVERSE_TIMESTAMP`
  - Where `REVERSE_TIMESTAMP = 9999999999999 - timestamp_ms`.
* **Technical Intent:** HBase stores row keys in lexicographical byte order. Inverting the timestamp ensures that newer records within a given station and UTC date partition sort first.
* **Retrieval Advantage:** Enables efficient chronological prefix scanning (`STATION#YYYYMMDD#`) to fetch the most recent telemetry without full table scans.
* **Architectural & Ingestion Limitation:**
  - *Write Hotspotting:* Prepending `STATION_ID#` groups writes by station. In a distributed multi-RegionServer HBase deployment, stations mapping to the same region would concentrate writes on a single server. Salt prefixes or hashed station IDs would be required to prevent write hotspots.
  - *Multi-Date Scanning Overhead:* Range queries spanning multiple calendar dates require separate prefix scans for each date partition, merged application-side in memory.

---

## 5. Literature Review Synthesis and Research Comparison

The system was evaluated against six verified peer-reviewed publications establishing benchmarks for urban microclimate sensing, Big Data ingestion, and biometeorological modeling:

```
+----------------------------------------------------------------------------------------------------+
|                                    PEER-REVIEWED RESEARCH COMPARISON                               |
+----------------------------------------------------------------------------------------------------+
| Study / Benchmark                  | Context & Methodology                   | Relationship to Project     |
+------------------------------------+-----------------------------------------+-----------------------------+
| Eingrüber et al. (2025)            | 12 locations (PU01–PU12) in Pune, India | Physical urban sensor       |
| J. Sens. Sens. Syst., 14(1), 13–26 | Quality-controlled sensor network.      | network benchmark.          |
|                                    | 59 sensors total (air, surface, rain).  | Project uses 5 nodes.       |
|                                    |                                         |                             |
| Lyu et al. (2022)                  | 1-km spatial resolution, 10-min freq,   | CyberGIS and ML spatial     |
| Urban Informatics, 1(1), Art. 6    | Random Forest MAE 0.45°C (2020) and     | prediction benchmark.       |
|                                    | 0.80°C (2018–2019) in Chicago (AoT).    | Project uses discrete nodes.|
|                                    |                                         |                             |
| Lefevre et al. (2024)              | Low-tech environmental station design   | Sensor hardware cost and    |
| Sustainability, 16(7), Art. 3093   | for urban microclimate monitoring.       | reproducibility benchmark.   |
|                                    | Open-source modular architecture.       | Project uses virtual nodes. |
|                                    |                                         |                             |
| Feigel et al. (2025)               | Freiburg, Germany: 13 Tier-I,           | Station metadata hierarchy  |
| Sustain. Cities Soc., 119, 105991  | 29 Tier-II, 42 total stations.          | and outdoor thermal comfort |
| (DOI: 10.1016/j.scs.2024.105991)   | Continuous thermal comfort monitoring.  | benchmark (uniWeather).     |
|                                    |                                         |                             |
| Chakraborty et al. (2022)          | Global urban moisture deficit study.    | Biometeorological context   |
| AGU Advances, 3(5), e2022AV000729  | European clusters Fig 7(c) r² = 0.04    | benchmark. Project uses     |
|                                    | (dry-bulb vs apparent heat index).      | rule-based alert triggers.  |
|                                    |                                         |                             |
| Steadman (1979) / Rothfusz (1990)  | Official US National Weather Service    | Algorithmic reference for   |
| NOAA NWS Technical Attachment SR90 | biometeorological heat index equations. | project heat-index formula. |
+----------------------------------------------------------------------------------------------------+
```

### Critical Epistemic Distinctions:
1. **Mathematical Algorithm Parity vs. Real-World Accuracy:** Independent formula parity proves that the project correctly computes the mathematical equations published by NOAA. It does **not** prove environmental accuracy in the urban canopy layer of Bengaluru.
2. **Operational Engineering Rules vs. Epidemiological Models:** The project's threshold alerts ($\ge 35^\circ\text{C}$ temperature, $\ge 60\ \mu\text{g/m}^3\ \text{PM}_{2.5}$, $\ge 38^\circ\text{C}$ heat index) are user-defined software triggers, not clinically validated public-health danger thresholds.
3. **Indicative Instantaneous Particulates vs. Official CPCB NAQI:** The dashboard compares instantaneous measurements against Central Pollution Control Board (CPCB) category breakpoints. This does **not** constitute the official composite 24-hour Indian National Air Quality Index (NAQI).

---

## 6. Performance Evaluation: Scope and Epistemic Boundaries

### 6.1 Verified Quantitative Baselines
Empirical benchmarks executed in Phase 8.4.2 established the following performance baselines:
* **In-Memory Buffer Capacity:** Configured at 1,000 items. Saturated burst test (500 items attempted against full queue) verified strict drop-on-full semantics: **0 items accepted, 500 items rejected (100% rejection)**.
* **FIFO Ordering:** 200 items drained sequentially verified 100.0% strict chronological preservation ($|\Delta_{\text{order}}| = 0$).
* **Worker Ingestion Processing Throughput:** Measured at **$31,765\ \text{records/sec}$** (mean elapsed time $31.48\ \text{ms}$ across 1,000 items) when persisting to a mocked backend.
* **HTTP Client Session Retry Backoff:** 3 retries (4 total attempts) with exponential backoff scheduled at `[0.0s, 0.6s, 1.2s]`, totaling $1.804\ \text{s}$ to exhaustion. In-flight recovery on attempt 3 completed in $0.603\ \text{s}$.

### 6.2 Epistemic Performance Boundaries
* **Mocked Worker Throughput is NOT HBase Throughput:** The $31,765\ \text{rec/s}$ figure measures in-memory CPU processing speed (deserialization, anomaly checks, and JSON formatting). Real network writes across the Stargate REST gateway would be bound by TCP handshake latency, HTTP serialization, and HBase write-ahead log (WAL) sync overhead.
* **Live Query Benchmark Blocked:** Performance testing against live HBase was not conducted during the non-destructive audit because the HBase REST service was not active.

---

## 7. Reliability and Fault-Handling Evaluation

Controlled mock injection experiments in Phase 8.4.3 evaluated system behavior across six failure dimensions:

```
+----------------------------------------------------------------------------------------------------+
|                                    RELIABILITY EVALUATION SUMMARY                                  |
+----------------------------------------------------------------------------------------------------+
| Dimension Tested                   | Test Condition                          | Evaluated Behaviour |
+------------------------------------+-----------------------------------------+---------------------+
| Ingestion Buffer Saturation        | Burst insertion beyond capacity (1,000) | Drop-on-full active;|
|                                    |                                         | 500/500 rejected    |
| HTTP Session Transport Retries     | HTTP 500, 502, 503, 504, ConnectionFail | 3 retries, 4 attempts|
|                                    |                                         | backoff [0,0.6,1.2]s|
| Secondary Table Failure Masking    | Failure of TABLE_STATION_STATUS write   | DEFECT: Ignored bool|
|                                    |                                         | misreports success  |
| Multi-Table Failure Atomicity      | Failure after TABLE_READINGS written    | LIMITATION: Partial |
|                                    |                                         | write leaves split  |
| Non-Finite IEEE 754 Values         | Input of float('nan') to telemetry      | DEFECT: Bypasses    |
|                                    |                                         | guards, writes NaN  |
| Flagged Raw Telemetry Retention    | Out-of-bounds readings (±inf, >65°C)    | INTENTIONAL: Stored |
|                                    |                                         | with INVALID alert  |
| Station ID Whitelist Enforcement   | Unmanaged station string (ST999)        | GAP: API rejects,   |
|                                    |                                         | worker accepts      |
| API Internal Exception Disclosure  | Route exceptions during HTTP 500        | RISK: Leaks socket  |
|                                    |                                         | codes and local URLs|
+----------------------------------------------------------------------------------------------------+
```

---

## 8. Heat-Index Accuracy and Anomaly-Detection Evaluation

### 8.1 Numerical Accuracy Reconciled
* Evaluated across **42 atmospheric test conditions**: 40 passed, 2 failed strictly due to confirmed defect RF-02 (`NaN` inputs).
* **Parity Rate across Valid Atmospheric Cases:** **100.0%** ($|\Delta| \le 0.05^\circ\text{C}$).
* **Maximum Absolute Difference:** **$0.004647^\circ\text{C}$** at $T = 30.0^\circ\text{C}, RH = 90.0\%$ (Project Output: $40.77^\circ\text{C}$; Reference Output: $40.774647^\circ\text{C}$).
* **Mean Absolute Difference:** **$0.002212^\circ\text{C}$**.
* **Precision Reconciliation:** Rounding the full double-precision reference output to two decimal places produces `round(40.774647, 2) == 40.77`, yielding **$0.000000^\circ\text{C}$ difference**. Across all 25 tested cases, observed differences are consistent with the project's two-decimal output rounding ($\le 0.005^\circ\text{C}$ half-step window).

### 8.2 Preliminary Average Discontinuity Reconciled
The exact preliminary-average equation is:

$$HI_{\text{avg}} = 0.5 \times (HI_{\text{simple}} + T_F) = 1.05\,T_F - 5.15 + 0.0235\,RH$$

At $T_F = 80.0^\circ\text{F}$:
* For $RH = 40.0\%$, $HI_{\text{avg}} = 79.790^\circ\text{F} < 80.0^\circ\text{F}$ (Steadman branch).
* For $RH = 42.0\%$, $HI_{\text{avg}} = 79.837^\circ\text{F} < 80.0^\circ\text{F}$ (Steadman branch).
* The actual threshold $HI_{\text{avg}} \ge 80.0^\circ\text{F}$ occurs at **$RH = 48.93617\%$**:
  - Immediately below ($RH = 48.936\%$): Evaluates to Steadman branch yielding **$26.67^\circ\text{C}$ ($80.00^\circ\text{F}$)**.
  - At and above ($RH = 48.940\%$): Evaluates to Rothfusz regression yielding **$27.06^\circ\text{C}$ ($80.71^\circ\text{F}$)**.
  - **Verified Step Jump:** **$+0.39^\circ\text{C}$ ($+0.71^\circ\text{F}$)** across the boundary at $T_F = 80.0^\circ\text{F}$ (or **$+0.4344^\circ\text{C}$ / $+0.7819^\circ\text{F}$** at fixed $RH = 50.0\%$ across temperature at $T_F = 79.976^\circ\text{F}$ in Phase 7.4).
  - **Defensible Conclusion:** The piecewise jump discontinuity is confirmed as an inherent mathematical property of the published NOAA WPC specification.

### 8.3 Anomaly Detection & State Machine Reconciled
* **37 / 37 Individual Rules Passed (100.0%):** Strict relational checking across Temperature, PM2.5, PM10, Heat Index, and Hardware Offline/Error states.
* **Absence of Standalone RH Anomaly Rule:** Source inspection confirms there is **no standalone Relative Humidity threshold alert rule** (e.g. `HIGH_HUMIDITY`). Humidity is checked only for physical sensor violations ($[0, 100]\%$) triggering `INVALID_READING`, and acts as an input to `HIGH_HEAT_INDEX`.
* **8 / 8 Lifecycle Steps Verified:** Initial emission, cooldown suppression (60s), immediate severity escalation (Warning $\rightarrow$ Critical), cooldown expiration re-emission (65s), recovery condition clearing, and simultaneous multi-metric alerts.

---

## 9. REST API and Dashboard Evaluation

### 9.1 REST API Evaluation Breakdown (56 Test Cases Reconciled)
A comprehensive battery of **56 test cases** was evaluated with 100.0% pass rate:
1. **Functional Endpoints (16 cases):** All 12 `/api/v1` routes, 2 top-level app routes (`/` HTML vs JSON, `/dashboard`), and operational vs degraded health check.
2. **Input Validation & Errors (27 cases):** Missing parameters, unknown stations (404), invalid limits (400), invalid order (400), invalid measurements (400), inverted date ranges (400), missing simulator actions (400), and unsupported HTTP methods (405).
3. **Security & Exception Handling (6 cases):** Route exception handlers tested under injected connection failures, re-verifying exception leakage (RF-07).
4. **Data Consistency (7 cases):** Multi-date ordering (desc/asc), measurement projection, provenance formatting (`VALID` vs `LEGACY_UNVERIFIED`), explicit 0.0 vs None ranking, and empty database responses.
* **Total Evidenced Test Cases:** $16 + 27 + 6 + 7 = 56$ (100% accounted for in `api_evaluation_results.json`).

### 9.2 Dashboard Evidence Categorization
* **DOM & JS Source Inspection:** Verified all 8 sections, 6 summary KPI cards, 5 Chart.js canvases, Leaflet container (`#station-map`), and stateful modals (`#stationDetailModal`, `#acknowledgeModal`).
* **Academic Disclosures:** Verified static `SIMULATED DATA` and `SIMULATED STATIONS` badges, CPCB NAQI instantaneous indicative disclaimer, and NWS Rothfusz methodology notes.
* **Visualization Integrity:** Verified `spanGaps: false` across all charts to prevent fabricating missing data as zero.
* **Failure Handling:** `api.js` captures network drops (`status: 0`), `app.js` displays "HBase Degraded" pills, and 10s auto-refresh enforces `isRefreshing` overlap lock.
* **Responsive CSS Inspection:** Verified `@media` breakpoints for 992px (collapsible tablet drawer), 768px (single-column mobile cards), and 576px (compact layout), along with horizontal table scrolling (`.table-responsive-custom`).
* **Existing Browser QA Evidence:** Cataloged Chromium Playwright artifacts (`dashboard_overview.png`, `heat_risk_intelligence.png`, `station_infrastructure.png`). Live browser execution was not repeated during this offline audit.

---

## 10. Consolidated Findings, Defects and Classifications

```
+-----------------------------------------------------------------------------------------------------------------------------+
|                                             CONSOLIDATED FINDINGS MATRIX                                                    |
+-----------------------------------------------------------------------------------------------------------------------------+
| ID    | Component            | Classification       | Impact / Observed Result                          | Priority | Action |
+-------+----------------------+----------------------+---------------------------------------------------+----------+--------+
| RF-01 | IngestionService     | CONFIRMED DEFECT     | Ignores put_row() return boolean for status and    | Critical | Fix    |
|       |                      |                      | alert tables; misreports complete ingestion success.|          |        |
| RF-02 | AnomalyDetector      | CONFIRMED DEFECT     | IEEE 754 NaN bypasses relational comparisons;     | Critical | Fix    |
|       |                      |                      | writes status: VALID with NaN heat index to HBase.|          |        |
| RF-07 | Flask Routes (api.py)| SECURITY RISK        | 500 error handlers format user messages via       | High     | Fix    |
|       |                      |                      | {str(e)}, leaking internal OS socket error codes. |          |        |
| RF-06 | IngestionService     | VALIDATION GAP       | Ingestion accepts arbitrary station strings;      | Medium   | Align  |
|       |                      |                      | API validates against whitelist (no explicit req).|          |        |
| RF-09 | REST Routing (api.py)| DESIGN LIMITATION    | Unencoded '#' in alert row key triggers URI path  | Medium   | Guide  |
|       |                      |                      | fragment truncation, returning 404 NOT_FOUND.     |          |        |
| RF-03 | Ingestion Architecture| DESIGN LIMITATION   | Multi-table writes lack distributed transactions; | Arch.    | Review |
|       |                      |                      | partial failure leaves tables out of sync.        |          |        |
| RF-04 | Ingestion Worker     | DESIGN LIMITATION    | Persistence failure drops unwritten records       | Arch.    | Review |
|       |                      |                      | without an on-disk Dead-Letter Queue (DLQ).       |          |        |
| RF-05 | Ingestion / Anomaly  | INTENTIONAL BEHAVIOUR| Preserves flagged raw sensor telemetry (±inf) in  | None     | Retain |
|       |                      |                      | readings table (project policy, not formal std).  |          |        |
| RF-08 | HBaseClient          | VERIFIED DESIGN      | HTTP session retries (3 retries, exponential      | None     | Retain |
|       |                      |                      | backoff [0, 0.6, 1.2]s) verified at transport.   |          |        |
| RF-10 | App Factory (init.py)| VERIFIED DESIGN      | Clean content negotiation on '/' and dedicated    | None     | Retain |
|       |                      |                      | '/dashboard' HTML route.                          |          |        |
| RF-11 | Response Utilities   | VERIFIED DESIGN      | Uniform JSON response envelopes across success    | None     | Retain |
|       |                      |                      | and error responses.                              |          |        |
| RF-12 | Charts (charts.js)   | VERIFIED DESIGN      | Enforces spanGaps: false; never fabricates        | None     | Retain |
|       |                      |                      | missing or null telemetry as zero.                |          |        |
| RF-13 | App (app.js)         | VERIFIED DESIGN      | 10s auto-refresh polling incorporates             | None     | Retain |
|       |                      |                      | isRefreshing execution lock.                      |          |        |
+-----------------------------------------------------------------------------------------------------------------------------+
```

---

## 11. Academic and Practical Limitations

1. **Simulation vs. Physical Microclimate Realities:** The system relies entirely on synthetic mathematical generator functions. Phenomena such as urban canyon shading, anthropogenic traffic heat spikes, and convective rainfall cooling are simulated deterministically and do not reflect empirical field sensor observations.
2. **Standalone vs. Distributed HBase Limitations:** Standalone HBase runs ZooKeeper, Master, and RegionServer in a single JVM process on local filesystem storage. True distributed-system failure modes (RegionServer split-brain, ZooKeeper quorum partitions, distributed WAL replication lag) cannot be evaluated on this prototype.
3. **Queue Eviction and Storage Resilience:** In the event of sustained database downtime exceeding the 1,000-item queue buffer, incoming telemetry is permanently dropped in memory due to the lack of an on-disk dead-letter queue.
4. **Offline Evaluation Boundary:** In strict compliance with academic audit preservation rules, live HBase writes and daemon execution were halted during evaluation.

---

## 12. Recommended Corrective Actions (Prioritised)

1. **Remediation 1 (Priority: Critical — RF-02):**  
   Add an explicit finite numeric guard in `app/services/anomaly_detector.py`:
   ```python
   if not math.isfinite(val):
       return True  # Flag immediately as unphysical / corrupt
   ```
2. **Remediation 2 (Priority: Critical — RF-01):**  
   Inspect the boolean return values of all secondary table writes (`put_row()` for `microclimate:station_status` at line 164 and `put_row()` for `microclimate:alerts` at line 175) in `app/services/ingestion_service.py`. If any write fails, do not record complete ingestion success; increment `total_failed` (or introduce a distinct `partial_persistence_count`) and log an error diagnostic.
3. **Remediation 3 (Priority: High — RF-07):**  
   Replace `{str(e)}` concatenation in `app/routes/api.py` with sanitized, generic client messages (e.g., `"An internal database error occurred. Please contact the administrator."`) while logging the traceback server-side.
4. **Remediation 4 (Priority: Medium — RF-06):**  
   Align station-ID validation across components if stakeholder requirements specify strict rejection, or document that `IngestionService` intentionally accepts dynamic unlisted station IDs. In the absence of a documented rejection requirement, this is maintained as a validation gap.
5. **Remediation 5 (Priority: Medium — RF-09):**  
   Update API documentation and provide alternative URL routing (e.g. Base64-encoding row keys or passing row keys as query parameters) to protect external REST clients from URI `#` fragment truncation.
6. **Remediation 6 (Priority: Architectural — RF-04 & RF-03):**  
   Implement an on-disk spillover log (SQLite or append-only JSONL) for persistence failures, and evaluate application-level saga compensation across multi-table writes.

---

## 13. Overall Evaluation and Defensible Conclusions

The Urban Microclimate & Heat-Risk Intelligence System demonstrates robust architectural engineering, strict mathematical fidelity to published biometeorological algorithms, and a highly responsive, well-instrumented command-center interface.

The evaluation conclusively establishes:
1. **Algorithmic Correctness:** The project's implementation of the US NWS Steadman and Rothfusz algorithms is mathematically verified ($100\%$ parity within two-decimal rounding precision).
2. **Prototype Scope:** The system is an educational prototype running standalone HBase on synthetic telemetry, not a physical sensor network or certified meteorological tool.
3. **Transparent Auditability:** All identified defects (RF-01, RF-02, RF-07), design limitations (RF-03, RF-04, RF-09), and mathematical boundary behaviors have been fully isolated, evidenced, and prioritized for college submission.

---

## 14. References

1. **Chakraborty, T., Venter, Z. S., Qian, Y., & Lee, X.** (2022). *Lower Urban Humidity Moderates Outdoor Heat Stress.* **AGU Advances**, 3(5), e2022AV000729. [DOI: 10.1029/2022AV000729](https://doi.org/10.1029/2022AV000729).
2. **Eingrüber, N., Korres, W., Löhnert, U., & Schneider, K.** (2025). *Setup of a densely distributed and quality-controlled meteorological sensor network in Pune, India, for urban microclimate research and citizen participation in the context of climate change adaptation.* **Journal of Sensors and Sensor Systems**, 14(1), 13–26. [DOI: 10.5194/jsss-14-13-2025](https://doi.org/10.5194/jsss-14-13-2025).
3. **Feigel, G., Plein, M., Zeeman, M., Metzger, S., Matzarakis, A., Schindler, D., & Christen, A.** (2025). *High spatio-temporal and continuous monitoring of outdoor thermal comfort in urban areas: A generic and modular sensor network and outreach platform.* **Sustainable Cities and Society**, 119, 105991. [DOI: 10.1016/j.scs.2024.105991](https://doi.org/10.1016/j.scs.2024.105991).
4. **Lefevre, A., Malet-Damour, B., Boyer, H., & Rivière, G.** (2024). *Advancing Urban Microclimate Monitoring: The Development of an Environmental Data Measurement Station Using a Low-Tech Approach.* **Sustainability**, 16(7), 3093. [DOI: 10.3390/su16073093](https://doi.org/10.3390/su16073093).
5. **Lyu, F., Wang, S., Han, S. Y., Catlett, C., & Wang, S.** (2022). *An integrated cyberGIS and machine learning framework for fine-scale prediction of Urban Heat Island using satellite remote sensing and urban sensor network data.* **Urban Informatics**, 1(1), Article 6. [DOI: 10.1007/s44212-022-00002-4](https://doi.org/10.1007/s44212-022-00002-4).
6. **Rothfusz, L. P.** (1990). *The Heat Index Equation (or, More Than You Ever Wanted to Know About Heat Index).* **National Oceanic and Atmospheric Administration (NOAA) National Weather Service (NWS)** Technical Attachment SR 90-23.
7. **Steadman, R. G.** (1979). *The Assessment of Sultriness. Part I: A Temperature-Humidity Index Based on Human Physiology and Clothing Science.* **Journal of Applied Meteorology**, 18(7), 861–873. [DOI: 10.1175/1520-0450(1979)018<0861:TAOSPI>2.0.CO;2](https://doi.org/10.1175/1520-0450(1979)018<0861:TAOSPI>2.0.CO;2).
