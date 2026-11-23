# Phase 8.4.3.2 — Reliability Finding Verification & Retry Semantics Report

**Project:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Document:** `docs/academic_validation/PHASE_8_4_3_2_RELIABILITY_FINDING_VERIFICATION.md`  
**Evaluation Date:** November 2026  
**Auditor:** Academic Technical Review Team  
**Verification Script:** [`docs/academic_validation/scripts/run_reliability_verification.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_reliability_verification.py)  
**Raw Results:** [`docs/academic_validation/scripts/reliability_verification_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/reliability_verification_results.json)  
**Verification Status:** **COMPLETED & VERIFIED**

---

## 1. Executive Summary

Phase 8.4.3.2 performs an independent, empirical verification of the reliability findings and fault-handling characteristics identified during Phase 8.4.3.1. The objective is to rigorously distinguish:
1. **Confirmed Implementation Defects:** Software bugs where the code contradicts its intended logic or produces silent corruption/masking.
2. **Intentional Design Decisions:** Deliberate engineering choices aligned with biometeorological monitoring and raw data preservation requirements.
3. **Architectural & Design Limitations:** Constraints arising from external system capabilities (e.g., Apache HBase's lack of multi-table ACID transactions) or prototype scope boundaries (e.g., in-memory vs. persistent queues).
4. **Validation Gaps & Security Risks:** Missing sanity boundaries or informational leakage that present operational risks.

### Primary Verified Determinations:
* **HBase HTTP Retry Mechanism Verified:** The real `urllib3.util.Retry` layer configured in `HBaseClient._create_session()` was proven to execute real retries for HTTP 500, 502, 503, 504 and connection errors up to **4 total attempts** (1 initial + 3 retries) with exponential backoff ($0.0\text{s}, 0.6\text{s}, 1.2\text{s}$, total $\approx 1.8\text{s}$), successfully recovering when backend health returns before exhaustion.
* **Confirmed Defect 1 (Status Write Failure Masking):** In `IngestionService._process_single_reading`, line 164 discards the return value of `put_row(TABLE_STATION_STATUS)`. If status persistence fails, `metrics["total_failed"]` is not incremented, and `metrics["total_ingested"]` increments, misreporting complete success while leaving HBase in an inconsistent partial state.
* **Confirmed Defect 2 (IEEE 754 NaN Sanity Check Bypass):** Python relational comparisons against `float('nan')` (`nan < -10.0`, `nan > 65.0`) all evaluate to `False`. As a result, `_is_reading_unphysical()` returns `False`, `AnomalyDetector` emits no alerts, `assess_heat_index()` calculates `NaN` marked as `status: "VALID"`, and `"nan"` is persisted to HBase.
* **Intentional Behaviour (Flagged Raw Data Preservation):** Readings exceeding physical thresholds ($70.0^\circ\text{C}$ or $\pm\infty$) trigger `INVALID_READING` alerts but are intentionally persisted into `microclimate:readings`. This reflects a standard meteorological archiving principle: preserving raw transducer outputs alongside anomaly tags rather than silently dropping data.
* **Design Limitation (Multi-Table Non-Atomicity & In-Memory Queue):** HBase REST does not provide distributed transactions across tables; the absence of a Dead-Letter Queue (DLQ) in an in-memory prototype queue is a scope boundary rather than an implementation bug.
* **Validation Gaps Identified:** Ingestion accepts unvalidated station IDs (e.g., `ST999`) despite strict API-level enforcement; API 500 responses leak internal Python exception strings (`{str(e)}`) including Windows socket error codes.

---

## 2. Verification of HBase HTTP Retry Mechanism

### 2.1 Configuration Inspection
In [`app/services/hbase_client.py` lines 95–106](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/hbase_client.py#L95-L106):
```python
def _create_session(self) -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=settings.INGESTION_RETRY_ATTEMPTS,       # 3
        backoff_factor=settings.INGESTION_RETRY_BACKOFF, # 0.3
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
```

### 2.2 Empirical Test Execution
The real retry layer was evaluated by intercepting `urllib3.connectionpool.HTTPConnectionPool._make_request` without mocking `HBaseClient.put_row()`. This allowed the actual `HTTPAdapter` and `Retry` loop to execute.

| Test ID | Failure Mode | Configured Retries | Actual HTTP Attempts | Retried? | Backoff Delays (s) | Elapsed Time (s) | Final Result | Policy Matched? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A** | Connection Refused (`NewConnectionError`) | 3 | **4** | **YES** | `[0.002, 0.601, 1.201]` | 1.807 s | `False` | **VERIFIED** |
| **B** | Read Timeout (`ReadTimeoutError`) | 3 | **4** | **YES** | `[0.001, 0.601, 1.201]` | 1.806 s | `False` | **VERIFIED** |
| **C** | HTTP 500 Internal Server Error | 3 | **4** | **YES** | `[0.000, 0.601, 1.201]` | 1.804 s | `False` | **VERIFIED** |
| **D** | HTTP 502 Bad Gateway | 3 | **4** | **YES** | `[0.002, 0.600, 1.201]` | 1.805 s | `False` | **VERIFIED** |
| **E** | HTTP 503 Service Unavailable | 3 | **4** | **YES** | `[0.000, 0.600, 1.201]` | 1.804 s | `False` | **VERIFIED** |
| **F** | HTTP 504 Gateway Timeout | 3 | **4** | **YES** | `[0.001, 0.601, 1.201]` | 1.805 s | `False` | **VERIFIED** |
| **G** | Recovery on Attempt 3 (500 $\rightarrow$ 500 $\rightarrow$ 200) | 3 | **3** | **YES** | `[0.001, 0.601]` | 0.603 s | **`True`** | **VERIFIED** |
| **H** | Exhaustion after 4 attempts | 3 | **4** | **YES** | `[0.001, 0.601, 1.201]` | 1.807 s | `False` | **VERIFIED** |

### 2.3 Key Retry Findings:
1. **Total Attempts Formula:** With `total=3`, `urllib3` executes $1 + 3 = \mathbf{4\ \text{attempts}}$ before exhausting retries.
2. **Backoff Schedule:** Urllib3's exponential backoff formula: $\text{delay} = \text{backoff\_factor} \times 2^{(\text{retry} - 1)}$.
   - Retry 1: $0.3 \times 2^0 = 0.0\ \text{s}$ (first retry executes immediately).
   - Retry 2: $0.3 \times 2^1 = 0.6\ \text{s}$.
   - Retry 3: $0.3 \times 2^2 = 1.2\ \text{s}$.
   - Total wait: $0.0 + 0.6 + 1.2 = \mathbf{1.8\ \text{s}}$.
3. **In-Flight Recovery (Test G):** When a failing gateway recovers on attempt 3, `put_row()` returns `True`, successfully persisting the record without client error.
4. **Clean Failure Return (Test H):** Because `raise_on_status=False`, exhaustion on status codes returns the HTTP response to `put_row()`, which checks `resp.status_code in (200, 201)` and cleanly returns `False`.

---

## 3. Verification of Multi-Table Persistence Semantics

### 3.1 Code Inspection
In [`app/services/ingestion_service.py` lines 140–193](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L140-L193):
- **Step 1:** Writes to `settings.TABLE_READINGS`. If `not success: self.metrics["total_failed"] += 1; return`.
- **Step 2:** Increments `self.metrics["total_ingested"] += 1`.
- **Step 3:** Writes to `settings.TABLE_STATION_STATUS`: `self.hbase.put_row(settings.TABLE_STATION_STATUS, status_key, status_cols)` (return value is **not captured or checked**).
- **Step 4:** If alerts exist, writes each to `settings.TABLE_ALERTS`. If `not success: logger.error(...)`, but `total_failed` is not incremented.

### 3.2 Controlled Multi-Table Failure Simulations

| Case | Scenario Simulated | Operations Attempted | Operations Succeeded | Operations Failed | $\Delta\text{Ingested}$ | $\Delta\text{Failed}$ | $\Delta\text{Alerts}$ | Partial Write? | Accurately Reflected in Metrics? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Case 1** | All Tables Succeed | `readings`, `status`, `alerts` | `readings`, `status`, `alerts` | None | **+1** | **0** | **+1** | No | **YES** |
| **Case 2** | Readings Fails (Step 1) | `readings` | None | `readings` | **0** | **+1** | **0** | No | **YES** |
| **Case 3** | Status Fails (Step 2) | `readings`, `status`, `alerts` | `readings`, `alerts` | `station_status` | **+1** | **0** | **+1** | **YES** | **NO (CONFIRMED DEFECT)** |
| **Case 4** | Alerts Fails (Step 3) | `readings`, `status`, `alerts` | `readings`, `status` | `alerts` | **+1** | **0** | **0** | **YES** | **NO (CONFIRMED DEFECT)** |
| **Case 5** | Status & Alerts Fail | `readings`, `status`, `alerts` | `readings` | `status`, `alerts` | **+1** | **0** | **0** | **YES** | **NO (CONFIRMED DEFECT)** |

### 3.3 Metric Inaccuracy Determination:
* **The Defect:** In Cases 3, 4, and 5, secondary table writes fail, leaving partial writes in HBase. However, `metrics["total_ingested"]` increments by 1, and `metrics["total_failed"]` remains 0.
* **Consequence:** The ingestion metrics report 100% operational success while live station status becomes stale and critical alerts are lost.

---

## 4. Verification of NaN and Infinity Handling

### 4.1 Comparative Evaluation Against `math.isfinite()`
Evaluated eight inputs across `_is_reading_unphysical()`, `AnomalyDetector.analyze_reading()`, `assess_heat_index()`, and `IngestionService._process_single_reading()`:

| Input Value | `math.isfinite()` Reference | Detected as Unphysical? | Alerts Generated | Heat Index Assessment | Persisted to HBase? | Ingestion Metric Delta | Finding Classification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `float('nan')` | **`False`** | **`False` (Defect)** | **None (Defect)** | `status: "VALID", HI: NaN` | **YES (`"nan"`)** | `+1 / 0` | **CONFIRMED DEFECT** |
| `float('inf')` | **`False`** | `True` | `INVALID_READING` (Critical) | `status: "UNPHYSICAL_TEMPERATURE"` | **YES (`"inf"`)** | `+1 / 0` | **INTENTIONAL BEHAVIOUR** |
| `float('-inf')` | **`False`** | `True` | `INVALID_READING` (Critical) | `status: "UNPHYSICAL_TEMPERATURE"` | **YES (`"-inf"`)** | `+1 / 0` | **INTENTIONAL BEHAVIOUR** |
| `28.5°C` (Normal) | `True` | `False` | None | `status: "VALID", HI: 29.59°C` | **YES (`"28.5"`)** | `+1 / 0` | **NORMAL BEHAVIOUR** |
| `-10.0°C` (Inside Lower) | `True` | `False` | None | `NOT_APPLICABLE_LOW_TEMPERATURE` | **YES (`"-10.0"`)** | `+1 / 0` | **NORMAL BEHAVIOUR** |
| `-10.1°C` (Outside Lower)| `True` | `True` | `INVALID_READING` (Critical) | `NOT_APPLICABLE_LOW_TEMPERATURE` | **YES (`"-10.1"`)** | `+1 / 0` | **INTENTIONAL BEHAVIOUR** |
| `65.0°C` (Inside Upper) | `True` | `False` | `HIGH_TEMPERATURE` (Critical) | `UNSUPPORTED_EXTRAPOLATION` | **YES (`"65.0"`)** | `+1 / 0` | **NORMAL BEHAVIOUR** |
| `65.1°C` (Outside Upper)| `True` | `True` | `INVALID_READING` (Critical) | `UNPHYSICAL_TEMPERATURE` | **YES (`"65.1"`)** | `+1 / 0` | **INTENTIONAL BEHAVIOUR** |

### 4.2 IEEE 754 NaN Defect Analysis:
1. **Root Cause:** In Python (and IEEE 754 floating-point arithmetic), any relational comparison against `NaN` evaluates to `False`:
   ```python
   nan < -10.0  # False
   nan > 65.0   # False
   ```
   Consequently, `_is_reading_unphysical()` returns `False`.
2. **Cascading Failure:** In `assess_heat_index(temp, hum)`:
   - Guard `temp < -50.0 or temp > 65.0` evaluates to `False`.
   - Guard `temp < 20.0` evaluates to `False`.
   - The Rothfusz regression equation executes: polynomial operations on `NaN` return `NaN`.
   - Returns `{"heat_index_celsius": NaN, "status": "VALID", "is_valid": True}`.
3. **Database Contamination:** `IngestionService` serializes `NaN` to Base64 string `"nan"`, committing corrupted non-numeric values to both `microclimate:readings` and `microclimate:station_status`.

---

## 5. Verification of Station Validation

### 5.1 Investigation of Inconsistency
* **Configuration:** Five monitoring stations are defined in `config/settings.py` (`ST001`–`ST005`).
* **API Route Handlers:** [`app/routes/api.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/routes/api.py) strictly validates `station_id in VALID_STATION_IDS`:
  - `GET /api/v1/stations/ST999` $\rightarrow$ **HTTP 404** (`STATION_NOT_FOUND`).
  - `GET /api/v1/telemetry/ST999` $\rightarrow$ **HTTP 404** (`STATION_NOT_FOUND`).
  - `GET /api/v1/alerts?station_id=ST999` $\rightarrow$ **HTTP 400** (`INVALID_PARAMETER`).
* **Ingestion Worker:** [`app/services/ingestion_service.py` line 118](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/app/services/ingestion_service.py#L118) performs **no station validation**:
  - Accepts `station_id = "ST999"`.
  - Builds row key: `ST999#20261117#8205058799999`.
  - Persists reading to `microclimate:readings` and status to `microclimate:station_status`.
  - Increments `total_ingested` by 1.

### 5.2 Classification Determination:
* **Classification:** **VALIDATION GAP** (Architectural Inconsistency).
* **Rationale:** The project requirements for Phase 1–3 specified that 5 stations would be simulated, but did not formally specify that the ingestion worker must reject dynamic or unconfigured station IDs. Therefore, it is classified as a **VALIDATION GAP** rather than a defect violating an explicit contractual specification.

---

## 6. Verification of API Information Disclosure

### 6.1 Exception Injection & Response Analysis
Evaluated client-visible error responses using the Flask test client across three controlled exceptions injected into `HBaseClient.scan_prefix()`:

1. **Connection Refused:**
   - Injected: `requests.exceptions.ConnectionError("Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it")`
   - Client Response: **HTTP 500**, `error.code: "INTERNAL_ERROR"`
   - Client-Visible Message:  
     `"Failed to fetch latest telemetry: Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"`
   - Information Disclosed: **Windows OS socket error code (`10061`), connection state**.
2. **HTTP Timeout:**
   - Injected: `requests.exceptions.Timeout("HTTP connection to http://localhost:8085 timed out after 5.0 seconds")`
   - Client Response: **HTTP 500**, `error.code: "INTERNAL_ERROR"`
   - Client-Visible Message:  
     `"Failed to fetch latest telemetry: HTTP connection to http://localhost:8085 timed out after 5.0 seconds"`
   - Information Disclosed: **Internal backend REST URL (`http://localhost:8085`), internal timeout threshold (5.0s)**.
3. **Internal Server RuntimeError:**
   - Injected: `RuntimeError("HBase RegionServer 10.0.1.42 reported internal MemStore flush deadlock")`
   - Client Response: **HTTP 500**, `error.code: "INTERNAL_ERROR"`
   - Client-Visible Message:  
     `"Failed to fetch latest telemetry: HBase RegionServer 10.0.1.42 reported internal MemStore flush deadlock"`
   - Information Disclosed: **Internal network topology (`10.0.1.42`), RegionServer architecture details**.

### 6.2 Classification:
* **Classification:** **VALIDATION GAP / SECURITY RISK**.
* **Rationale:** The response envelope remains structurally valid (`{"status": "error", "error": {...}}`), but embedding `{str(e)}` exposes internal hostnames, ports, and OS socket codes.

---

## 7. Authoritative Reclassification Matrix

| Finding ID | Finding Title | System Component | Phase 8.4.3.1 Finding | Phase 8.4.3.2 Reclassification | Academic Justification & Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RF-01** | Silent Masking of Station-Status Persistence Failures | `IngestionService._process_single_reading:164` | Defect | **CONFIRMED DEFECT** | Return value of `put_row(TABLE_STATION_STATUS)` is discarded; failures do not increment `total_failed` and misreport complete success. |
| **RF-02** | IEEE 754 NaN Bypasses Unphysical Sanity Checks | `AnomalyDetector._is_reading_unphysical:195` | Defect | **CONFIRMED DEFECT** | Python relational comparisons against `NaN` evaluate to `False`; `NaN` bypasses checks, returns `status: "VALID"`, and persists to HBase. |
| **RF-03** | Multi-Table Sequential Non-Atomicity Across HBase | Architecture / Ingestion Pipeline | Defect | **DESIGN LIMITATION** | Native Apache HBase REST does not support cross-table transactions. Partial writes under network failure are an inherent trade-off of HBase without external transaction coordinators. |
| **RF-04** | Absence of Dead-Letter Queue (DLQ) / Drop-on-Failure | Ingestion Buffer Architecture | Defect | **DESIGN LIMITATION** | The project specification called for an in-memory `queue.Queue`. Dropping on failure during persistent outages is a documented scope boundary of the prototype, not a software bug. |
| **RF-05** | Persistence of Flagged Raw Telemetry (Unphysical / Anomalous) | Ingestion & Anomaly Detection Pipeline | Defect | **INTENTIONAL BEHAVIOUR** | Preserving raw sensor values in `microclimate:readings` while emitting anomaly alerts in `microclimate:alerts` is standard meteorological practice to enable auditability. |
| **RF-06** | Missing Station Whitelist in Ingestion Engine | `IngestionService._process_single_reading:118` | Defect | **VALIDATION GAP** | While API endpoints strictly enforce `VALID_STATION_IDS`, ingestion accepts arbitrary station strings. Because dynamic onboarding was not formally forbidden, it is a validation gap. |
| **RF-07** | Internal Exception String Disclosure on HTTP 500 Responses | Flask API Route Handlers (`api.py`) | Defect | **VALIDATION GAP / SECURITY RISK** | Formatting 500 messages as `f"...: {str(e)}"` discloses internal OS socket codes, hostnames, and ports to external clients. |
| **RF-08** | HBase Client HTTP Session Retry Mechanism | `HBaseClient._create_session:95` | Verified | **INTENTIONAL BEHAVIOUR / VERIFIED DESIGN** | Verified that `urllib3.util.Retry` executes up to 4 attempts across HTTP 500, 502, 503, 504 and connection errors with $1.8\text{s}$ cumulative exponential backoff. |

---

## 8. Git Status & Safety Confirmation

- **Git Status:** `git status --short` confirms tracked repository files are completely clean:
  ```
  ?? docs/academic_validation/
  ```
- **Git Diff:** `git diff --stat` returns empty (0 files changed, 0 insertions, 0 deletions across tracked repository files).
- **Git Commit:** Confirmed on `main` at `f6823f6` (*Initial release: Urban Microclimate & Heat-Risk Intelligence System*).
- **HBase Data & Application Source:** Strictly untouched. No live HBase tables were modified, truncated, or written to. Application source code (`app/`), configuration (`config/`), and unit tests (`tests/`) remain pristine.
- **Daemons:** Simulator and ingestion worker background daemons remain stopped.

---

**Phase 8.4.3.2 is formally COMPLETED.** Execution is stopped in accordance with instructions. No subsequent sub-phase has been started.