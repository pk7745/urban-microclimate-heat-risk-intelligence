# Project Technical Baseline Audit

**System:** Urban Microclimate & Heat-Risk Intelligence System using Apache HBase  
**Audit Date:** November 2026 (Phase 7.3 Verified & Evidence-Backed Edition)  
**Auditor:** Academic Technical Review Team  
**Workspace:** `C:\Users\pky45\.gemini\antigravity\scratch\urban-microclimate-hbase`  
**Git Commit Baseline:** `f6823f6` (Repository: `https://github.com/pk7745/urban-microclimate-heat-risk-intelligence`)  

---

## 1. Executive Summary & Architectural Overview

The **Urban Microclimate & Heat-Risk Intelligence System** is an end-to-end distributed environmental data pipeline built on **Apache HBase 2.6.7** (Hadoop 3.3.6 substrate) designed for continuous high-frequency microclimate ingestion, physiological heat-stress index calculation, threshold-based environmental anomaly detection, and interactive decision-support visualization.

This document establishes the verified technical baseline of the system as implemented in the Python source code, configuration files, and database schemas.

```
+---------------------------------------------------------------------------------------------------+
|                                  SYSTEM ARCHITECTURAL PIPELINE                                    |
+---------------------------------------------------------------------------------------------------+
|  [Simulated Stations ST001-ST005] (Configured in config/settings.py)                              |
|         | -> 5-second cycle interval (0.2 Hz per station, 1 reading/sec aggregate)                |
|         | -> Diurnal Solar Curve + Autoregressive Drift + Controlled Anomaly Injection            |
|         v                                                                                         |
|  [app/services/sensor_simulator.py]                                                               |
|         | -> NWS Steadman / Rothfusz Heat Index Assessment (assess_heat_index)                    |
|         | -> In-memory Physical Validation & Operational Safeguards                               |
|         v                                                                                         |
|  [app/services/ingestion_service.py]                                                              |
|         | -> Bounded In-Memory Queue (queue.Queue(maxsize=1000))                                  |
|         | -> Non-blocking Put with Queue-Full Drop Counter                                        |
|         | -> Single Background Consumer Worker Thread                                             |
|         v                                                                                         |
|  [app/services/anomaly_detector.py]                                                               |
|         | -> Rule-Based Multi-Metric Threshold Evaluation (Temp, PM2.5, PM10, Heat Index)         |
|         | -> Hardware Failure & Unphysical Reading Checks                                         |
|         | -> In-memory State Tracking & 60-second Alert Deduplication Cooldown                     |
|         v                                                                                         |
|  [app/services/hbase_client.py (Stargate REST Gateway :8085)]                                     |
|         |                                                                                         |
|         +---> microclimate:readings        (Row Key: STATION#YYYYMMDD#REV_TS_MS)                  |
|         +---> microclimate:alerts          (Row Key: STATION#REV_TS_MS#ALERT_TYPE)                |
|         +---> microclimate:station_status  (Row Key: STATION_ID)                                  |
|         v                                                                                         |
|  [Flask REST API :5000 (app/routes/api.py)]                                                       |
|         | -> Multi-date partition querying, in-memory timestamp sorting, alert acknowledgement   |
|         v                                                                                         |
|  [Interactive Dashboard (app/static/js/app.js + Leaflet.js + Chart.js)]                          |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Component Technical Audits

### Component 1: Sensor Simulation Engine
* **Source Location:** `app/services/sensor_simulator.py` (`SensorStation`, `SensorSimulatorManager`)
* **Mathematical & Algorithmic Formulation:**
  Each station implements an autoregressive first-order stochastic drift model combined with a deterministic sinusoidal diurnal solar cycle.
  
  #### Critical Audit of the Diurnal Equation & Timezone Offset (Task 4 Finding)
  In `SensorStation.generate_reading()`, the diurnal offsets are computed as follows:
  ```python
  now = datetime.now(timezone.utc)
  hour_frac = now.hour + (now.minute / 60.0)
  diurnal_temp_delta = 2.5 * math.sin((hour_frac - 9.0) * math.pi / 12.0)
  diurnal_humidity_delta = -4.0 * math.sin((hour_frac - 9.0) * math.pi / 12.0)
  ```
  - **Mathematical Analysis of the Peak:**
    Let $h = \text{hour\_frac}$ represent the decimal hour input. The function $\sin(\theta)$ reaches its mathematical maximum $+1.0$ at $\theta = \frac{\pi}{2}$:
    $$\frac{(h - 9.0) \cdot \pi}{12.0} = \frac{\pi}{2} \implies \frac{h - 9.0}{12.0} = \frac{1}{2} \implies h - 9.0 = 6.0 \implies h = 15.0$$
    The mathematical minimum $-1.0$ occurs at:
    $$\frac{(h - 9.0) \cdot \pi}{12.0} = -\frac{\pi}{2} \implies h - 9.0 = -6.0 \implies h = 3.0$$
    The zero-crossing ($\sin(\theta) = 0$) occurs at $h = 9.0$ and $h = 21.0$.
  - **Timezone Audit (UTC vs. IST):**
    The Python code extracts `now` directly in UTC (`timezone.utc`). **No timezone offset conversion to Indian Standard Time (IST = UTC + 5:30) is applied before calculating `hour_frac`**.
    - Evaluated directly in UTC, the mathematical peak (+2.5°C) occurs at **$15:00\ \text{UTC}$**, which corresponds to **$20:30\ \text{IST}$** (8:30 PM local Bengaluru time).
    - The developer's inline code comment states:
      `# Diurnal solar cycle: peak at 14:00 UTC+5.30 (approx 08:30 UTC), minimum at 05:00 UTC+5.30`
  - **Academic Audit Finding:**  
    There is a documented algebraic discrepancy between the developer's intended physical solar peak (14:00 IST / ~08:30 UTC) and the implemented formula. At $h = 9.0\ \text{UTC}$ ($14:30\ \text{IST}$), the function evaluates to $\sin(0) = 0.0$ (zero delta), while the actual maximum (+2.5°C) is reached 6 hours later at $15:00\ \text{UTC}$ ($20:30\ \text{IST}$).  
    *Recommendation:* Application code was intentionally not modified during this read-only audit. A future correction should introduce an explicit local timezone conversion (`hour_ist = (now_utc + timedelta(hours=5, minutes=30)).hour...`) only after intended simulation behavior is confirmed by project stakeholders.

  - **Autoregressive Drift & Noise:**
    $$T_t = 0.80 \cdot T_{t-1} + 0.20 \cdot (T_{\text{baseline}} + \Delta T_{\text{diurnal}}) + \epsilon_T, \quad \epsilon_T \sim \mathcal{N}(0, 0.15^2), \quad T_t \in [15.0, 50.0]^\circ\text{C}$$
    $$RH_t = 0.80 \cdot RH_{t-1} + 0.20 \cdot (RH_{\text{baseline}} + \Delta RH_{\text{diurnal}}) + \epsilon_{RH}, \quad \epsilon_{RH} \sim \mathcal{N}(0, 0.40^2), \quad RH_t \in [10.0, 100.0]\%$$
    $$PM2.5_t = 0.85 \cdot PM2.5_{t-1} + 0.15 \cdot PM2.5_{\text{baseline}} + \epsilon_{PM2.5}, \quad \epsilon_{PM2.5} \sim \mathcal{N}(0, 1.20^2), \quad PM2.5_t \in [5.0, 500.0]\ \mu\text{g/m}^3$$
    $$PM10_t = 0.85 \cdot PM10_{t-1} + 0.15 \cdot PM10_{\text{baseline}} + \epsilon_{PM10}, \quad \epsilon_{PM10} \sim \mathcal{N}(0, 2.00^2), \quad PM10_t \in [10.0, 800.0]\ \mu\text{g/m}^3$$
    $$P_t = 0.90 \cdot P_{t-1} + 0.10 \cdot P_{\text{baseline}} + \epsilon_P, \quad \epsilon_P \sim \mathcal{N}(0, 0.05^2)\ \text{hPa}$$

