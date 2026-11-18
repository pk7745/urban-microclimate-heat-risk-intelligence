# Frontend Architecture & Technical Specification
## Urban Microclimate & Heat-Risk Intelligence System (Phase 4)

### 1. Overview
The frontend is an enterprise-grade dark-themed command center built to visualize, monitor, and manage the urban microclimate telemetry persisted in **Apache HBase 2.6.7**. It is designed as an interactive single-page application (SPA) served directly by Flask via Jinja2 templates and modular vanilla ES6 JavaScript modules, avoiding unnecessary heavyweight build-step overhead.

---

### 2. Design System & Theming
- **Palette:**
  - Background (Dark Space): `#0a0f1d`
  - Surface Background: `#111a2e`
  - Cards & Panels: `#15223c` (hover: `#1c2c4d`)
  - Borders: `#1e3152`
  - Accent Cyan: `#00d2ff` (primary highlights, brand icon)
  - Accent Blue: `#3b82f6` (information, links, secondary charts)
  - Accent Amber: `#f59e0b` (temperature, warning alerts, heat caution)
  - Accent Red: `#ef4444` (critical anomalies, heat danger, errors)
  - Accent Purple: `#a855f7` (fine particulate matter PM2.5)
  - Accent Green: `#10b981` (active status, verified metrics)
- **Typography:**
  - Sans-Serif: `Inter` (Google Fonts) for high legibility at dashboard density.
  - Monospace: `JetBrains Mono` / `SF Mono` for timestamps, row keys, IDs, and sensor values.

---

### 3. Module Hierarchy

```
app/
├── templates/
│   └── index.html                # Master semantic HTML structure & layout
└── static/
    ├── css/
    │   └── dashboard.css         # Dark theme styling, animations, responsive grid
    └── js/
        ├── api.js                # Centralized REST client (fetch wrapper, error handling)
        ├── charts.js             # Chart.js managers (responsive dark-themed time-series)
        ├── map.js                # Leaflet mapping module (custom markers, CartoDB tiles)
        ├── alerts.js             # Alert table manager & acknowledgement modal
        ├── simulator.js          # Simulator lifecycle & anomaly injection controller
        └── app.js                # Master coordinator (routing, auto-refresh, clock)
```

---

### 4. Component Details

#### A. Centralized API Service (`api.js`)
Encapsulates all asynchronous network requests to `/api/v1/*` endpoints:
- `getHealth()`: Polls `/api/v1/health` for HBase and cluster status.
- `getStations()`, `getStation(id)`: Queries station metadata merged with live HBase status.
- `getLatestTelemetry(params)`: Retrieves time-series records sorted descending.
- `getStationTelemetry(id, params)`: Multi-date partition historical scanning.
- `getAlerts(params)`: Queries active and acknowledged alerts from `microclimate:alerts`.
- `acknowledgeAlert(id, note)`: Safe POST mutation of HBase alert acknowledgement column.
- `getStationComparison()`, `getAirQualityAnalytics()`, `getTemperatureAnalytics()`: Analytical summaries.
- `getSimulatorStatus()`, `controlSimulator(payload)`: In-process simulator lifecycle management.

#### B. Mapping Engine (`map.js`)
- **Technology:** Leaflet 1.9.4 with CartoDB Dark Matter basemap tiles.
- **Station Nodes:** 5 verified geographical coordinates across the Bengaluru metropolitan region:
  - `ST001`: Bengaluru Central (`12.9716, 77.5946`)
  - `ST002`: Bengaluru East (`12.9784, 77.6408`)
  - `ST003`: Bengaluru South (`12.9250, 77.5938`)
  - `ST004`: Bengaluru West (`12.9750, 77.5350`)
  - `ST005`: Bengaluru North (`13.0358, 77.5970`)
- **Dynamic Pins:** Custom SVG markers color-coded by connectivity and apparent thermal stress with popups revealing live metrics.
- **Disclosure:** Explicitly labeled as `SIMULATED STATIONS` in compliance with academic project standards.

