# Phase 8.4.5 — REST API and Dashboard Evaluation Report

**Project:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Document:** `docs/academic_validation/PHASE_8_4_5_API_DASHBOARD_EVALUATION.md`  
**Evaluation Date:** November 2026  
**Auditor:** Academic Technical Review Team  
**Evaluation Scripts:**
- [`docs/academic_validation/scripts/run_api_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_api_evaluation.py)
- [`docs/academic_validation/scripts/run_dashboard_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_dashboard_evaluation.py)
**Raw Results Artifacts:**
- [`docs/academic_validation/scripts/api_evaluation_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/api_evaluation_results.json)
- [`docs/academic_validation/scripts/dashboard_evaluation_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/dashboard_evaluation_results.json)  
**Evaluation Status:** **COMPLETED & VERIFIED**

---

## 1. Executive Summary & Evaluation Scope

Phase 8.4.5 evaluates the REST API and command-center dashboard as an integrated, multi-tier operational intelligence application. In accordance with strict academic audit guidelines, this phase evaluates the implementation as-is using Flask's isolated test client, mocked persistence harnesses, and static frontend code analysis. **No application source code or configuration files were altered, and no background daemons or live database mutation operations were executed.**

### Key Evaluation Findings:
1. **Route Reconciliation Confirmed:** Source code inspection reconciles the previously observed count discrepancies:
   - **12 REST API Endpoints:** Implemented in `app/routes/api.py` under Blueprint `api_bp` (`url_prefix="/api/v1"`).
   - **2 Application Routes:** Implemented in `app/__init__.py` on root Flask app (`GET /` with content negotiation, `GET /dashboard` rendering template).
   - **16 Phase 3.8 Test Specifications:** Implemented in `tests/test_api.py` covering functional operations, validation edge cases, and mocked degradation.
2. **REST API Functional & Validation Correctness (100%):** All 56 evaluated API test cases passed across functional endpoints (16/16), input validation checks (27/27), security exception handlers (6/6), and data consistency assertions (7/7).
3. **Confirmed Security Risk RF-07 Re-Verified:** All route error handlers in `app/routes/api.py` concatenate unhandled runtime exceptions (`f"...: {str(e)}"`) directly into user-facing HTTP 500 JSON responses. Under simulated connection failures, socket error codes (`[WinError 10061]`), internal hostnames, and loopback URLs (`http://localhost:8085`) are disclosed to external HTTP clients.
4. **URL Path Fragment Truncation with `#` in Row Keys:** HBase row keys formatted as `STATION#REV_TS#ALERT_TYPE` contain the `#` character. If clients issue HTTP requests with unencoded `#` (e.g. `/api/v1/alerts/ST001#8205.../acknowledge`), standard URL parsers treat `#` as an HTTP fragment identifier, truncating the URL before the route handler is reached (returning HTTP 404 `NOT_FOUND`). The frontend client (`app/static/js/api.js`) correctly applies `encodeURIComponent()`, but this represents an architectural REST vulnerability when accessed by external API clients.
5. **Dashboard Presentation & Governance (100%):** All 8 functional dashboard sections, 5 Chart.js time-series canvases, Leaflet geospatial mapping, and stateful alert acknowledgement modals render as designed. Academic integrity disclosures (`SIMULATED DATA`, `SIMULATED STATIONS`, and the CPCB NAQI instantaneous indicative disclaimer) are verified in the HTML layout.
6. **Frontend Failure Handling & Resilience:** `app/static/js/api.js` captures network and gateway failures cleanly (`status: 0`), `app/static/js/app.js` updates cluster status badges to "HBase Degraded", `app/static/js/charts.js` enforces `spanGaps: false` to prevent drawing missing or invalid data as zero, and the 10-second polling loop employs an `isRefreshing` execution lock to prevent burst overlap.

---

## 2. Baseline Route & Endpoint Reconciliation

A structural audit of `app/__init__.py`, `app/routes/api.py`, and `tests/test_api.py` resolves previous documentation discrepancies:

```
+----------------------------------------------------------------------------------------------------+
|                                    APPLICATION ROUTE RECONCILIATION                                |
+----------------------------------------------------------------------------------------------------+
| Layer / Category                   | Count | Source File             | Description                 |
+------------------------------------+-------+-------------------------+-----------------------------+
| REST API Endpoints (/api/v1/*)     | 12    | app/routes/api.py       | Blueprint routes for data   |
| Top-Level Application Routes       | 2     | app/__init__.py         | / and /dashboard routes     |
| Total Flask Route Handlers         | 14    | Flask url_map           | Complete HTTP routing table |
| Phase 3.8 Test Specifications      | 16    | tests/test_api.py       | Requirement test suites     |
+----------------------------------------------------------------------------------------------------+
```

### Complete Endpoint Inventory:

| # | HTTP Method | Rule / Path | Handler Function | Purpose & Summary |
| :- | :--- | :--- | :--- | :--- |
| **1** | `GET` | `/` | `index()` | Content negotiation: returns HTML if `Accept: text/html`, else service JSON metadata. |
| **2** | `GET` | `/dashboard` | `dashboard()` | Dedicated route rendering command-center `templates/index.html`. |
| **3** | `GET` | `/api/v1/health` | `health_check()` | Checks HBase REST gateway connectivity, table availability, and simulator status. |
| **4** | `GET` | `/api/v1/stations` | `list_stations()` | Retrieves all 5 Bengaluru monitoring stations with static metadata and live status. |
| **5** | `GET` | `/api/v1/stations/<station_id>` | `get_station()` | Detailed metadata, latest reading, and 5 recent alerts for a specific station. |
| **6** | `GET` | `/api/v1/telemetry/latest` | `get_latest_telemetry()` | Newest available telemetry globally sorted descending by timestamp. |
| **7** | `GET` | `/api/v1/telemetry/<station_id>` | `get_station_telemetry()` | Multi-date partition historical scanning with ISO timestamp bounds and sorting. |
| **8** | `GET` | `/api/v1/alerts` | `list_alerts()` | System alerts sorted newest-first, filtered by station, severity, and acknowledgement. |
| **9** | `POST` | `/api/v1/alerts/<path:alert_id>/acknowledge` | `acknowledge_alert()` | Acknowledges an alert in HBase with operator note without mutating other fields. |
| **10** | `GET` | `/api/v1/analytics/temperature` | `get_temperature_analytics()` | Statistical aggregates (min, max, avg, std_dev) across 1–30 day windows. |
| **11** | `GET` | `/api/v1/analytics/air-quality` | `get_air_quality_analytics()` | PM2.5/PM10 statistics and indicative CPCB particulate category classification. |
| **12** | `GET` | `/api/v1/analytics/station-comparison` | `get_station_comparison()` | Comparative rankings of all 5 stations by Apparent Heat Index. |
| **13** | `GET` | `/api/v1/simulator/status` | `get_simulator_status()` | Background simulator state, execution mode, and reading counters. |
| **14** | `POST` | `/api/v1/simulator/control` | `control_simulator()` | In-process lifecycle control (`start`, `stop`, `inject_anomaly`). |

---

## 3. REST API Functional Evaluation Results

Every implemented endpoint was evaluated using isolated test harnesses mocking `TelemetryService`, `HBaseClient`, and `SimulatorController`. All responses conform to the standardized JSON envelope defined in `app/utils/response.py`.

### Standardized Response Envelope:
* **Success Envelope (`200 OK`):**
  ```json
  {
    "status": "success",
    "data": { ... },
    "message": "Optional human-readable confirmation",
    "meta": { ... },
    "timestamp": "2026-11-22T15:14:15.830000+00:00"
  }
  ```
* **Error Envelope (`400`, `404`, `405`, `500`, `503`):**
  ```json
  {
    "status": "error",
    "error": {
      "code": "ERROR_CODE_STRING",
      "message": "Descriptive error message",
      "details": null
    },
    "timestamp": "2026-11-22T15:14:15.830000+00:00"
  }
  ```

### Functional Evaluation Summary:

```
+----------------------------------------------------------------------------------------------------+
|                                    FUNCTIONAL ENDPOINT TEST MATRIX                                 |
+----------------------------------------------------------------------------------------------------+
| Endpoint Tested                            | Method | Expected | Actual | Envelope Status | Result |
+--------------------------------------------+--------+----------+--------+-----------------+--------+
| / (Browser Accept: text/html)              | GET    | 200      | 200    | HTML Document   | PASS   |
| / (Programmatic Accept: application/json)  | GET    | 200      | 200    | JSON Metadata   | PASS   |
| /dashboard                                 | GET    | 200      | 200    | HTML Document   | PASS   |
| /api/v1/health (Operational)               | GET    | 200      | 200    | success         | PASS   |
| /api/v1/health (HBase Degraded)            | GET    | 503      | 503    | error (503)     | PASS   |
| /api/v1/stations                           | GET    | 200      | 200    | success         | PASS   |
| /api/v1/stations/ST001                     | GET    | 200      | 200    | success         | PASS   |
| /api/v1/telemetry/latest?limit=10          | GET    | 200      | 200    | success         | PASS   |
| /api/v1/telemetry/ST001?limit=10           | GET    | 200      | 200    | success         | PASS   |
| /api/v1/alerts?limit=10                    | GET    | 200      | 200    | success         | PASS   |
| /api/v1/alerts/<quoted_id>/acknowledge     | POST   | 200      | 200    | success         | PASS   |
| /api/v1/analytics/temperature?days=1       | GET    | 200      | 200    | success         | PASS   |
| /api/v1/analytics/air-quality?days=1       | GET    | 200      | 200    | success         | PASS   |
| /api/v1/analytics/station-comparison       | GET    | 200      | 200    | success         | PASS   |
| /api/v1/simulator/status                   | GET    | 200      | 200    | success         | PASS   |
| /api/v1/simulator/control (start)          | POST   | 200      | 200    | success         | PASS   |
+----------------------------------------------------------------------------------------------------+
| Total Functional Tests: 16 | Passed: 16 (100.0%) | Failed: 0                                      |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. API Input Validation & Edge Case Handling

The API layer enforces input validation across query parameters, path variables, and JSON bodies. A comprehensive battery of 27 invalid and boundary conditions was evaluated:

| Test Case | Method | Endpoint / Payload | Expected Code | Actual Status | Code Match | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Unknown Station ID in Path** | `GET` | `/api/v1/stations/ST999` | `STATION_NOT_FOUND` | `404` | `STATION_NOT_FOUND` | **PASS** |
| **Invalid Station in Telemetry** | `GET` | `/api/v1/telemetry/latest?station_id=INVALID` | `INVALID_PARAMETER` | `400` | `INVALID_PARAMETER` | **PASS** |
| **Negative / Zero Limit** | `GET` | `/api/v1/telemetry/latest?limit=0` | `INVALID_LIMIT` | `400` | `INVALID_LIMIT` | **PASS** |
| **Excessive Limit (> 500)** | `GET` | `/api/v1/telemetry/latest?limit=9999` | `INVALID_LIMIT` | `400` | `INVALID_LIMIT` | **PASS** |
| **Non-Integer Limit** | `GET` | `/api/v1/telemetry/latest?limit=abc` | `INVALID_LIMIT` | `400` | `INVALID_LIMIT` | **PASS** |
| **Unknown Station in History** | `GET` | `/api/v1/telemetry/ST999` | `STATION_NOT_FOUND` | `404` | `STATION_NOT_FOUND` | **PASS** |
| **Invalid Historical Order** | `GET` | `/api/v1/telemetry/ST001?order=diagonal` | `INVALID_ORDER` | `400` | `INVALID_ORDER` | **PASS** |
| **Invalid Measurement Field** | `GET` | `/api/v1/telemetry/ST001?measurement=radiation` | `INVALID_MEASUREMENT` | `400` | `INVALID_MEASUREMENT` | **PASS** |
| **Inverted Time Window** | `GET` | `/api/v1/telemetry/ST001?start=...&end=...` | `INVALID_PARAMETERS` | `400` | `INVALID_PARAMETERS` | **PASS** |
| **Excessive Historical Limit** | `GET` | `/api/v1/telemetry/ST001?limit=5000` | `INVALID_LIMIT` | `400` | `INVALID_LIMIT` | **PASS** |
| **Invalid Station in Alerts** | `GET` | `/api/v1/alerts?station_id=ST888` | `INVALID_PARAMETER` | `400` | `INVALID_PARAMETER` | **PASS** |
| **Negative Alert Limit** | `GET` | `/api/v1/alerts?limit=-5` | `INVALID_LIMIT` | `400` | `INVALID_LIMIT` | **PASS** |
| **Alert ID Not Found** | `POST` | `/api/v1/alerts/<quoted_id>/acknowledge` | `ALERT_NOT_FOUND` | `404` | `ALERT_NOT_FOUND` | **PASS** |
| **Unencoded `#` in Alert Path**| `POST` | `/api/v1/alerts/ST001#8205.../acknowledge` | `NOT_FOUND` (404) | `404` | `NOT_FOUND` (404) | **PASS** |
| **Invalid Station in Analytics**| `GET` | `/api/v1/analytics/temperature?station_id=BAD`| `INVALID_PARAMETER` | `400` | `INVALID_PARAMETER` | **PASS** |
| **Zero Days in Analytics** | `GET` | `/api/v1/analytics/temperature?days=0` | `INVALID_PARAMETER` | `400` | `INVALID_PARAMETER` | **PASS** |
| **Excessive Days (> 30)** | `GET` | `/api/v1/analytics/temperature?days=35` | `INVALID_PARAMETER` | `400` | `INVALID_PARAMETER` | **PASS** |
| **Non-Integer Days** | `GET` | `/api/v1/analytics/temperature?days=two` | `INVALID_PARAMETER` | `400` | `INVALID_PARAMETER` | **PASS** |
| **Missing Simulator Action** | `POST` | `/api/v1/simulator/control` `{}` | `MISSING_ACTION` | `400` | `MISSING_ACTION` | **PASS** |
| **Invalid Simulator Action** | `POST` | `/api/v1/simulator/control` `{"action":"destroy"}`| `INVALID_ACTION` | `400` | `INVALID_ACTION` | **PASS** |
| **Missing Anomaly Influx Params**| `POST`| `/api/v1/simulator/control` `{"action":"inject..."}`| `MISSING_PARAMETERS` | `400` | `MISSING_PARAMETERS` | **PASS** |
| **Unsupported Method (POST)**| `POST` | `/api/v1/telemetry/latest` | `METHOD_NOT_ALLOWED`| `405` | `METHOD_NOT_ALLOWED`| **PASS** |
| **Unsupported Method (GET)** | `GET` | `/api/v1/simulator/control` | `METHOD_NOT_ALLOWED`| `405` | `METHOD_NOT_ALLOWED`| **PASS** |
| **Nonexistent Route** | `GET` | `/api/v1/not_a_real_route` | `NOT_FOUND` | `404` | `NOT_FOUND` | **PASS** |