* **Configured Stations (5 Macro-Zones across Bengaluru):**
  Defined in `config/settings.py`:
  1. `ST001` (Bengaluru Central - Commercial / Urban Core): Lat 12.9716, Lon 77.5946. Baselines: $T=31.0^\circ\text{C}, RH=55.0\%, PM2.5=52.0, PM10=85.0, P=920.0\ \text{hPa}$.
  2. `ST002` (Bengaluru East - Tech Corridor / Dense Traffic): Lat 12.9784, Lon 77.6408. Baselines: $T=30.0^\circ\text{C}, RH=58.0\%, PM2.5=46.0, PM10=76.0, P=921.0\ \text{hPa}$.
  3. `ST003` (Bengaluru South - Residential / Green Canopy): Lat 12.9250, Lon 77.5938. Baselines: $T=28.5^\circ\text{C}, RH=64.0\%, PM2.5=32.0, PM10=52.0, P=923.0\ \text{hPa}$.
  4. `ST004` (Bengaluru West - Industrial / Transit Interchange): Lat 12.9750, Lon 77.5350. Baselines: $T=31.5^\circ\text{C}, RH=52.0\%, PM2.5=58.0, PM10=98.0, P=919.0\ \text{hPa}$.
  5. `ST005` (Bengaluru North - Highway / Peri-urban): Lat 13.0358, Lon 77.5970. Baselines: $T=29.5^\circ\text{C}, RH=60.0\%, PM2.5=42.0, PM10=78.0, P=922.0\ \text{hPa}$.

