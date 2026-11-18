# Urban Microclimate & Heat-Risk Intelligence System
## REST API Reference Manual (v1.0.0)

**Base URL:** `http://localhost:5000/api/v1`  
**Underlying Datastore:** Apache HBase 2.6.7 (Hadoop 3 binary, standalone mode) via Stargate REST Gateway (`http://localhost:8085`)  
**Data Formats:** JSON (`Content-Type: application/json; charset=utf-8`)

---

## 1. System & Health Endpoints

### 1.1 Cluster Health Check
Checks connectivity to the Apache HBase Stargate REST gateway, verifies existence of all required tables (`microclimate:readings`, `microclimate:alerts`, `microclimate:station_status`), and returns simulator execution status.

- **Endpoint:** `GET /health`
- **Response Codes:**
  - `200 OK`: All systems and HBase tables operational.
  - `503 SERVICE UNAVAILABLE`: HBase or required tables are unreachable or degraded.
- **Example Response (200 OK):**
```json
{
  "status": "success",
  "message": "System and HBase are operational",
  "timestamp": "2026-11-18T00:44:30.123456+00:00",
  "data": {
    "app_status": "UP",
    "hbase_connected": true,
    "hbase_version": "2.6.7-hadoop3",
    "simulator_running": false,
    "tables": {
      "microclimate:alerts": true,
      "microclimate:readings": true,
      "microclimate:station_status": true
    },
    "timestamp": "2026-11-18T00:44:30.123456+00:00"
  }
}
```

---

## 2. Station Metadata & Live Telemetry

### 2.1 List All Stations
Retrieves configured static metadata for all 5 Bengaluru monitoring stations merged with live telemetry values from `microclimate:station_status`.

- **Endpoint:** `GET /stations`
- **Example Response (200 OK):**
```json
{
  "status": "success",
  "message": "Station metadata and live status retrieved",
  "timestamp": "2026-11-18T00:44:31.000000+00:00",
  "data": {
    "total": 5,
    "stations": [
      {
        "station_id": "ST001",
        "station_name": "Bengaluru Central",
        "zone": "Commercial / Urban Core",
        "coordinates": {
          "latitude": 12.9716,
          "longitude": 77.5946
        },
        "connectivity": "ACTIVE",
        "temperature": 31.8,
        "humidity": 53.18,
        "pm25": 53.54,
        "pm10": 85.2,
        "heat_index": 34.76,
        "last_reading_time": "2026-11-17T18:57:29.787566+00:00",
        "data_source": "SIMULATED"
      }
    ]
  }
}
```

### 2.2 Get Specific Station Details
Returns station metadata, current connectivity status, the single latest reading, and the 5 most recent alerts for the given station.

- **Endpoint:** `GET /stations/<station_id>`
- **Parameters:** `station_id` (e.g. `ST001`, `ST002`, `ST003`, `ST004`, `ST005`)
- **Response Codes:**
  - `200 OK`: Station found.
  - `404 NOT FOUND`: Unknown station ID.
- **Example Response (200 OK):**
```json
{
  "status": "success",
  "timestamp": "2026-11-18T00:44:32.000000+00:00",
  "data": {
    "station_id": "ST001",
    "station_name": "Bengaluru Central",
    "zone": "Commercial / Urban Core",
    "coordinates": { "latitude": 12.9716, "longitude": 77.5946 },
    "status": {
      "connectivity": "ACTIVE",
      "last_reading_time": "2026-11-17T18:57:29.787566+00:00"
    },
    "latest_reading": {
      "row_key": "ST001#20261117#8205058150212",
      "temperature_celsius": 31.8,
      "humidity_percent": 53.18,
      "heat_index_celsius": 34.76,
      "pm25": 53.54,
      "pm10": 85.2,
      "sensor_status": "ACTIVE"
    },
    "recent_alerts": []
  }
}
```

---

## 3. Telemetry Time-Series Endpoints

### 3.1 Get Global Latest Telemetry
Queries the newest available readings across all stations (or a single station) globally sorted descending by timestamp.

- **Endpoint:** `GET /telemetry/latest`
- **Query Parameters:**
  - `station_id` (optional): Filter to specific station (`ST001` - `ST005`).
  - `limit` (optional, default `50`, max `500`): Maximum records to return.
- **Example Request:**
  `GET /api/v1/telemetry/latest?station_id=ST001&limit=5`

### 3.2 Historical Station Telemetry (Multi-Date Boundary Compliant)
Queries historical telemetry for a station. Resolves multi-date partitioning across UTC day boundaries, performs exact epoch filtering, and sorts records before applying limits.

- **Endpoint:** `GET /telemetry/<station_id>`
- **Query Parameters:**
  - `start` (optional): Start timestamp in ISO-8601 (e.g. `2026-11-16T00:00:00Z`). Defaults to 24 hours ago.
  - `end` (optional): End timestamp in ISO-8601. Defaults to current time.
  - `measurement` (optional): Filter/project by metric (`temperature`, `humidity`, `pm25`, `pm10`, `pressure`, `heat_index`).
  - `order` (optional, default `desc`): Sort direction (`desc` for newest-first, `asc` for oldest-first).
  - `limit` (optional, default `50`, max `1000`): Maximum records to return.