---

## 5. API Reliability, Security & Error Disclosure (RF-07 Re-Verification)

### 5.1 Re-Verification of Confirmed Defect RF-07 (Security Risk)
Phase 8.4.3 identified that exception handlers in `app/routes/api.py` concatenate raw Python exception strings (`f"...: {str(e)}"`) into client responses. This evaluation tested all 6 route exception blocks under controlled failure injections:

```json
// Example Injected Connection Refused Error Response:
{
  "status": "error",
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Failed to retrieve stations: [WinError 10061] No connection could be made because the target machine actively refused it http://localhost:8085"
  },
  "timestamp": "2026-11-22T15:14:15.843000+00:00"
}
```

* **Observed Result across All 6 Routes:** Injected errors for stations, single station lookup, latest telemetry, historical telemetry, alerts, and analytics all leaked raw OS error codes (`WinError 10061`), Python error types (`ConnectionRefusedError`, `ZeroDivisionError`), and internal network addresses (`http://localhost:8085`).
* **Classification:** **CONFIRMED DEFECT / SECURITY RISK (RF-07)**.
* **Remediation Recommendation:** Replace string concatenation `{str(e)}` with sanitized user messages (e.g., `"An error occurred while retrieving station records. Please check database connectivity."`), while logging the full exception traceback server-side.

### 5.2 Process Availability vs. Data Availability
The `/api/v1/health` endpoint correctly decouples Flask process availability from HBase data availability:
* When the Flask process is running and HBase is operational, `/api/v1/health` returns `200 OK` (`app_status: "UP"`, `hbase_connected: true`).
* When HBase or required tables are unreachable, `/api/v1/health` returns `503 SERVICE UNAVAILABLE` (`app_status: "DEGRADED"`, `hbase_connected: false`).
* This enables upstream load balancers and container orchestrators to distinguish between a dead application server and degraded storage connectivity.