* **Generation Timing & Frequency:**
  Configured interval: `settings.SIMULATOR_INTERVAL_SECONDS = 5.0` seconds. In each cycle, the manager generates readings for all 5 stations and sleeps for the remainder of the 5-second window. This produces an aggregate generation rate of 1 reading per second (0.2 Hz per station).

---

### Component 2: Ingestion Queue & Backpressure Engine
* **Source Location:** `app/services/ingestion_service.py` (`IngestionService`)
* **Queue Architecture & Buffer Capacity:**
  - In-memory bounded queue: `queue.Queue(maxsize=1000)` configured via `settings.INGESTION_QUEUE_MAXSIZE`.
  - Non-blocking producer insertion: `submit_reading()` executes `self.queue.put(reading, block=False)`.
  - Overflow / Drop Policy: When the queue reaches 1,000 items, `queue.Full` is caught, the reading is dropped immediately without blocking the simulator thread, and `metrics["dropped_due_to_queue_full"]` is incremented.
* **Consumer Worker & Throughput Profile:**
  - Single background daemon thread (`_worker_loop`) with 1.0-second timeout on `queue.get()`.
  - Configured generation rate: 1 reading/second aggregate.
  - Measured single-worker ingestion throughput: ~40–80 sequential writes/second over HTTP REST in local environment.
  - Theoretical scalability: Higher write rates require a multi-threaded consumer pool and HBase batch put mutations.

---

### Component 3: Apache HBase Schemas & Row-Key Architecture

#### Row-Key Ordering & Multi-Date Partitioning
The HBase row key for sensor readings is:
$$\text{RowKey}_{\text{reading}} = \text{STATION\_ID} + \text{"\#"} + YYYYMMDD + \text{"\#"} + (9999999999999 - t_{\text{epoch\_ms}})$$
where `MAX_REVERSE_EPOCH_MS = 9999999999999`.

1. **Within a Single Date Partition:**  
   Because the station ID and date string are identical, smaller reverse timestamps sort first. Since smaller reverse timestamps represent larger epoch times, **records within a single calendar date sort in descending chronological order (newest first)**.
2. **Across Multiple Date Partitions:**  
   Because the date string `YYYYMMDD` precedes the reverse timestamp, HBase sorts rows by date ascending (`20261117` precedes `20261118`). **HBase does NOT sort records newest-first globally across dates**.
3. **Application-Side Multi-Date Query Solution:**  
   In `app/services/telemetry_service.py` (`get_station_telemetry` and `get_latest_telemetry`), multi-date queries perform separate prefix scans per date partition, merge the returned records in memory, and sort them globally using Python's `sort(key=lambda x: x["timestamp_ms"], reverse=True)`.