- **Example Request:**
  `GET /api/v1/telemetry/ST001?start=2026-11-16T12:00:00Z&end=2026-11-17T23:59:59Z&order=desc&limit=10`

---

## 4. Alert Management Endpoints

### 4.1 List Alerts
Queries active and historical alerts stored in `microclimate:alerts` globally sorted newest-first.

- **Endpoint:** `GET /alerts`
- **Query Parameters:**
  - `station_id` (optional): Filter by station.
  - `severity` (optional): `WARNING` or `CRITICAL`.
  - `acknowledged` (optional): `true` or `false`.
  - `limit` (optional, default `20`, max `500`).
- **Example Response:**
```json
{
  "status": "success",
  "data": {
    "count": 1,
    "alerts": [
      {
        "alert_id": "ST001#8205058153242#HIGH_TEMPERATURE",
        "station_id": "ST001",
        "type": "HIGH_TEMPERATURE",
        "severity": "CRITICAL",
        "measurement": "45.17",
        "threshold": "40.0",
        "message": "Extreme heat alert: Temperature at 45.17°C exceeds critical threshold 40.0°C.",
        "timestamp": "2026-11-17T18:57:26.757052+00:00",
        "acknowledged": false
      }
    ]
  }
}
```

### 4.2 Acknowledge Alert
Updates the acknowledgement status of an alert in HBase without mutating the measurement or threshold data.

- **Endpoint:** `POST /alerts/<alert_id>/acknowledge`
- **URL Parameter:** `alert_id` (URL-encoded row key, e.g. `ST001%238205058153242%23HIGH_TEMPERATURE`).
- **Request Body (JSON):**
```json
{
  "note": "Operator acknowledged excessive temperature spike"
}
```

---

## 5. Statistical Analytics Endpoints

### 5.1 Temperature Analytics
- **Endpoint:** `GET /analytics/temperature`
- **Query Parameters:** `station_id` (optional), `days` (optional, default `1`, max `30`).
- **Returns:** Global and station-by-station `count`, `min`, `max`, `average`, and `std_dev`.

### 5.2 Air Quality Analytics
- **Endpoint:** `GET /analytics/air-quality`
- **Query Parameters:** `station_id` (optional), `days` (optional, default `1`, max `30`).
- **Returns:** Aggregate PM2.5 and PM10 metrics and indicative particulate categories (`GOOD`, `SATISFACTORY`, `MODERATE`, `POOR`, `VERY POOR`, `SEVERE`) derived from CPCB India concentration breakpoints.
- **Scientific Methodology Note:** CPCB breakpoints are applied to instantaneous/sampled PM2.5 and PM10 observations to produce an indicative particulate severity category. This is not an official composite 24-hour CPCB NAQI score (which statutory regulations define as a multi-pollutant 24-hour running average).

### 5.3 Station Heat-Risk Comparison
- **Endpoint:** `GET /analytics/station-comparison`
- **Returns:** Side-by-side comparative rankings of all 5 stations ordered descending by Heat Index.
- **Scientific Methodology Note:**
  - Rankings use explicit `None` handling: stations with valid calculated apparent temperatures (including numerical $0.0^\circ\text{C}$) are ranked above uncalculated nodes; stations with missing/invalid heat index (`None`, e.g. low-temperature suppression $< 20^\circ\text{C}$ or divergence safeguard) are placed at the bottom of rankings.
  - Risk categories (`NORMAL` $<32^\circ\text{C}$, `CAUTION` $32-38^\circ\text{C}$, `DANGER / WARNING` $38-44^\circ\text{C}$, `EXTREME DANGER` $\ge 44^\circ\text{C}$) are project-defined operational thresholds mapped from NOAA physiological guidelines for real-time telemetry alarms, distinct from statutory multi-day NWS Heat Advisory/Warning issuances.

---

## 6. Sensor Simulator Control Endpoints

### 6.1 Simulator Status
- **Endpoint:** `GET /simulator/status`
- **Returns:** Runtime state (`running`, `execution_mode`, `stations_count`, `readings_generated`).

### 6.2 Simulator Lifecycle Control
- **Endpoint:** `POST /simulator/control`
- **Supported Payloads:**

**A. Start In-Process Simulator:**
```json
{
  "action": "start",
  "interval_seconds": 5.0
}
```

**B. Stop Simulator:**
```json
{
  "action": "stop"
}
```

**C. Inject Controlled Anomaly:**
```json
{
  "action": "inject_anomaly",
  "station_id": "ST001",
  "anomaly_type": "HIGH_TEMPERATURE",
  "duration_ticks": 4
}
```
*Valid Anomaly Types:* `HIGH_TEMPERATURE`, `HIGH_HUMIDITY`, `ELEVATED_PM25`, `ELEVATED_PM10`, `SENSOR_OFFLINE`, `INVALID_READING`.