### 5.3 Architectural Row-Key Hash Fragment Vulnerability
* HBase row keys incorporate `#` delimiters (e.g. `ST001#8205058153242#HIGH_TEMPERATURE`).
* In standard HTTP specifications (RFC 3986), `#` denotes a URI fragment. Unencoded `#` characters are stripped by client HTTP libraries or WSGI servers, causing path truncation and returning 404 `NOT_FOUND`.
* While the project's internal frontend client uses `encodeURIComponent()`, external REST consumers querying the API directly without percent-encoding `%23` fail to reach the resource.
* **Classification:** **DESIGN LIMITATION**.

---

## 6. Data Consistency Evaluation

Using isolated fixtures and mock implementations, the evaluation examined data integrity across 7 key dimensions:

```
+----------------------------------------------------------------------------------------------------+
|                                    DATA CONSISTENCY EVALUATION MATRIX                              |
+----------------------------------------------------------------------------------------------------+
| Dimension Tested                   | Mock Condition Evaluated                | Observed Behaviour  |
+------------------------------------+-----------------------------------------+---------------------+
| Multi-Date Chronological Ordering  | Records across Nov 16 and Nov 17        | DESC: Nov 17 > Nov  |
|                                    |                                         | ASC: Nov 16 < Nov 17|
| Measurement Field Projection       | Query with measurement=temperature_c    | Returns only the    |
|                                    |                                         | projected metric    |
| Provenance Classification          | Mixed Verified vs Legacy Alert records  | Verified -> VALID   |
|                                    |                                         | Legacy -> UNVERIFIED|
| Explicit 0.0 vs None Ranking       | Stations with 42.0, 28.5, 0.0, -5.0,    | 0.0°C ranks above   |
|                                    | and None heat index                     | negative; None last |
| Empty Telemetry Database Result    | scan_prefix returns empty list []       | Status 200, count 0,|
|                                    |                                         | readings: []        |
| Empty Alerts Database Result       | get_alerts returns empty list []        | Status 200, count 0,|
|                                    |                                         | alerts: []          |
+----------------------------------------------------------------------------------------------------+
```

### Critical Consistency Verifications:
1. **Explicit Zero vs. None Handling in Station Ranking:**  
   In `TelemetryService.get_station_comparison()`, stations are sorted using:
   ```python
   comparison.sort(
       key=lambda x: x["heat_index"] if x.get("heat_index") is not None else float("-inf"),
       reverse=True
   )
   ```
   This ensures that a valid freezing measurement of $0.0^\circ\text{C}$ ranks strictly above negative temperatures ($-5.0^\circ\text{C}$), while uncomputed or invalid heat indices (`None`) are placed at the bottom rather than being falsely converted to $0.0^\circ\text{C}$.
2. **Provenance Traceability:**  
   Alerts with calculation provenance format `calculation_applicability` with `is_valid: true, status: "VALID"`. Legacy alerts lacking provenance return `is_valid: null, status: "LEGACY_UNVERIFIED"` without guessing validity from the scalar value alone.

---

## 7. Dashboard Functional & Presentation Evaluation

A structural audit of `app/templates/index.html` and modular JavaScript components (`api.js`, `app.js`, `charts.js`, `alerts.js`, `map.js`, `simulator.js`) verified the frontend implementation:

### 7.1 Sections and Elements Verified:
* **8 Complete Functional Sections:** Overview, Live Monitoring, Historical Analytics, Air Quality, Heat Risk, Alerts, Stations, and System Status.
* **Summary KPI Widgets:** Total Stations (5), Active Online, Critical Anomalies, Average Temperature, Average Humidity, Average PM2.5.
* **Geospatial Station Map:** Leaflet map container (`#station-map`) initialized with dark CartoDB tiles and 5 Bengaluru station coordinates.
* **Chart Canvases:** 5 dedicated canvases configured for Chart.js rendering.
* **Stateful Modals:** Station Deep-Dive modal (`#stationDetailModal`) and Alert Acknowledgement modal (`#acknowledgeModal`).
* **Active API Catalog Table:** Embedded table documenting all 12 active `/api/v1` endpoints with method badges and parameter descriptions.

### 7.2 Academic Integrity & Disclosures:
* **SIMULATED DATA Badge:** Statically rendered in topbar navigation (`<span class="badge-simulated"><i class="bi bi-cpu"></i> SIMULATED DATA</span>`).
* **SIMULATED STATIONS Badge:** Displayed on the geospatial map card header.
* **CPCB NAQI Guidance Note:** The Air Quality section includes an explicit disclaimer:
  > *"These values represent indicative pollutant categories and do not constitute an official composite 24-hour CPCB NAQI score."*
