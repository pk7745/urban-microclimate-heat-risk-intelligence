# Phase 8.4.3.1 — Reliability & Fault-Handling Evaluation Report

**Project:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Document:** `docs/academic_validation/PHASE_8_4_3_1_RELIABILITY_RESULTS.md`  
**Evaluation Date:** November 2026  
**Auditor:** Academic Technical Review Team  
**Evaluation Script:** [`docs/academic_validation/scripts/run_reliability_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_reliability_evaluation.py)  
**Raw Results:** [`docs/academic_validation/scripts/reliability_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/reliability_results.json)  
**Evaluation Status:** **VERIFIED & COMPLETED**

---

## 1. Executive Summary

Phase 8.4.3.1 conducts a rigorous, empirical, and non-destructive reliability evaluation of the Urban Microclimate & Heat-Risk Intelligence System under controlled failure conditions. Prior phases established baseline capabilities (Phase 8.1), academic literature alignment (Phase 8.2–8.3), evaluation methodology (Phase 8.4.1), and safe baseline performance benchmarks (Phase 8.4.2).

The purpose of this phase is not to assume idealized behavior or redesign the system, but to discover and document **what the current implementation actually does** when hardware, communication, schema, or persistence faults occur.

### Key Empirical Findings:
1. **Graceful Queue Saturation Handling:** Ingestion buffer overflow uses non-blocking submission (`queue.put(block=False)`). Saturated records are counted (`dropped_due_to_queue_full`), previously queued records maintain FIFO order and data integrity, and normal ingestion resumes immediately once buffer capacity frees up.
2. **Worker Exception Immunity:** The background worker consumer loop (`_worker_loop`) wraps per-record processing in `try...except Exception...finally: task_done()`. A corrupt or crashing record does not terminate the worker thread; subsequent valid records continue processing without interruption.
3. **Multi-Table Non-Atomicity & Partial Writes:** Apache HBase lacks multi-table ACID transactions. Writes spanning `microclimate:readings`, `microclimate:station_status`, and `microclimate:alerts` are executed as independent sequential HTTP requests. If secondary table writes fail after reading persistence, partial writes occur. Furthermore, failure on `TABLE_STATION_STATUS` is ignored without incrementing failure counters.
4. **Permanent Data Loss on Failure (No DLQ):** The system has no dead-letter queue (DLQ) or store-and-forward retry queue. Any record failing HBase persistence or schema extraction is permanently dropped from memory.
5. **Ingestion Station Whitelist Absence:** While Flask REST API endpoints strictly enforce a station whitelist (`VALID_STATION_IDS = {'ST001'..'ST005'}`), the ingestion worker (`IngestionService`) performs **no station ID validation**, silently persisting readings for arbitrary station identifiers (e.g., `ST999`).
6. **API Exception Leakage:** On unhandled internal errors (HTTP 500), API route handlers concatenate raw Python exception strings (`{str(e)}`), leaking internal network and runtime details (e.g., socket connection failure traces) to API consumers.

---

## 2. System Components Inspected