#### C. Chart Visualizations (`charts.js`)
- **Technology:** Chart.js 4.4.2.
- **Visualizations:**
  1. *Citywide Environmental Dynamics (Overview):* Multi-line trend of Temperature, Humidity, and PM2.5.
  2. *Live Monitoring Time Series:* High-resolution single-metric stream with user-selectable units.
  3. *Historical Analytics Trends:* Date-bounded prefix scan time series.
  4. *Particulate Matter Comparison (Air Quality):* Dual-bar PM2.5 vs PM10 comparison across all 5 nodes.
  5. *Sensible vs Apparent Heat Stress (Heat Risk):* Ambient Dry-Bulb vs NOAA Heat Index comparison.
- **Data Integrity:** Employs `spanGaps: false` so missing or invalid readings are never fabricated or drawn as zero.

#### D. Alert Management (`alerts.js`)
- Interactive filter bar for station, severity (`CRITICAL`, `WARNING`), and acknowledgement status (`Acknowledged`, `Unacknowledged`).
- Historical Alert Governance: Distinctly labels legacy alerts lacking provenance metadata as `LEGACY_UNVERIFIED` without evaluating validity from the output scalar alone.
- Non-Destructive Mutation: Allows operators to acknowledge alerts with custom notes via modal, writing to `metadata:acknowledged` in HBase without deleting records.

#### E. System Simulator Controls (`simulator.js`)
- Displays background execution state, sampling frequency, and reading count.
- Thread-safe start/stop controls with confirmation safeguards.
- Interactive anomaly injector supporting 6 scenarios: `HIGH_TEMPERATURE`, `HIGH_HUMIDITY`, `ELEVATED_PM25`, `ELEVATED_PM10`, `SENSOR_OFFLINE`, `INVALID_READING`.

---

### 5. Polling & Real-Time Synchronization
- **Background Interval:** Polls the backend every 10 seconds (`REFRESH_INTERVAL_MS = 10000`).
- **Overlap Prevention:** Employs an `isRefreshing` execution lock to prevent overlapping HTTP bursts on slower connections.
- **Resilience:** If an HBase request encounters a transient failure, previous metrics are retained on the dashboard while an alert indicates potential stale state.

---

### 6. Scientific & Operational Integrity Disclosures

1. **Representative Simulated Coordinates:**
   Station coordinates correspond to actual geographic neighborhoods in Bengaluru (Central, Indiranagar, Jayanagar, Rajajinagar, Hebbal) chosen to simulate realistic urban morphology microclimates. They serve as representative spatial demonstration locations rather than physical IoT field enclosures.

2. **Indicative Particulate Matter Categories (CPCB Breakpoints):**
   The Air Quality section evaluates instantaneous / sampled $\text{PM}_{2.5}$ and $\text{PM}_{10}$ observations against Central Pollution Control Board (CPCB) India breakpoint ranges. These provide immediate indicative pollutant risk categories (`GOOD` to `SEVERE`). They are explicitly disclosed as indicative categories and do not constitute an official 24-hour composite statutory CPCB NAQI score.

3. **Project-Defined Operational Heat-Risk Thresholds:**
   Apparent thermal stress categories are discretized into operational early-warning boundaries ($<32^\circ\text{C}$ Normal, $32-38^\circ\text{C}$ Caution, $38-44^\circ\text{C}$ Warning/Extreme Caution, $\ge 44^\circ\text{C}$ Danger/Critical). These represent real-time sensor anomaly triggers mapped from NOAA biometeorological guidelines, distinct from multi-day statutory NWS Heat Advisories or Excessive Heat Warnings.

4. **Historical Event Logs vs. Current Station Connectivity:**
   The `microclimate:alerts` table functions as an append-only historical audit log of all threshold violations detected since cluster inception. Rows retain their historical state, provenance tags, and legacy metadata (e.g. `LEGACY_UNVERIFIED`). Current operational health and latest sensor readings are decoupled and tracked independently in `microclimate:station_status`.

5. **Simulated Nature of Observations:**
   All sensor streams are synthesized through physical diurnal cycles, autoregressive drifts, and controlled anomaly models, labeled with `data_source: "SIMULATED"` across all API contracts and UI views.