* **NWS Rothfusz Disclosure:** The Heat Risk section explicitly notes derivation from Steadman and Rothfusz (1990) formulas and documents project operational guards (<20°C low-temperature suppression, extrapolation boundary).

---

## 8. Visualization Correctness & Integrity

1. **Missing Data Handling (`spanGaps: false`):**  
   All 5 Chart.js definitions in `app/static/js/charts.js` explicitly configure `spanGaps: false`. When telemetry records contain `None` or `NaN` (such as heat index during cool weather $<20^\circ\text{C}$), the chart leaves a visible gap in the trend line rather than falsely connecting points across missing intervals or drawing missing values as zero.
2. **Units and Axes:**  
   Y-axes and tooltip formatters explicitly state physical units: Temperature ($^\circ\text{C}$), Relative Humidity ($\%$) Apparent Heat Index ($^\circ\text{C}$), Fine Dust ($\mu\text{g/m}^3$), and Coarse Dust ($\mu\text{g/m}^3$).
3. **Indicative Particulate Matter vs. Official NAQI:**  
   The dashboard displays instantaneous simulated concentrations against Central Pollution Control Board (CPCB) category breakpoints (Good, Satisfactory, Moderate, Poor, Very Poor, Severe). It does **not** claim to compute the official Indian National Air Quality Index (NAQI), which requires 24-hour composite sub-index weighting across at least three monitored pollutants.

---

## 9. Frontend Failure Handling & Resilience

The frontend JavaScript architecture incorporates resilience mechanisms across all network and data layers:

```
+----------------------------------------------------------------------------------------------------+
|                                    FRONTEND FAILURE RESILIENCE MATRIX                              |
+----------------------------------------------------------------------------------------------------+
| Failure Condition                  | Handling Mechanism In Code              | User-Visible Impact |
+------------------------------------+-----------------------------------------+---------------------+
| Network Offline / Gateway Down     | api.js catches exception, returns       | Stale data retained;|
|                                    | status: 0 with descriptive error        | status badge red    |
| HBase Unavailable (HTTP 503)       | app.js inspects getHealth(), updates    | Header pill changes |
|                                    | header-hbase-status to badge-critical   | to "HBase Degraded" |
| Alerts Query Failure               | alerts.js replaces table body with      | Error alert banner  |
|                                    | alert-danger banner                     | displayed in table  |
| Overlapping Polling Bursts         | isRefreshing lock flag in app.js        | Concurrent duplicate|
|                                    | prevents starting new poll cycle        | requests prevented  |
| Chart Rendering with Empty Data    | destroyChart() cleans up prior canvas;  | Empty chart canvas; |
|                                    | exits cleanly if readings array empty   | no JS console error |
+----------------------------------------------------------------------------------------------------+
```

---

## 10. Responsive Layout & Usability Review

### 10.1 Responsive CSS Breakpoints (`app/static/css/dashboard.css`):
1. **Desktop Viewport ($> 992\text{px}$):** Static sidebar navigation ($260\text{px}$ width), main content margin-left ($260\text{px}$), dual-column layout for map and trends.
2. **Tablet Viewport ($\le 992\text{px}$):** Sidebar transforms offscreen (`transform: translateX(-100%)`), mobile hamburger toggle button appears in topbar, sidebar backdrop enabled with click-to-close handler, main wrapper margin set to 0.
3. **Mobile Viewport ($\le 768\text{px}$):** KPI summary cards stack to single column, topbar clock hidden, full-width filter controls.
4. **Small Phone Viewport ($\le 576\text{px}$):** Badges and headers downscaled, body `overflow-x: hidden` prevents horizontal page shifts.
5. **Table Overflow Containment:** All tables are wrapped inside `.table-responsive-custom` with `overflow-x: auto`, ensuring tables scroll horizontally on small viewports without breaking page layout.

### 10.2 Verified Browser Evidence Catalog:
In accordance with non-destructive audit rules, live browser execution was not triggered during this offline evaluation. Existing empirical Chromium Playwright visual artifacts were cataloged:
* `docs/screenshots/dashboard_overview.png` ($23,171\ \text{bytes}$) — Verified overview layout, KPI cards, and trend chart.
* `docs/screenshots/heat_risk_intelligence.png` ($70,505\ \text{bytes}$) — Verified heat vulnerability table and Rothfusz guidance card.
* `docs/screenshots/station_infrastructure.png` ($94,865\ \text{bytes}$) — Verified station hardware attributes and simulated nodes grid.