4. **Retrieval of the Latest Reading:**  
   Direct $O(1)$ point lookup of the latest station reading is supported by querying the `microclimate:station_status` table directly using row key `STATION_ID`.

---

### Component 4: Biometeorological Heat Index & Scientific Safeguards
* **Source Location:** `app/services/sensor_simulator.py` (`assess_heat_index()`, `calculate_heat_index()`)
* **Scientific Reference:** National Weather Service (NWS) / NOAA Technical Attachment SR 90-23 (Rothfusz, 1990); Steadman (1979).
* **Three-Tier Scientific Categorization:**
  - **Level A (Official NWS Formula):** Steadman preliminary equation, averaging step, $80.0^\circ\text{F}$ branching, 9-term Rothfusz polynomial regression, and low/high-RH empirical adjustments.
  - **Level B (Project-Specific Operational Policies):** Low-temperature suppression below $20.0^\circ\text{C}$ (`NOT_APPLICABLE_LOW_TEMPERATURE`), physical atmospheric boundary validation ($RH \in [0, 100]\%$, $T \in [-50, 65]^\circ\text{C}$), and conservative polynomial divergence guards ($T_F > 110.0^\circ\text{F}$ and $RH > 40.0\%$).
  - **Level C (Real-World Accuracy Validation):** Unperformed because current data is synthetically simulated.

---

### Component 5: Anomaly Detection Engine & Operational Alerting
* **Source Location:** `app/services/anomaly_detector.py` (`AnomalyDetector`)
* **Detection Model:** Rule-based multi-metric static threshold evaluation.
* **Configured Thresholds (`config/settings.py`):**
  - Ambient Air Temperature: Warning $\ge 35.0^\circ\text{C}$, Critical $\ge 40.0^\circ\text{C}$.
  - PM2.5 (Fine Particulates): Warning $\ge 60.0\ \mu\text{g/m}^3$, Critical $\ge 120.0\ \mu\text{g/m}^3$.
  - PM10 (Coarse Particulates): Warning $\ge 100.0\ \mu\text{g/m}^3$, Critical $\ge 200.0\ \mu\text{g/m}^3$.
  - NWS Heat Index: Warning $\ge 38.0^\circ\text{C}$, Critical $\ge 44.0^\circ\text{C}$.
  - Hardware / Comm Status: `OFFLINE` $\rightarrow$ Critical `SENSOR_OFFLINE`; unphysical readings $\rightarrow$ Critical `INVALID_READING`.
* **Stateful Deduplication & Cooldown Logic:**
  - In-memory cooldown of 60.0 seconds per `(station_id, alert_type)`.
  - Severity Escalation Bypass: Warning $\rightarrow$ Critical bypasses cooldown immediately.
  - Automatic clearing via `_clear_condition_if_recovered()` when readings normalize.

---

### Component 6: Test Suite Architecture & Execution Status
* **Test Suite Files in Workspace:** `test_heat_index_safeguards.py`, `test_row_key.py`, `test_sensor_simulator.py`, `test_anomaly_detector.py`, `test_api.py`, `test_hbase_client.py`, `test_dashboard.py`, `test_failure_scenarios.py`.
* **Execution Evidence (Phase 7.3):**
  - **Independent Verification Script (`verify_heat_index_reference.py`):** 12 / 12 tests passed (7 formula parity, 5 operational policies).
  - **Safe Offline Unit Tests (Pytest):** 30 passed, 0 failed across `test_row_key.py` (5), `test_sensor_simulator.py` (7), `test_anomaly_detector.py` (6), and `test_heat_index_safeguards.py` (12 passed, 1 deselected live test).
  - **Pending Tests:** 16 live REST tests in `test_api.py` and 2 mutating client tests in `test_hbase_client.py`.

---

### Component 7: Preserved Historical Data Records
* **Storage Engine:** Apache HBase 2.6.7 on Hadoop 3.3.6.
* **Preserved Records:** `readings=149`, `alerts=21`, `station_status=5`.
* **Phase 5.1 Verification Record (Immutable Anchor):** Row Key `ST001#20261118#8205027936173`, Provenance `SIMULATED_TEST_VERIFICATION`.
