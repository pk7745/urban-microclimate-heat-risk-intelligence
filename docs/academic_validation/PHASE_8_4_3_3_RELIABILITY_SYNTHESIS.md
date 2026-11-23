# Phase 8.4.3.3 — Reliability Evaluation Synthesis

**Project:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Document:** `docs/academic_validation/PHASE_8_4_3_3_RELIABILITY_SYNTHESIS.md`  
**Evaluation Date:** November 2026  
**Auditor:** Academic Technical Review Team  
**Underlying Reports:**
- [`docs/academic_validation/PHASE_8_4_3_1_RELIABILITY_RESULTS.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/PHASE_8_4_3_1_RELIABILITY_RESULTS.md)
- [`docs/academic_validation/PHASE_8_4_3_2_RELIABILITY_FINDING_VERIFICATION.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/PHASE_8_4_3_2_RELIABILITY_FINDING_VERIFICATION.md)
**Underlying Data Artifacts:**
- [`docs/academic_validation/scripts/reliability_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/reliability_results.json)
- [`docs/academic_validation/scripts/reliability_verification_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/reliability_verification_results.json)
- [`docs/academic_validation/scripts/reliability_synthesis_summary.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/reliability_synthesis_summary.json)  
**Evaluation Status:** **SYNTHESIZED & VERIFIED**

---

## 1. Executive Summary & Synthesis Objective

Phase 8.4.3.3 synthesizes the empirical evaluations conducted in Phase 8.4.3.1 (Reliability & Fault-Handling Evaluation) and Phase 8.4.3.2 (Reliability Finding Verification & Retry Semantics) into a consolidated, definitive academic report. The objective of this phase is documentation, evidence reconciliation, and architectural analysis only; no application source code, configuration, test files, or database states have been altered.

The evaluation demonstrates that the Urban Microclimate & Heat-Risk Intelligence System possesses strong operational resilience in its decoupled buffer ingestion and consumer daemon execution, surviving malformed inputs, single-record exceptions, and transient network dropouts without worker crashes. Concurrently, the evaluation reveals two confirmed implementation defects (silent masking of secondary write failures and IEEE 754 NaN bypass), two architectural design limitations (multi-table non-atomicity and absence of a persistent dead-letter queue), two validation gaps (ingestion station whitelist absence and API information disclosure), and two verified deliberate designs (raw telemetry persistence and HTTP session retries).

---

## 2. Evidence Reconciliation & Methodology

Every reported reliability finding from Phase 8.4.3.1 was cross-referenced against the independent reproduction harness in Phase 8.4.3.2 and the ground truth codebase. All findings are classified using strict, mutually exclusive epistemic categories:

* **CONFIRMED DEFECT:** The codebase implementation contains an explicit programming error or unintended logic path that contradicts intended behavior, causes silent masking, or corrupts data structures.
* **DESIGN LIMITATION:** An inherent architectural constraint resulting from chosen infrastructure primitives (e.g., Apache HBase REST lacking distributed transactions) or prototype scope boundaries (in-memory queues).
* **INTENTIONAL BEHAVIOUR:** A deliberate architectural choice aligned with meteorological domain requirements (e.g., storing raw sensor data alongside anomaly tags for auditability).
* **VALIDATION GAP:** A missing boundary check or discrepancy between subsystems (e.g., API vs. Ingestion) that does not violate a formal functional contract but creates operational inconsistency.
* **SECURITY RISK:** An implementation pattern that leaks sensitive runtime, infrastructure, or topology details to untrusted clients.
* **VERIFIED DESIGN:** An implemented subsystem proven through controlled testing to operate strictly according to its configured specification.
* **NOT REPRODUCED:** A previously claimed defect or behavior that failed to manifest under reproducible testing.
* **NOT EVALUATED:** A scenario excluded due to non-destructive safety constraints (e.g., live cluster partition splits).

---

## 3. Consolidated Reliability Findings

The eight consolidated findings are detailed below with verified source code locations, empirical evidence, and remediation guidance:

### RF-01: Silent Masking of Station-Status Persistence Failures
* **Technical Description:** In `IngestionService._process_single_reading`, the write to `microclimate:station_status` occurs after `microclimate:readings` succeeds. The code invokes `put_row()` but completely ignores its boolean return value.
* **Component Involved:** [`app/services/ingestion_service.py` line 164](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L164).
* **Direct Evidence:** In Phase 8.4.3.2 Case 3, when `TABLE_STATION_STATUS` returned `False`, `metrics["total_ingested"]` incremented by 1, while `metrics["total_failed"]` remained 0.
* **Classification:** **CONFIRMED DEFECT**.
* **Reliability Impact:** Live station connectivity and current temperature status become silently stale while historical readings advance, presenting false data in dashboard views while telemetry counters falsely report 100% operational success.
* **Scope & Limitations:** Affects `microclimate:station_status`. Readings are successfully committed.
* **Remediation Recommended:** Capture the return value of `put_row(TABLE_STATION_STATUS)`; increment `total_failed` or log an explicit warning if it fails.

---

### RF-02: IEEE 754 NaN Bypasses Unphysical Sanity Checks
* **Technical Description:** Python IEEE 754 floating-point comparisons evaluate to `False` for any relational operator (`<`, `>`, `<=`, `>=`) against `float('nan')`. The sanity check `temp < -10.0 or temp > 65.0` evaluates to `False`.
* **Component Involved:** [`app/services/anomaly_detector.py` lines 195–210](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/anomaly_detector.py#L195-L210), [`app/services/sensor_simulator.py` lines 77–81](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/sensor_simulator.py#L77-L81).
* **Direct Evidence:** Feeding `temperature_celsius = float('nan')` resulted in `_is_reading_unphysical()` returning `False`. `AnomalyDetector` emitted 0 alerts, `assess_heat_index()` returned `status: "VALID"` with `heat_index_celsius: NaN`, and the value was encoded to Base64 and committed to HBase as string `"nan"`.
* **Classification:** **CONFIRMED DEFECT**.
* **Reliability Impact:** Corrupt non-numeric telemetry bypasses anomaly detection and contaminates HBase storage, potentially breaking downstream mathematical aggregation routines.
* **Scope & Limitations:** Affects `temperature_celsius`, `humidity_percent`, `pm25`, and `pm10` fields.
* **Remediation Recommended:** Add explicit `math.isnan(val)` or `not math.isfinite(val)` guards before executing relational boundary checks.

---

### RF-03: Sequential Multi-Table Writes are Non-Atomic
* **Technical Description:** A single ingested sensor reading triggers sequential HTTP PUT calls across three distinct HBase tables: `microclimate:readings`, `microclimate:station_status`, and optionally `microclimate:alerts`.
* **Component Involved:** Ingestion pipeline and HBase REST gateway architecture ([`app/services/ingestion_service.py` lines 140–193](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L140-L193)).
* **Direct Evidence:** Phase 8.4.3.2 Cases 3, 4, and 5 demonstrated that failures on secondary tables leave committed rows in `microclimate:readings` without corresponding updates in `station_status` or `alerts`.
* **Classification:** **DESIGN LIMITATION**.
* **Reliability Impact:** Network glitches or gateway timeouts during secondary writes produce cross-table state inconsistencies without automated compensatory rollback.
* **Scope & Limitations:** An inherent characteristic of Apache HBase; atomic mutations exist only within a single row mutation on a single table. Distributed cross-table transactions require external frameworks (e.g., Apache Tephra or Omid).
* **Remediation Recommended:** Document as an architectural trade-off; consider application-level retry/compensation or single-table consolidated schemas for future production architectures.

---

### RF-04: Absence of a Dead-Letter Queue (DLQ)
* **Technical Description:** Records that fail database persistence (due to gateway downtime, timeouts, or unhandled serialization errors) are logged via `logger.error` and discarded from memory.
* **Component Involved:** Ingestion buffer architecture ([`app/services/ingestion_service.py` lines 141–145](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L141-L145)).
* **Direct Evidence:** During simulated 5-record gateway outages in Scenario E, all 5 records failed (`total_failed = 5`) and were permanently dropped. When connectivity was restored, only new in-flight records were ingested.
* **Classification:** **DESIGN LIMITATION**.
* **Reliability Impact:** Transient persistence outages cause irrecoverable data loss during the outage window.
* **Scope & Limitations:** In-memory queue buffering was explicitly designed as a lightweight prototype architecture for streaming simulation. A disk-backed store-and-forward queue was out of scope for Phase 1–3 specifications.
* **Remediation Recommended:** Maintain as an academic baseline limitation; recommend an on-disk SQLite or WAL-backed spillover queue for production deployment.

---

### RF-05: Persistence of Flagged Raw Telemetry
* **Technical Description:** Telemetry readings with temperatures outside the configured sanity envelope (e.g., $70.0^\circ\text{C}$, $-20.0^\circ\text{C}$, or $\pm\infty$) trigger `INVALID_READING` alerts but are nonetheless persisted to `microclimate:readings` and `microclimate:station_status`.
* **Component Involved:** Ingestion and anomaly detection pipeline ([`app/services/ingestion_service.py` lines 122–140](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L122-L140)).
* **Direct Evidence:** In Phase 8.4.3.1 Tests B11 and B12, readings at $70.0^\circ\text{C}$ and $-20.0^\circ\text{C}$ triggered `CRITICAL` severity `INVALID_READING` alerts, yet both were written to HBase tables (`total_ingested` delta +1).
* **Classification:** **INTENTIONAL BEHAVIOUR**.
* **Reliability Impact:** Allows historical auditability and sensor hardware forensics. Raw sensor outputs are preserved alongside anomaly metadata rather than silently discarded.
* **Scope & Limitations:** Downstream analytics must query and filter readings using the corresponding `microclimate:alerts` records.
* **Remediation Recommended:** Preserve current design; verify that downstream query consumers apply alert masks where pristine data is required.

---

### RF-06: Missing Station Whitelist in Ingestion Engine
* **Technical Description:** While the Flask REST API strictly enforces `VALID_STATION_IDS = {'ST001'..'ST005'}`, the `IngestionService` accepts arbitrary station identifiers (e.g., `ST999`).
* **Component Involved:** Ingestion worker ([`app/services/ingestion_service.py` line 118](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L118)).
* **Direct Evidence:** Submitting `station_id="ST999"` resulted in successful row-key construction (`ST999#20261117#8205058799999`) and persistence to `microclimate:readings` and `microclimate:station_status`. In contrast, `GET /api/v1/stations/ST999` returned HTTP 404.
* **Classification:** **VALIDATION GAP**.
* **Reliability Impact:** Misconfigured or rogue edge devices can ingest data under unmanaged station prefixes, polluting the HBase table namespace.
* **Scope & Limitations:** Prototype specifications did not explicitly forbid dynamic station onboarding; the gap represents an architectural inconsistency between the API and ingestion layers.
* **Remediation Recommended:** Add an ingestion-layer validation guard against `VALID_STATION_IDS` if dynamic onboarding is not supported.

---

### RF-07: Internal Exception Disclosure on HTTP 500 Responses
* **Technical Description:** Unhandled runtime errors in API route handlers format user-facing messages by directly concatenating Python exception text (`f"...: {str(e)}"`).
* **Component Involved:** Flask API route handlers ([`app/routes/api.py` lines 80, 106, 145, 203, 252](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/routes/api.py#L80)).
* **Direct Evidence:** Injected connection failures and timeouts returned messages disclosing raw Windows socket codes (`[WinError 10061] No connection could be made because the target machine actively refused it`) and internal URLs (`http://localhost:8085`).
* **Classification:** **SECURITY RISK**.
* **Reliability Impact:** Discloses operating system error codes, internal network endpoints, and stack trace information to external clients, violating CWE-209 (Generation of Error Message Containing Sensitive Information).
* **Scope & Limitations:** Affects HTTP 500 responses across telemetry, station, and alert endpoints.
* **Remediation Recommended:** Return sanitized client-facing error strings (e.g., `"An internal error occurred while communicating with the storage backend"`) while preserving full stack traces in server logs.

---

### RF-08: HBase Client HTTP Session Retry Mechanism
* **Technical Description:** `HBaseClient._create_session()` configures an `HTTPAdapter` with `urllib3.util.Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504], raise_on_status=False)`.
* **Component Involved:** HTTP transport layer ([`app/services/hbase_client.py` lines 95–106](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/hbase_client.py#L95-L106)).
* **Direct Evidence:** Verified through real `urllib3` transport execution: executes exactly 4 attempts (1 initial + 3 retries) with delays of $0.0\text{s}$, $0.6\text{s}$, and $1.2\text{s}$ (total elapsed $1.804\text{s}$). Successfully recovers in-flight on transient failures before exhausting retries.
* **Classification:** **VERIFIED DESIGN**.
* **Reliability Impact:** Protects against transient Stargate servlet hiccups and brief network blips without manual intervention.
* **Scope & Limitations:** Retries connection errors and HTTP 500/502/503/504; socket read timeouts are not retried by default under urllib3 non-idempotent semantics.
* **Remediation Recommended:** None; operates strictly as designed.

---

## 4. Evaluation Across Six Reliability Dimensions

```
+----------------------------------------------------------------------------------------------------+
|                               THE SIX EVALUATED RELIABILITY DIMENSIONS                             |
+----------------------------------------------------------------------------------------------------+
|  1. QUEUE RELIABILITY          | Bounded 1,000 capacity; non-blocking drop; strict FIFO preserved. |
|  2. PERSISTENCE RELIABILITY    | Multi-table non-atomic; status failure masking; no DLQ.            |
|  3. FAULT TOLERANCE            | 4-attempt HTTP retry with backoff; clean failure return.          |
|  4. INPUT VALIDATION           | Missing keys caught; types guarded; NaN comparison defect found.   |
|  5. API RELIABILITY & SECURITY | Standardized error envelope; 503 on degraded; exception leakage.  |
|  6. RECOVERY & CONTINUITY      | Daemon survives bad records; in-flight recovery on restoration.   |
+----------------------------------------------------------------------------------------------------+
```

### 4.1 Queue Reliability
- **Bounded Buffer Protection:** Configured with `maxsize=1000`. When saturated, non-blocking `put(block=False)` drops incoming records immediately, preventing thread starvation in upstream sensor generation.
- **Drop Accounting:** Rejected records increment `metrics["dropped_due_to_queue_full"]`. Tested with 500 overflow records: exactly 500 drops recorded, buffer size remained at 1,000.
- **FIFO Order Integrity:** Draining 200 items from a full buffer verified that the first item popped matched $t_0 = 1794940000000$ and the 200th matched $t_{199} = 1794940000199$.
- **Buffer Reusability:** Once capacity freed up, the buffer accepted 100 new submissions without latency degradation.
- **Task Accounting:** All 1,100 consumed items were acknowledged via `task_done()`; `queue.join()` completed with zero deadlock.

### 4.2 Persistence Reliability
- **Readings Table:** Primary persistence operates reliably. If `TABLE_READINGS` fails, ingestion aborts immediately, `total_failed` increments, and secondary writes are skipped.
- **Station Status Table:** Unreliable failure accounting. If `TABLE_STATION_STATUS` fails, the failure is ignored, leaving partial writes in HBase while reporting complete success.
- **Alert Table:** If `TABLE_ALERTS` fails, the error is logged, but the record is counted as ingested.
- **Absence of DLQ:** Persistent outages result in permanent data loss; no store-and-forward spool exists.

### 4.3 Fault Tolerance
- **Connection Refusal:** Retried across 4 attempts with exponential backoff; cleanly returns `False` on exhaustion.
- **Read Timeout:** Retried across 4 attempts; cleanly returns `False` on exhaustion.
- **HTTP 500/502/503/504:** All server error status codes trigger retries up to configured limits.
- **In-Flight Recovery:** Proved that transient gateway failures recovering on attempt 2 or 3 succeed without data loss.

### 4.4 Input Validation
- **Missing Required Fields:** Missing `station_id` or `timestamp_ms` triggers `KeyError`, caught by worker loop, incrementing `total_failed`.
- **Non-Numeric Types:** String or list types trigger `TypeError` in `_is_reading_unphysical()`, caught by worker loop.
- **IEEE 754 NaN Defect:** `float('nan')` bypasses unphysical checks and persists to HBase as string `"nan"`.
- **Infinities & Out-of-Bounds:** Flagged as `INVALID_READING` alerts and persisted to HBase.
- **Station Whitelist:** Ingestion lacks station validation, accepting arbitrary station identifiers.

### 4.5 API Reliability and Security
- **Health Check Resilience:** `GET /api/v1/health` correctly returns HTTP 503 (`SERVICE_UNAVAILABLE`) when HBase REST is unreachable or tables are missing.
- **Parameter Validation:** Malformed parameters return HTTP 400 (`INVALID_LIMIT`, `INVALID_ORDER`); unknown stations return HTTP 404 (`STATION_NOT_FOUND`).
- **Process vs. Service Availability:** When backend persistence fails, the Flask WSGI process remains healthy and responsive, returning structured HTTP 500 responses.
- **Exception Leakage:** HTTP 500 error messages concatenate raw Python exception strings, disclosing internal hostnames, ports, and Windows socket error codes.

### 4.6 Recovery and Continuity
- **Daemon Survival:** `_worker_loop` wraps per-item processing in `try...except Exception...finally: task_done()`. Corrupt or failing records increment `total_failed` without killing the background consumer thread.
- **Subsequent Record Processing:** A valid record submitted immediately after a crashing record processes successfully.
- **Outage Recovery:** Once backend connectivity recovers, ingestion resumes automatically without requiring service restarts. Records dropped during the outage are permanently lost.

---

## 5. Quantitative Evidence Synthesis

All quantitative metrics cited below are sourced directly from the verified raw JSON outputs ([`reliability_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/reliability_results.json) and [`reliability_verification_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/reliability_verification_results.json)):

| Evaluation Parameter | Configuration / Origin | Measured / Observed Value | Epistemic Category |
| :--- | :--- | :--- | :--- |
| **Ingestion Buffer Capacity** | `settings.INGESTION_QUEUE_MAXSIZE` | **1,000 records** | Configured Parameter |
| **Tested Buffer Overflow Burst** | Scenario A test harness | **500 records** | Measured Value |
| **Overflow Accepted Count** | Scenario A test harness | **0 records (0%)** | Measured Value |
| **Overflow Rejected Count** | Scenario A test harness | **500 records (100%)** | Measured Value |
| **Total Items Consumed & Acknowledged** | Scenario A test harness | **1,100 records** | Measured Value |
| **Configured Retry Attempts** | `settings.INGESTION_RETRY_ATTEMPTS` | **3 retries** | Configured Parameter |
| **Total HTTP Attempts per Exhaustion** | Real urllib3 Retry execution | **4 attempts** ($1 + 3$) | Measured Value |
| **Configured Retry Backoff Factor** | `settings.INGESTION_RETRY_BACKOFF` | **0.3 seconds** | Configured Parameter |
| **Inter-Attempt Backoff Delays** | Measured via `time.perf_counter` | **`[0.000s, 0.601s, 1.201s]`** | Measured Value |
| **Total Exhaustion Elapsed Time** | Measured across 4 attempts | **1.804 to 1.807 seconds** | Measured Value |
| **Recovery Attempt Index** | Test G (Recovery on Attempt 3) | **Attempt 3** | Measured Value |
| **Recovery Elapsed Time** | Test G elapsed duration | **0.6034 seconds** | Measured Value |
| **Worker Processing Throughput** | Phase 8.4.2 Benchmark B | **$31,765.25\ \text{rec/s}$** | Measured Value (Mocked CPU Only) |
| **Live HBase Write Throughput** | Phase 8.4.2 Benchmark C | **UNBENCHMARKED / OFFLINE** | Measured Value (Offline Status) |

---

## 6. Comprehensive Reliability Assessment

### 6.1 What the System Handles Reliably:
1. **Producer Protection Under High Load:** Bounded non-blocking queues prevent buffer overflows from degrading upstream simulator threads.
2. **Worker Daemon Exception Isolation:** Consumer loops do not terminate on malformed payloads, corrupted keys, or database timeouts.
3. **Transient Network Blip Resilience:** The HTTP retry layer successfully handles brief gateway hiccups (up to 3 retries over 1.8 seconds).
4. **Automatic Service Resumption:** Ingestion resumes immediately upon database restoration without manual operator intervention.
5. **API Stateless Stability:** The Flask API remains operational and serves healthy routes even when backend queries fail.

### 6.2 What the System Handles Partially:
1. **Anomaly & Boundary Detection:** High and low temperature violations ($70^\circ\text{C}$, $-20^\circ\text{C}$, $\pm\infty$) generate alerts, but IEEE 754 `NaN` values bypass detection entirely.
2. **Station Identifier Validation:** Station IDs are validated at the REST API boundary but accepted without validation at the ingestion boundary.
3. **Multi-Table Persistence:** Primary telemetry writes are verified, but secondary status writes are executed without failure verification.

### 6.3 What the System Cannot Currently Guarantee:
1. **Zero Data Loss Across Outages:** In-memory queue buffering means all data generated during persistent database outages is permanently lost.
2. **Cross-Table Consistency:** A failure during secondary table writes leaves HBase in an inconsistent partial state without automated rollback.
3. **Accurate Operational Failure Accounting:** Status table write failures are masked, reporting 100% success when live status has stalled.

### 6.4 Academic Verdict on Production Readiness:
The project demonstrates an **academically robust and resilient prototype architecture**, exhibiting sound decoupled design patterns. However, due to the absence of a Dead-Letter Queue, non-atomic multi-table persistence, and the silent status write masking defect, **the current implementation is not production-ready**.

---

## 7. Recommended Remediation Priorities Matrix

The proposed engineering roadmap outlines prioritized remediation actions for future development phases:

| Priority | Finding ID | Proposed Remediation Summary | Intended Outcome | Target Subsystem |
| :--- | :--- | :--- | :--- | :--- |
| **Critical** | **RF-01** | Inspect `put_row(TABLE_STATION_STATUS)` return value; increment `total_failed` and log error on failure. | Eliminate false success metrics; reflect partial persistence accurately. | `app/services/ingestion_service.py` |
| **Critical** | **RF-02** | Add `not math.isfinite(val)` guard in `_is_reading_unphysical()`. | Prevent corrupted `NaN` values from bypassing anomaly checks and contaminating HBase. | `app/services/anomaly_detector.py` |
| **High** | **RF-07** | Replace `{str(e)}` with sanitized client messages in API 500 error responses. | Prevent disclosure of internal OS error codes, hostnames, and socket details. | `app/routes/api.py` |
| **Medium** | **RF-06** | Enforce `station_id in VALID_STATION_IDS` in `IngestionService._process_single_reading`. | Prevent unmanaged station prefixes from polluting HBase tables. | `app/services/ingestion_service.py` |
| **Medium** | **RF-01 / RF-03** | Introduce explicit `metrics["partial_persistence_count"]` tracking. | Provide runtime visibility into secondary table write failures. | `app/services/ingestion_service.py` |
| **Architectural**| **RF-04** | Implement an on-disk SQLite or JSON-lines spillover queue for persistence failures. | Eliminate permanent data loss during transient database outages. | Ingestion Architecture |
| **Architectural**| **RF-03** | Evaluate consolidated single-table schema or application-level saga compensation. | Eliminate cross-table data inconsistencies. | HBase Schema Architecture |

---

## 8. Academic Limitations & Defensibility Boundary

To uphold strict scientific integrity, the evaluation boundaries and constraints of Phase 8.4.3 must be explicitly stated:

1. **Test-Harness Isolation:** All persistence failure and recovery tests were conducted using fine-grained, in-memory mock transports and isolated queues.
2. **Real Retry Transport Boundary:** HTTP retry evaluations executed the real `urllib3.util.Retry` algorithm, but network responses were generated via mock connection handlers rather than live Apache HBase RegionServers.
3. **Absence of Live Cluster Mutations:** Live HBase failure injections (e.g., killing RegionServer processes, Zookeeper quorum splits, or WAL disk saturation) were strictly prohibited by non-destructive safety protocols.
4. **No Multi-Node Distributed Verification:** Tests evaluated single-process Python execution on Windows AMD64. Distributed queue brokers (Kafka, RabbitMQ) and multi-node RegionServer rebalancing were not evaluated.
5. **Absence of Physical Hardware:** Environmental telemetry was generated via mathematical simulation models rather than physical microclimate sensors.
6. **Epistemic Defensibility:** Mocked worker processing speeds ($31,765\ \text{rec/s}$) reflect pure CPU-bound algorithmic latency and **must never be cited as Apache HBase persistence throughput**.

---

## 9. Verification of Git Status & Data Integrity

- **Tracked Repository Status:** `git status --short` confirms tracked repository files are completely clean:
  ```
  ?? docs/academic_validation/
  ```
- **Git Diff:** `git diff --stat` confirms zero tracked files were modified across `app/`, `config/`, or `tests/`.
- **Git Commit:** Confirmed on `main` at `f6823f6` (*Initial release: Urban Microclimate & Heat-Risk Intelligence System*).
- **HBase Data Integrity:** No live HBase writes, table drops, or schema modifications occurred.
- **Daemons:** Simulator and ingestion worker background daemons remain stopped.

---

## 10. Conclusion

Phase 8.4.3.3 has successfully unified, reconciled, and documented the reliability evaluation of the Urban Microclimate & Heat-Risk Intelligence System. All eight findings are definitively classified, backed by reproducible quantitative evidence, and structured with clear remediation pathways.

**Phase 8.4.3.3 is formally COMPLETED.** No application source code, configuration, or database data have been modified. No subsequent sub-phase has been started.