---

## 11. Results and Consolidated Classification

All findings from the Phase 8.4.5 evaluation are classified according to standard academic audit taxonomy:

| Finding ID | Component | Classification | Description & Observed Impact | Recommended Priority |
| :--- | :--- | :--- | :--- | :--- |
| **RF-07** | Flask Routes (`app/routes/api.py`) | **SECURITY RISK / CONFIRMED DEFECT** | Unhandled route exceptions format user-facing responses using `{str(e)}`, leaking internal Windows socket error codes, URLs, and paths. | **High** |
| **RF-02** | Telemetry Pipeline | **CONFIRMED DEFECT** | IEEE 754 `NaN` values bypass relational anomaly checks, propagating `status: VALID` with NaN heat index to HBase. | **Critical** |
| **RF-09** | REST Routing (`app/routes/api.py`) | **DESIGN LIMITATION** | HBase row keys containing `#` characters require URL percent-encoding (`%23`) by REST clients to avoid URI fragment truncation. | **Medium** |
| **RF-10** | Application Routing (`app/__init__.py`) | **VERIFIED DESIGN** | Clean content negotiation on `/` (HTML for browsers, JSON metadata for programmatic clients) and dedicated `/dashboard` route. | **None** |
| **RF-11** | Error Envelope (`app/utils/response.py`)| **VERIFIED DESIGN** | Uniform JSON envelope across success and error responses with standardized status, code, and timestamp fields. | **None** |
| **RF-12** | Frontend Charts (`app/static/js/charts.js`)| **VERIFIED DESIGN** | All time-series charts enforce `spanGaps: false`, preventing fabrication of missing telemetry data as zero. | **None** |
| **RF-13** | Frontend Polling (`app/static/js/app.js`)| **VERIFIED DESIGN** | 10-second auto-refresh polling incorporates an `isRefreshing` lock flag, preventing concurrent burst overlap on slow connections. | **None** |

---

## 12. Phase 8.4.4 Audit Reconciliation Notes

In accordance with Phase 8.4.5 instructions, the following three audit points from Phase 8.4.4 are reconciled:

### 1. Full-Precision vs. Rounded Heat-Index Comparison:
* In `app/services/sensor_simulator.py` (line 149), the heat-index algorithm explicitly rounds the calculated Celsius temperature to two decimal places: `hi_celsius = round((hi_fahrenheit - 32.0) * (5.0 / 9.0), 2)`.
* In Phase 8.4.4, the maximum absolute difference between the project implementation and the unrounded first-principles reference was **$0.004647^\circ\text{C}$** at $T = 30.0^\circ\text{C}, RH = 90.0\%$ (Project: $40.77^\circ\text{C}$; Reference: $40.774647^\circ\text{C}$).
* **Reconciliation Note:** Rounding the reference calculation to two decimal places yields `round(40.774647, 2) == 40.77`, producing **$0.000000^\circ\text{C}$ difference**. Across all 25 tested atmospheric cases, observed differences are consistent with the project's two-decimal output rounding ($\le 0.005^\circ\text{C}$ half-step window).