| Component | File Path | Responsibilities & Failure Handling Mechanism |
| :--- | :--- | :--- |
| **Ingestion Buffer & Worker** | [`app/services/ingestion_service.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py) | Non-blocking queue buffer (`maxsize=1000`); background thread with `try/except/finally: task_done()`; failure metrics counters. |
| **HBase REST Client** | [`app/services/hbase_client.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/hbase_client.py) | Stargate HTTP REST communication; Base64 cell encoding/decoding; `urllib3.util.Retry` (3 retries, backoff 0.3s) for HTTP 500/502/503/504; catches `requests.RequestException` and returns `False` or `None`. |
| **Row Key Builder** | [`app/services/hbase_client.py:25-84`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/hbase_client.py#L25-L84) | Row-key generation (`STATION#YYYYMMDD#REV_TS`); reverse epoch timestamp math (`MAX_REVERSE_EPOCH_MS - ts`). Unvalidated timestamp arithmetic raises `TypeError` or `ValueError`. |
| **Anomaly Detection Engine** | [`app/services/anomaly_detector.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/anomaly_detector.py) | Boundary checks (`_is_reading_unphysical`); threshold evaluations; stateful alert deduplication (`active_alert_states`) with 60s cooldown. |
| **Telemetry & Query Service** | [`app/services/telemetry_service.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/telemetry_service.py) | Multi-date boundary scanning; cluster health checks (`check_health`); station validation; query error propagation. |
| **Flask REST API & Response** | [`app/routes/api.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/routes/api.py), [`app/utils/response.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/utils/response.py) | Blueprint route handlers; query parameter validation; standardized JSON responses (`api_success`, `api_error`); internal exception string formatting. |
| **System Configuration** | [`config/settings.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/config/settings.py) | Network endpoints, table names, station metadata, retry parameters, and physical threshold boundaries. |
| **Existing Failure Tests** | [`tests/test_failure_scenarios.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/tests/test_failure_scenarios.py) | 10 unit test cases evaluating isolated failure modes. |

---

## 3. Reliability Evaluation Matrix

| Scenario | Component | Expected Behaviour | Actual Implementation | Safe Test Method | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A1. Empty Queue** | Ingestion Buffer | Non-blocking read raises or blocks until timeout; no thread termination | `queue.get(timeout=0.5)` raises `queue.Empty`; caught in `_worker_loop` and continues | Isolated `IngestionService` queue inspection | **VERIFIED** |
| **A2. Queue Saturated** | Ingestion Buffer | Drop reading without blocking producer; increment drop counter | `queue.put(r, block=False)` raises `queue.Full`; catches, increments `dropped_due_to_queue_full`, returns `False` | Submit 1,000 items into buffer of capacity 1,000, then burst 500 | **VERIFIED** |
| **A3. Buffer Recovery** | Ingestion Buffer | Once drained, buffer accepts new submissions; FIFO intact | Drained items maintain strict FIFO order; buffer accepts 100 new items up to freed capacity | Drain 200 items, verify FIFO timestamps, submit 100 new items | **VERIFIED** |
| **B1. Missing Required Fields** | Ingestion Worker | Reject reading; increment failure counter; no corrupted HBase write | Accessing `reading["station_id"]` raises `KeyError`; caught by `_worker_loop`, increments `total_failed` | Feed dictionary missing `station_id` or `timestamp_ms` | **VERIFIED** |
| **B2. Unknown Station ID** | Ingestion Worker | Reject or quarantine unknown station; prevent HBase partition poll | Ingestion pipeline has **no station ID validation**; builds row-key `ST999#...` and persists to HBase | Feed `station_id="ST999"` | **VERIFIED (DEFECT)** |
| **B3. Non-Numeric Types** | Ingestion Worker / Anomaly Detector | Detect invalid type; log error; increment failure counter | `_is_reading_unphysical` evaluates `temp < -10.0`, raising `TypeError`; caught by worker loop | Feed `"hot"` or `[55.0]` | **VERIFIED** |
| **B4. NaN Values** | Ingestion Worker / Anomaly Detector | Detect NaN; mark reading invalid; suppress persistence | `nan < -10.0` and `nan > 65.0` are `False`; **bypasses sanity checks**; written as `"nan"` | Feed `temperature_celsius=float('nan')` | **VERIFIED (DEFECT)** |
| **B5. Out-of-Bounds Temp** | Ingestion Worker / Anomaly Detector | Flag as `INVALID_READING`; alert logged; reading quarantined | Flagged as `INVALID_READING` alert, but reading is **still written to HBase** | Feed `70.0°C` and `-20.0°C` | **VERIFIED** |
| **C1. Connection Failure** | HBase Client / Worker | Retry with backoff; on failure log error and update health | `put_row` catches `RequestException`, logs error, returns `False`; worker increments `total_failed`; drops record | Mock `put_row` raising `ConnectionError` | **VERIFIED** |
| **C2. Request Timeout** | HBase Client / Worker | Timeout after configured duration; return failure | `put_row` catches `Timeout`, returns `False`; worker increments `total_failed` | Mock `put_row` raising `requests.exceptions.Timeout` | **VERIFIED** |
| **C3. Partial Multi-Table Write** | Ingestion Worker | Atomic multi-table commit or rollback across tables | Writes are non-atomic; if `TABLE_STATION_STATUS` fails, `TABLE_READINGS` remains written; failure is **silently ignored** | Mock status table returning `False` while readings returns `True` | **VERIFIED (DEFECT)** |
| **D1. Worker Exception Safety** | Background Consumer | Unhandled error does not terminate consumer thread | `_worker_loop` catches `Exception`, increments `total_failed`, calls `task_done()`, continues next item | Submit failing item followed by valid item | **VERIFIED** |
| **E1. Transient Outage Recovery** | Ingestion Pipeline | Ingestion resumes automatically once backend recovers | Worker immediately resumes persisting new records; dropped outage records are not recovered | Inject 5 failures, restore mock, inject 5 successes | **VERIFIED** |
| **F1. API Degraded State** | Flask REST API | Return HTTP 503 with standardized error structure | Health endpoint returns HTTP 503, `SERVICE_UNAVAILABLE`, status `"error"` | Mock `TelemetryService.check_health` | **VERIFIED** |
| **F2. API Exception Leakage** | Flask REST API | Sanitize internal error messages; hide socket traces | Route handlers concatenate `{str(e)}` into user-facing message, **exposing internal errors** | Mock `scan_prefix` raising socket error | **VERIFIED (DEFECT)** |

---

## 4. Empirical Test Results by Scenario

The evaluation was executed via [`run_reliability_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_reliability_evaluation.py) using isolated mocks and non-mutating test queues. Raw results are stored in [`reliability_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/reliability_results.json).

### 4.1 Scenario A: Queue Saturation
- **Buffer Configuration:** `queue.Queue(maxsize=1000)` (matching `settings.INGESTION_QUEUE_MAXSIZE`).
- **Initial State:** Empty queue verified (`empty() == True`, `qsize == 0`).
- **Phase 1 (Fill to Capacity):**
  - Submissions attempted: 1,000
  - Submissions accepted: **1,000 (100%)**
  - Full condition verified: `full() == True`, `qsize == 1000`.
- **Phase 2 (Overflow Saturation Burst):**
  - Submissions attempted: 500
  - Submissions accepted: **0 (0%)**
  - Submissions rejected (`queue.Full`): **500 (100%)**
  - Metric counters: `dropped_due_to_queue_full` = **500**, `total_received` = **1,000**.
  - Queue size maintained: Exactly 1,000 (no corruption or buffer over-allocation).
- **Phase 3 (Partial Drain & FIFO Verification):**
  - Items drained: 200 (queue size became 800).
  - FIFO verification: First item drained had $t_0 = 1794940000000$; 200th item had $t_{199} = 1794940000199$. **Strict FIFO ordering preserved**.
  - Refill submissions into freed space: 100 attempted, **100 accepted (100%)**, 0 rejected. Queue size: 900.
- **Phase 4 (Final Drain & Task Accounting):**
  - Remaining items drained: 900. Total consumed: **1,100**.
  - Final queue state: `empty() == True`, `qsize == 0`.
  - Task accounting: `task_done()` called on all 1,100 consumed items; `queue.join()` completed with zero deadlock.
- **Classification:** **VERIFIED**.

---

### 4.2 Scenario B: Invalid and Malformed Telemetry

Twelve distinct invalid, malformed, or boundary-violating inputs were evaluated against `AnomalyDetector` and `IngestionService._process_single_reading`:

| Test ID | Input Anomaly Description | Anomaly Detector Outcome | Ingestion Worker Outcome | HBase Persistence Tables | Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **B01** | Missing `station_id` | No exception | `KeyError: 'station_id'` raised & caught | None (0 tables) | **REJECTED_BY_EXCEPTION** |
| **B02** | Missing `timestamp_ms` | No exception | `KeyError: 'timestamp_ms'` raised & caught | None (0 tables) | **REJECTED_BY_EXCEPTION** |
| **B03** | Missing non-critical fields (`humidity`, `pm25`) | No exception | Missing values cast to `None` / empty string | `readings`, `station_status` | **PERSISTED_SILENTLY** |
| **B04** | Unknown station identifier (`ST999`) | No exception | Accepted without validation against whitelist | `readings`, `station_status` | **PERSISTED_SILENTLY (DEFECT)** |
| **B05** | Non-numeric temperature string (`"hot"`) | `TypeError: '<' not supported` | `TypeError` caught in worker loop | None (0 tables) | **REJECTED_BY_EXCEPTION** |
| **B06** | Non-numeric humidity list (`[55.0]`) | `TypeError: '<' not supported` | `TypeError` caught in worker loop | None (0 tables) | **REJECTED_BY_EXCEPTION** |
| **B07** | NaN temperature (`float('nan')`) | Unphysical check bypassed (all comparisons `False`) | Persisted as string `"nan"` to HBase | `readings`, `station_status` | **PERSISTED_SILENTLY (DEFECT)** |
| **B08** | Positive Infinity (`float('inf')`) | Generates `INVALID_READING` alert | Persisted to HBase alongside alert | `readings`, `station_status`, `alerts` | **ALERTED_AND_PERSISTED** |
| **B09** | Date string timestamp (`"2026-11-18"`) | No exception | `TypeError: unsupported operand /` | None (0 tables) | **REJECTED_BY_EXCEPTION** |
| **B10** | Negative out-of-range timestamp (`-10^15`) | No exception | `OSError: Invalid argument` in `fromtimestamp` | None (0 tables) | **REJECTED_BY_EXCEPTION** |
| **B11** | High unphysical temperature ($70.0^\circ\text{C}$) | Generates `INVALID_READING` alert | Persisted to HBase alongside alert | `readings`, `station_status`, `alerts` | **ALERTED_AND_PERSISTED** |
| **B12** | Low unphysical temperature ($-20.0^\circ\text{C}$) | Generates `INVALID_READING` alert | Persisted to HBase alongside alert | `readings`, `station_status`, `alerts` | **ALERTED_AND_PERSISTED** |

#### Notable Defect Details:
1. **Station Whitelist Absence (B04):** While `VALID_STATION_IDS` is enforced at the API layer, `IngestionService` accepts any station string. A rogue device emitting `ST999` creates HBase rows `ST999#YYYYMMDD#...` and updates `microclimate:station_status` without restriction.
2. **NaN Value Bypass (B07):** In Python, IEEE 754 `NaN` comparisons (`nan < -10.0`, `nan > 65.0`, `nan >= 35.0`) all evaluate to `False`. As a result, `_is_reading_unphysical()` returns `False`, and `AnomalyDetector` generates no alerts. The `NaN` value is encoded as string `"nan"` and committed to the database.
3. **Unphysical Readings Persisted (B08, B11, B12):** When a reading is determined to be unphysical (e.g., $70.0^\circ\text{C}$), the system emits an alert but **does not discard or quarantine the data**. The corrupted metric is written directly into `microclimate:readings` and updates `microclimate:station_status`.

---

### 4.3 Scenario C: Persistence Failure & Multi-Table Semantics

Six controlled failure modes were injected into `HBaseClient.put_row()`:

| Test ID | Persistence Failure Mode | Unhandled Exception | Tables Attempted | Ingested / Failed Delta | Partial Multi-Table Write? | Record Disposition |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **C1** | Connection Refused on `TABLE_READINGS` | `ConnectionError` (caught by `put_row`) | `microclimate:readings` | `+0 / +1` | No (0 persisted) | **Dropped permanently** |
| **C2** | Generic `RuntimeError` on `TABLE_READINGS` | `RuntimeError` (caught by `_worker_loop`) | `microclimate:readings` | `+0 / +1` | No (0 persisted) | **Dropped permanently** |
| **C3** | Socket Read Timeout on `TABLE_READINGS` | `Timeout` (caught by `put_row`) | `microclimate:readings` | `+0 / +1` | No (0 persisted) | **Dropped permanently** |
| **C4** | Gateway returns HTTP 500 on `TABLE_READINGS` | None (`put_row` returns `False`) | `microclimate:readings` | `+0 / +1` | No (0 persisted) | **Dropped permanently** |
| **C5** | Failure on `TABLE_STATION_STATUS` (Readings OK) | None | `readings`, `station_status`, `alerts` | **`+1 / +0` (Defect)** | **YES (Readings written, Status lost)** | **Dropped permanently** |
| **C6** | Failure on `TABLE_ALERTS` (Readings & Status OK) | None | `readings`, `station_status`, `alerts` | `+1 / +0` (Alerts: 0) | **YES (Readings & Status written, Alert lost)** | **Dropped permanently** |

#### Key Architectural Findings:
1. **Absence of Multi-Table Atomicity:** In HBase, atomic mutations exist only within a single row mutation batch on a single table. The three-step sequence (`put_row(TABLE_READINGS)`, `put_row(TABLE_STATION_STATUS)`, `put_row(TABLE_ALERTS)`) has no two-phase commit or rollback mechanism. If step 2 or step 3 fails, preceding writes remain in HBase indefinitely.
2. **Status Failure Metric Masking:** In `IngestionService._process_single_reading`:
   ```python
   # Line 140:
   success = self.hbase.put_row(settings.TABLE_READINGS, reading_key, reading_cols)
   if not success:
       with self._lock:
           self.metrics["total_failed"] += 1
       return

   with self._lock:
       self.metrics["total_ingested"] += 1

   # Line 164:
   self.hbase.put_row(settings.TABLE_STATION_STATUS, status_key, status_cols)
   ```
   The return value of `put_row` on `TABLE_STATION_STATUS` is **completely ignored**. Even if the status write fails, `metrics["total_ingested"]` was already incremented, and `metrics["total_failed"]` is **not incremented**.
3. **No Dead-Letter Queue (DLQ):** Failed records are simply logged via `logger.error` and dropped. There is no offline buffer, retry queue, or replay log.

---

### 4.4 Scenario D: Worker Exception Handling & Continuation
- **Sub-test D1 (Single Failing Record Followed by Valid Record):**
  - Record 1 submitted: Missing `station_id` (causes `KeyError`).
  - Record 2 submitted: Valid telemetry payload.
  - Results: Record 1 raised `KeyError: 'station_id'`, caught in `_worker_loop`, incremented `total_failed` by 1. Record 2 immediately processed successfully, incrementing `total_ingested` by 1.
  - Consumer thread state: **Remained alive and healthy**.
- **Sub-test D2 (10 Records with Middle Failure):**
  - 10 records queued; Record #5 (index 4) corrupted.
  - Successfully processed: **9 records**.
  - Failed: **1 record**.
  - Final queue state: `empty() == True`. All 10 tasks acknowledged via `task_done()`.
- **Classification:** **VERIFIED**. The consumer loop design provides robust isolation against single-record crashes.

---

### 4.5 Scenario E: Transient Failure Recovery Behavior
- **Phase 1 (Simulated Gateway Outage):** Mock configured to return `False`. 5 records submitted; all 5 failed (`total_failed = 5`, `total_ingested = 0`).
- **Phase 2 (Gateway Restoration):** Mock restored to healthy operation (`return True`). 5 new records submitted.
- **Results:**
  - All 5 new records processed successfully (`total_ingested` increased from 0 to 5).
  - `last_ingest_timestamp` advanced to the timestamp of the recovered ingestion.
  - **Recovery Mechanism:** **Automatic in-flight resumption**. The worker requires no operator restart or manual intervention to resume ingestion once backend connectivity is restored.
  - **Data Disposition:** The 5 records submitted during Phase 1 were permanently dropped and **not replayed**.
- **Classification:** **VERIFIED**.

---

### 4.6 Scenario F: Flask API Degraded-State Behavior
Evaluated using the Flask test client (`create_app({"TESTING": True}).test_client()`):

1. **F1 (Health Endpoint during HBase Downtime):**
   - Simulated state: `TelemetryService.check_health` returns `({"app_status": "DEGRADED", "hbase_connected": False, ...}, 503)`.
   - Response: **HTTP 503 Service Unavailable**.
   - JSON structure: Standardized error envelope (`status: "error"`, `error.code: "SERVICE_UNAVAILABLE"`).
2. **F2 (Telemetry Endpoint on Socket Connection Failure):**
   - Simulated state: `HBaseClient.scan_prefix` raises `requests.exceptions.ConnectionError("Failed to establish a new connection: [WinError 10061] No connection could be made")`.
   - Response: **HTTP 500 Internal Server Error**, `error.code: "INTERNAL_ERROR"`.
   - **Exception Leakage Confirmed:** The response message was:
     `"Failed to fetch latest telemetry: Failed to establish a new connection: [WinError 10061] No connection could be made"`
     The raw Windows socket error message was directly exposed to the HTTP client.
3. **F3 (Unknown Station Lookup):**
   - Request: `GET /api/v1/stations/ST999`
   - Response: **HTTP 404 Not Found**, `error.code: "STATION_NOT_FOUND"`.
4. **F4 (Malformed Parameters):**
   - Request: `GET /api/v1/telemetry/latest?limit=-1` $\rightarrow$ **HTTP 400 Bad Request**, `error.code: "INVALID_LIMIT"`.
   - Request: `GET /api/v1/telemetry/ST001?order=diagonal` $\rightarrow$ **HTTP 400 Bad Request**, `error.code: "INVALID_ORDER"`.
5. **F5 (API Continuous Operation):**
   - Immediately following HTTP 500 socket errors, `GET /` responded with **HTTP 200 OK**. The WSGI application maintained 100% operational stability.
- **Classification:** **VERIFIED**.

---

## 5. Failure and Recovery Analysis

```
+----------------------------------------------------------------------------------------------------+
|                                RELIABILITY ARCHITECTURE FLOW & GAPS                                |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  PRODUCER (Simulator)                                                                              |
|      |                                                                                             |
|      v                                                                                             |
|  submit_reading() -------- [ Queue Full? ] --- YES ---> Drop reading & increment drop counter (OK) |
|      |                                                                                             |
|     NO                                                                                             |
|      v                                                                                             |
|  queue.Queue(1000) (In-memory FIFO, sub-microsecond put, non-blocking protection)                  |
|      |                                                                                             |
|      v                                                                                             |
|  _worker_loop() (Single daemon thread; try/except/finally: task_done prevents daemon crash)        |
|      |                                                                                             |
|      v                                                                                             |
|  _process_single_reading()                                                                         |
|      |                                                                                             |
|      +---> Step 1: Anomaly Detection                                                               |
|      |             * GAP: NaN comparisons evaluate False, bypassing sanity checks.                 |
|      |             * GAP: Out-of-bounds readings generate alerts but are NOT discarded.            |
|      |             * GAP: Unknown stations (e.g. ST999) are NOT validated or blocked.              |
|      |                                                                                             |
|      +---> Step 2: Write microclimate:readings                                                     |
|      |             * Fails? -> Drop reading, increment total_failed, return (OK)                   |
|      |             * GAP: No retry queue or dead-letter queue (data permanently lost).             |
|      |                                                                                             |
|      +---> Step 3: Write microclimate:station_status                                               |
|      |             * GAP: Non-atomic write. If Step 3 fails, Step 2 remains in HBase!              |
|      |             * GAP: Return value ignored! total_failed is NOT incremented!                   |
|      |                                                                                             |
|      +---> Step 4: Write microclimate:alerts (if alerts detected)                                  |
|                    * GAP: Non-atomic write. If Step 4 fails, readings & status remain.             |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 6. Identified Reliability Weaknesses

### Weakness 1: Silent Masking of Station-Status Persistence Failures
- **Location:** [`app/services/ingestion_service.py` line 164](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L164)
- **Mechanism:** `self.hbase.put_row(settings.TABLE_STATION_STATUS, status_key, status_cols)` is called without inspecting its boolean return value.
- **Consequence:** If the station-status write fails, the failure is neither logged nor counted in `metrics["total_failed"]`, and `metrics["total_ingested"]` reflects a false success. The live station status becomes stale while readings advance.

### Weakness 2: Non-Atomic Multi-Table Inconsistency
- **Location:** [`app/services/ingestion_service.py` lines 140–193](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L140-L193)
- **Mechanism:** Sequential REST PUT calls to `microclimate:readings`, `microclimate:station_status`, and `microclimate:alerts`.
- **Consequence:** In the event of a partial network failure or timeout during multi-table writes, readings exist in HBase without corresponding station-status or alert entries. No compensatory rollback exists.

### Weakness 3: Total Data Loss on Persistence Failure (Absence of DLQ)
- **Location:** [`app/services/ingestion_service.py` lines 141–145](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L141-L145)
- **Mechanism:** When `put_row` fails or raises an exception, the worker increments `total_failed` and immediately exits `_process_single_reading`.
- **Consequence:** Any record encountering a transient database glitch is permanently discarded. There is no disk-backed spillover buffer, dead-letter queue, or retry scheduler.

### Weakness 4: Absence of Ingestion Station ID Validation
- **Location:** [`app/services/ingestion_service.py` line 118](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L118)
- **Mechanism:** `station_id = reading["station_id"]` is used directly without checking `station_id in VALID_STATION_IDS`.
- **Consequence:** Unlike the REST API (which validates `VALID_STATION_IDS`), the ingestion engine accepts telemetry from arbitrary or spoofed station IDs, polluting HBase tables with unmanaged prefixes.

### Weakness 5: IEEE 754 NaN Sanity Check Bypass
- **Location:** [`app/services/anomaly_detector.py` lines 195–210](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/anomaly_detector.py#L195-L210)
- **Mechanism:** Python evaluates `float('nan') < -10.0` as `False` and `float('nan') > 65.0` as `False`.
- **Consequence:** `_is_reading_unphysical()` fails to detect `NaN` values, allowing them to pass silently into HBase as string `"nan"` without triggering `INVALID_READING` alerts.

### Weakness 6: Internal Exception Exposure in API Error Responses
- **Location:** [`app/routes/api.py` lines 80, 106, 145, 203, 252](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/routes/api.py#L80)
- **Mechanism:** Unhandled exceptions format messages as `f"Failed to ...: {str(e)}"`.
- **Consequence:** Internal environment and socket details (such as `[WinError 10061] No connection could be made`) are returned in client HTTP responses, violating security best practices for information disclosure.

---

## 7. Evidence Limitations

1. **In-Memory Mock Boundary:** The persistence failure tests (Scenario C) used fine-grained mock objects simulating HTTP status codes and socket exceptions. They do not simulate HBase RegionServer WAL flushes, MemStore splits, or Zookeeper quorum partition events.
2. **Single-Node Queue Scope:** Buffer saturation benchmarks and reliability evaluations reflect a single Python process on Windows AMD64. Distributed queue brokers (e.g., Apache Kafka or RabbitMQ) were not evaluated.
3. **Synthetic Failure Injections:** Faults were injected synchronously during single-threaded execution rather than under continuous high-concurrency production load.

---

## 8. Overall Reliability Assessment

| Dimension | Rating | Academic Assessment |
| :--- | :--- | :--- |
| **Buffer Management** | **HIGH** | Non-blocking queue insertion protects streaming producers; drop metrics are tracked; FIFO integrity is strictly preserved. |
| **Worker Fault Tolerance** | **HIGH** | Unhandled record exceptions are safely caught; daemon thread survives continuous failures; automatic recovery on backend restoration. |
| **Data Durability & Retries** | **LOW** | No dead-letter queue (DLQ) or retry buffer; failed records are permanently lost; transient outages cause complete data loss during the outage window. |
| **Multi-Table Consistency** | **LOW** | Sequential non-atomic HBase writes across 3 tables; partial writes occur; station-status write failures are silently ignored. |
| **Input Validation** | **MEDIUM** | Type errors and missing keys are caught via exceptions; boundary envelopes trigger alerts; however, NaN values bypass checks and station IDs are unvalidated at ingestion. |
| **API Error Handling** | **MEDIUM** | Standardized JSON envelopes used consistently; HTTP status codes (400, 404, 503) correct; internal exception strings leaked on 500 errors. |

---

## 9. Recommendations for Future Improvements (Phase 9+ Engineering Roadmap)

1. **Dead-Letter Queue (DLQ) Implementation:** Implement an on-disk SQLite or JSON-lines spillover queue to capture records that fail `put_row`, with a background retry task.
2. **Status Write Verification:** Inspect the return value of `put_row(TABLE_STATION_STATUS)` in `_process_single_reading`, and increment `metrics["total_failed"]` or log a warning when it fails.
3. **Explicit NaN & Inf Guards:** Add `math.isnan(temp)` and `math.isinf(temp)` checks to `AnomalyDetector._is_reading_unphysical()`.
4. **Ingestion Station Whitelist:** Enforce `reading["station_id"] in VALID_STATION_IDS` at the ingestion boundary before proceeding to anomaly detection or row-key construction.
5. **API Exception Sanitization:** Replace `{str(e)}` in API error messages with sanitized messages (e.g., `"An internal error occurred while communicating with the database"`) while logging the full traceback internally.

---

## 10. Conclusion

Phase 8.4.3.1 has successfully executed a comprehensive, empirical reliability and fault-handling evaluation across scenarios A through F without mutating application source code, configuration, or HBase tables. All observed behaviors, defects, and recovery characteristics are backed by reproducible test evidence and stored in structured JSON.

**Phase 8.4.3.1 is formally COMPLETED.** No application source code or Git history has been modified.