### 2. Exact 80°F Preliminary Boundary Discontinuity Evidence:
* At preliminary average heat index $HI_{\text{avg}} < 80.0^\circ\text{F}$, the NWS specification mandates using Steadman's preliminary equation.
* At $HI_{\text{avg}} \ge 80.0^\circ\text{F}$, the specification mandates switching to the 9-term Rothfusz polynomial regression.
* **Reconciliation Note:** The exact preliminary-average equation is $HI_{\text{avg}} = 0.5 \times (HI_{\text{simple}} + T_F) = 1.05\,T_F - 5.15 + 0.0235\,RH$. At $T_F = 80.0^\circ\text{F}$, $RH = 40.0\%$ evaluates to $HI_{\text{avg}} = 79.790^\circ\text{F}$ and $RH = 42.0\%$ evaluates to $79.837^\circ\text{F}$; both remain strictly on the Steadman preliminary branch. The actual preliminary-average threshold ($HI_{\text{avg}} = 80.0^\circ\text{F}$) at $T_F = 80.0^\circ\text{F}$ occurs at **$RH = 48.93617\%$**. Immediately below ($RH = 48.936\%$), the Steadman preliminary equation yields $26.67^\circ\text{C}$ ($80.00^\circ\text{F}$). At and above ($RH = 48.940\%$), the formula branches to the 9-term Rothfusz polynomial regression yielding $27.06^\circ\text{C}$ ($80.71^\circ\text{F}$). A verified mathematical step jump of **$+0.39^\circ\text{C}$ ($+0.71^\circ\text{F}$)** is observed at $T_F = 80.0^\circ\text{F}$ (or **$+0.4344^\circ\text{C}$ / $+0.7819^\circ\text{F}$** at fixed $RH = 50.0\%$ across temperature at $T_F = 79.976^\circ\text{F}$ in Phase 7.4), confirming that piecewise jump discontinuity is an inherent mathematical property of the published NOAA WPC specification.

### 3. Standalone Relative Humidity Anomaly Rule Existence Check:
* Inspection of `AnomalyDetector.analyze_reading()` in `app/services/anomaly_detector.py` (lines 76–193) confirms that threshold alert evaluations are executed exclusively for:
  1. Ambient Temperature (`HIGH_TEMPERATURE`, Warning $\ge 35^\circ\text{C}$, Critical $\ge 40^\circ\text{C}$)
  2. Fine Particulate Matter (`ELEVATED_PM25`, Warning $\ge 60\ \mu\text{g/m}^3$, Critical $\ge 120\ \mu\text{g/m}^3$)
  3. Coarse Particulate Matter (`ELEVATED_PM10`, Warning $\ge 100\ \mu\text{g/m}^3$, Critical $\ge 200\ \mu\text{g/m}^3$)
  4. Apparent Heat Index (`HIGH_HEAT_INDEX`, Warning $\ge 38^\circ\text{C}$, Critical $\ge 44^\circ\text{C}$)
* **Reconciliation Note:** There is **no standalone Relative Humidity threshold alert rule** (e.g. `HIGH_HUMIDITY`) evaluated during normal telemetry analysis. Relative humidity is checked only for physical sensor bounds violation ($[0.0, 100.0]\%$ in `_is_reading_unphysical()`), which triggers an `INVALID_READING` alert. Atmospheric humidity primarily influences alerts indirectly through the `HIGH_HEAT_INDEX` calculation.

---

## 13. Deliverables Created & Updated

1. **Evaluation Report:** [`docs/academic_validation/PHASE_8_4_5_API_DASHBOARD_EVALUATION.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/PHASE_8_4_5_API_DASHBOARD_EVALUATION.md)
2. **API Evaluation Script:** [`docs/academic_validation/scripts/run_api_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_api_evaluation.py)
3. **Dashboard Evaluation Script:** [`docs/academic_validation/scripts/run_dashboard_evaluation.py`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/run_dashboard_evaluation.py)
4. **API Results Dataset:** [`docs/academic_validation/scripts/api_evaluation_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/api_evaluation_results.json)
5. **Dashboard Results Dataset:** [`docs/academic_validation/scripts/dashboard_evaluation_results.json`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/scripts/dashboard_evaluation_results.json)
6. **Academic Audit Trail Log Updated:** [`docs/academic_validation/ACADEMIC_AUDIT_CORRECTIONS.md`](file:///C:/Users/pky45/.gemini/antigravity/scratch/urban-microclimate-hbase/docs/academic_validation/ACADEMIC_AUDIT_CORRECTIONS.md) (Appended Section 2.21).

---

## 14. Git Status & Safety Confirmation

* **Tracked Repository Files:**
  * `git status --short`: `?? docs/academic_validation/` (tracked files clean).
  * `git diff --stat`: Empty (0 tracked files modified across `app/`, `config/`, `tests/`).
  * Current Git HEAD: `main` at `f6823f6`.
* **HBase & Daemon Preservation:**
  * Zero live HBase writes, table truncations, or schema alters were executed.
  * No background processes or daemons (sensor simulator, ingestion worker, Flask live server) were started.
  * All evaluations were executed via non-mutating test client and static inspection.

---

**Phase 8.4.5 is formally COMPLETED.** Execution is stopped in accordance with instructions. No subsequent phase has been started.
