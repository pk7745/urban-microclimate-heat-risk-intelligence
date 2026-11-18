/**
 * Main Application Orchestration Module.
 * Controls routing/navigation, data polling, clock synchronization,
 * section rendering, and connects UI components to API services.
 */
const App = (function () {
  let activeSection = 'overview';
  let stationsCache = [];
  let isRefreshing = false;
  let refreshTimer = null;
  const REFRESH_INTERVAL_MS = 10000; // 10s auto-refresh
  let lastRefreshTime = null;

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initNavigation();
    initEventListeners();

    // Initial Data Load
    refreshAllData();

    // Start Auto-refresh interval
    refreshTimer = setInterval(() => {
      refreshAllData(true);
    }, REFRESH_INTERVAL_MS);
  });

  // ---------------------------------------------------------------------------
  // Topbar Clock
  // ---------------------------------------------------------------------------
  function initClock() {
    function update() {
      const now = new Date();
      const localTimeStr = now.toLocaleTimeString([], { hour12: false });
      const localDateStr = now.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
      const utcTimeStr = now.toISOString().substring(11, 19) + ' UTC';

      const clockEl = document.getElementById('topbar-clock');
      if (clockEl) {
        clockEl.innerHTML = `<span>${localDateStr} ${localTimeStr}</span> <span class="text-muted ms-1 font-mono" style="font-size: 0.725rem;">(${utcTimeStr})</span>`;
      }
    }
    update();
    setInterval(update, 1000);
  }

  // ---------------------------------------------------------------------------
  // Navigation & Routing
  // ---------------------------------------------------------------------------
  function initNavigation() {
    // Hash change listener
    window.addEventListener('hashchange', () => {
      const hash = window.location.hash.replace('#', '') || 'overview';
      switchSection(hash);
    });

    // Check initial hash
    const initialHash = window.location.hash.replace('#', '') || 'overview';
    switchSection(initialHash);

    // Mobile sidebar toggle, close button & backdrop
    const toggleBtn = document.getElementById('mobile-menu-toggle');
    const closeBtn = document.getElementById('mobile-sidebar-close');
    const backdrop = document.getElementById('sidebar-backdrop');
    const sidebar = document.querySelector('.sidebar');

    function closeSidebar() {
      if (sidebar) sidebar.classList.remove('open');
      if (backdrop) backdrop.classList.remove('show');
    }

    if (toggleBtn && sidebar) {
      toggleBtn.addEventListener('click', () => {
        const isOpen = sidebar.classList.toggle('open');
        if (backdrop) backdrop.classList.toggle('show', isOpen);
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', closeSidebar);
    }
    if (backdrop) {
      backdrop.addEventListener('click', closeSidebar);
    }
  }

  const ALIAS_MAP = {
    'telemetry': 'live',
    'heat-stress': 'heat-risk',
    'heat-stress-intelligence': 'heat-risk',
    'simulator': 'system',
    'api-catalog': 'system',
    'health': 'system'
  };

  const VALID_SECTIONS = ['overview', 'live', 'analytics', 'air-quality', 'heat-risk', 'alerts', 'stations', 'system'];

  function switchSection(rawSectionId) {
    const canonicalId = ALIAS_MAP[rawSectionId] || rawSectionId;
    const sectionId = VALID_SECTIONS.includes(canonicalId) ? canonicalId : 'overview';
    activeSection = sectionId;

    // Update nav links
    document.querySelectorAll('.nav-link-custom').forEach(link => {
      const href = link.getAttribute('href');
      if (href === `#${sectionId}` || href === `#${rawSectionId}`) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    // Update section visibility
    document.querySelectorAll('.dashboard-section').forEach(sec => {
      if (sec.id === `section-${sectionId}`) {
        sec.style.display = 'block';
      } else {
        sec.style.display = 'none';
      }
    });

    // Update page title
    const titleMap = {
      'overview': 'Citywide Environmental Overview',
      'live': 'Real-Time Sensor Telemetry',
      'telemetry': 'Real-Time Sensor Telemetry',
      'analytics': 'Historical Multi-Day Analytics',
      'air-quality': 'Urban Air Quality & Indicative PM Categories',
      'heat-risk': 'Microclimate Heat Stress & Risk Intelligence',
      'heat-stress': 'Microclimate Heat Stress & Risk Intelligence',
      'alerts': 'Real-Time Anomaly & Threshold Alerts',
      'stations': 'Sensor Station Infrastructure Management',
      'system': 'System Architecture & HBase Cluster Health',
      'simulator': 'Sensor Simulation & Telemetry Controls',
      'api-catalog': 'Active REST API Endpoints Catalog'
    };
    const titleEl = document.getElementById('current-page-title');
    if (titleEl) {
      titleEl.textContent = titleMap[rawSectionId] || titleMap[sectionId] || 'Microclimate Intelligence';
    }

    // Trigger map resize if switching to overview
    if (sectionId === 'overview') {
      MapManager.resize();
    }

    // Trigger section-specific loads
    loadSectionData(sectionId);

    // Close mobile menu if open
    const sidebar = document.querySelector('.sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (sidebar) sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('show');
  }

  // ---------------------------------------------------------------------------
  // Event Listeners for Filters & Actions
  // ---------------------------------------------------------------------------
  function initEventListeners() {
    // Manual Refresh Button
    const refreshBtn = document.getElementById('btn-manual-refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        refreshAllData(false);
      });
    }

    // Live Monitoring Filters
    const liveStationSelect = document.getElementById('live-filter-station');
    const liveMetricSelect = document.getElementById('live-filter-metric');
    if (liveStationSelect && liveMetricSelect) {
      const handler = () => loadLiveSection();
      liveStationSelect.addEventListener('change', handler);
      liveMetricSelect.addEventListener('change', handler);
    }

    // Historical Analytics Search Form
    const histForm = document.getElementById('historical-filter-form');
    if (histForm) {
      histForm.addEventListener('submit', (e) => {
        e.preventDefault();
        loadHistoricalAnalytics();
      });
    }

    // Historical Quick Preset Buttons
    document.querySelectorAll('.btn-hist-preset').forEach(btn => {
      btn.addEventListener('click', function () {
        const hours = parseInt(this.getAttribute('data-hours'), 10);
        applyDatePreset(hours);
        loadHistoricalAnalytics();
      });
    });

    // Alert Filter Dropdowns
    const alertStation = document.getElementById('alert-filter-station');
    const alertSev = document.getElementById('alert-filter-severity');
    const alertAck = document.getElementById('alert-filter-ack');
    if (alertStation && alertSev && alertAck) {
      const filterHandler = () => {
        AlertManager.filterAlerts({
          station_id: alertStation.value,
          severity: alertSev.value,
          acknowledged: alertAck.value
        });
      };
      alertStation.addEventListener('change', filterHandler);
      alertSev.addEventListener('change', filterHandler);
      alertAck.addEventListener('change', filterHandler);
    }

    // Acknowledge Alert Modal Confirm Button
    const confirmAckBtn = document.getElementById('btn-confirm-ack');
    if (confirmAckBtn) {
      confirmAckBtn.addEventListener('click', () => {
        const note = document.getElementById('ack-note-input')?.value || '';
        AlertManager.submitAcknowledgement(note);
      });
    }

    // Simulator Controls
    const startSimBtn = document.getElementById('btn-start-sim');
    const stopSimBtn = document.getElementById('btn-stop-sim');
    const injectBtn = document.getElementById('btn-inject-anomaly');

    if (startSimBtn) {
      startSimBtn.addEventListener('click', () => {
        const interval = document.getElementById('sim-interval-select')?.value || 5.0;
        SimulatorManager.startSimulator(interval);
      });
    }

    if (stopSimBtn) {
      stopSimBtn.addEventListener('click', () => {
        SimulatorManager.stopSimulator();
      });
    }

    if (injectBtn) {
      injectBtn.addEventListener('click', () => {
        const stId = document.getElementById('anomaly-station-select')?.value;
        const anomType = document.getElementById('anomaly-type-select')?.value;
        const duration = document.getElementById('anomaly-duration-select')?.value;
        if (stId && anomType) {
          SimulatorManager.injectAnomaly(stId, anomType, duration);
        }
      });
    }
  }

  function applyDatePreset(hoursBack) {
    const end = new Date();
    const start = new Date(end.getTime() - hoursBack * 60 * 60 * 1000);

    const startInput = document.getElementById('hist-start-date');
    const endInput = document.getElementById('hist-end-date');

    if (startInput && endInput) {
      // Local ISO formatting YYYY-MM-DDTHH:mm
      const toLocalISO = (d) => {
        const tzOffset = d.getTimezoneOffset() * 60000;
        return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
      };
      startInput.value = toLocalISO(start);
      endInput.value = toLocalISO(end);
    }
  }

  // ---------------------------------------------------------------------------
  // Master Data Refresh Loop
  // ---------------------------------------------------------------------------
  async function refreshAllData(isBackground = false) {
    if (isRefreshing) return;
    isRefreshing = true;

    const refreshIcon = document.querySelector('#btn-manual-refresh i');
    if (refreshIcon) refreshIcon.classList.add('spin-animation');

    try {
      // 1. Check System & HBase Health
      await updateSystemHealth();

      // 2. Fetch Station Metadata & Live Telemetry
      const stationsRes = await ApiService.getStations();
      if (stationsRes.success) {
        stationsCache = stationsRes.data.stations || [];
        updateOverviewKPIs(stationsCache);
        renderOverviewStationCards(stationsCache);
        MapManager.updateMarkers(stationsCache);
        renderStationManagementCards(stationsCache);
      }

      // 3. Check Simulator Status
      await SimulatorManager.checkStatus();

      // 4. Update Current Active Section
      await loadSectionData(activeSection);

      lastRefreshTime = new Date();
      updateLastRefreshUI();
    } catch (err) {
      console.error('Error during master refresh:', err);
    } finally {
      isRefreshing = false;
      if (refreshIcon) refreshIcon.classList.remove('spin-animation');
    }
  }

  function updateLastRefreshUI() {
    const el = document.getElementById('last-refresh-time');
    if (el && lastRefreshTime) {
      el.textContent = lastRefreshTime.toLocaleTimeString([], { hour12: false });
    }
  }

  async function updateSystemHealth() {
    const res = await ApiService.getHealth();
    const pill = document.getElementById('header-hbase-status');
    const sysHealthContainer = document.getElementById('system-health-content');

    if (res.success && res.data.hbase_connected) {
      if (pill) {
        pill.innerHTML = `<span class="badge-status badge-active"><i class="bi bi-database-check"></i> HBase Operational</span>`;
      }
      if (sysHealthContainer) {
        renderSystemHealth(res.data);
      }
    } else {
      if (pill) {
        pill.innerHTML = `<span class="badge-status badge-critical"><i class="bi bi-database-slash"></i> HBase Degraded</span>`;
      }
      if (sysHealthContainer) {
        sysHealthContainer.innerHTML = `
          <div class="alert alert-danger">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            <strong>HBase Connection Warning:</strong> Stargate REST gateway at port 8085 is unreachable or tables are degraded.
          </div>
        `;
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Section Loaders
  // ---------------------------------------------------------------------------
  async function loadSectionData(sectionId) {
    switch (sectionId) {
      case 'overview':
        await loadOverviewSection();
        break;
      case 'live':
        await loadLiveSection();
        break;
      case 'analytics':
        await loadHistoricalAnalytics();
        break;
      case 'air-quality':
        await loadAirQualitySection();
        break;
      case 'heat-risk':
        await loadHeatRiskSection();
        break;
      case 'alerts':
        await AlertManager.loadAlerts();
        break;
      case 'stations':
        // Populated during stations fetch
        break;
      case 'system':
        await updateSystemHealth();
        break;
    }
  }

  // ---------------------------------------------------------------------------
  // 1. Overview Section
  // ---------------------------------------------------------------------------
  async function loadOverviewSection() {
    MapManager.initMap();

    // Latest readings for overview chart
    const telRes = await ApiService.getLatestTelemetry({ limit: 40 });
    if (telRes.success && telRes.data.readings) {
      ChartManager.renderOverviewChart('overview-trend-chart', telRes.data.readings);
    }

    // Load recent alerts preview
    const alertsRes = await ApiService.getAlerts({ limit: 5 });
    const alertsPreview = document.getElementById('overview-alerts-preview');
    if (alertsPreview && alertsRes.success) {
      const alerts = alertsRes.data.alerts || [];
      if (alerts.length === 0) {
        alertsPreview.innerHTML = '<div class="text-muted text-center py-3"><i class="bi bi-check2 text-success me-1"></i> No active alerts.</div>';
      } else {
        alertsPreview.innerHTML = alerts.map(a => `
          <div class="d-flex align-items-center justify-content-between p-2 mb-2 rounded" style="background-color: var(--bg-surface); border: 1px solid var(--border-color);">
            <div>
              <strong class="text-light">${a.station_id}</strong>
              <span class="ms-2 font-mono small">${a.type}</span>
              <div class="text-muted small">${a.message}</div>
            </div>
            <div class="text-end">
              ${AlertManager.getSeverityBadge(a.severity)}
              <div class="font-mono text-muted small mt-1">${AlertManager.formatTime(a.timestamp)}</div>
            </div>
          </div>
        `).join('');
      }
    }
  }

  function updateOverviewKPIs(stations) {
    const total = stations.length;
    const online = stations.filter(s => s.connectivity === 'ACTIVE').length;
    const critical = stations.filter(s => s.connectivity === 'ERROR' || (s.heat_index && s.heat_index >= 44.0)).length;

    const validTemps = stations.map(s => s.temperature).filter(v => v !== null && v !== undefined);
    const avgTemp = validTemps.length ? (validTemps.reduce((a, b) => a + b, 0) / validTemps.length).toFixed(1) : 'N/A';

    const validHums = stations.map(s => s.humidity).filter(v => v !== null && v !== undefined);
    const avgHum = validHums.length ? (validHums.reduce((a, b) => a + b, 0) / validHums.length).toFixed(1) : 'N/A';

    const validPM25 = stations.map(s => s.pm25).filter(v => v !== null && v !== undefined);
    const avgPM25 = validPM25.length ? (validPM25.reduce((a, b) => a + b, 0) / validPM25.length).toFixed(1) : 'N/A';

    const setKpi = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setKpi('kpi-total-stations', total);
    setKpi('kpi-online-stations', online);
    setKpi('kpi-critical-stations', critical);
    setKpi('kpi-avg-temp', avgTemp !== 'N/A' ? `${avgTemp}°C` : 'N/A');
    setKpi('kpi-avg-humidity', avgHum !== 'N/A' ? `${avgHum}%` : 'N/A');
    setKpi('kpi-avg-pm25', avgPM25 !== 'N/A' ? `${avgPM25} µg` : 'N/A');
  }

  function renderOverviewStationCards(stations) {
    const container = document.getElementById('overview-stations-grid');
    if (!container) return;

    container.innerHTML = stations.map(s => {
      const conn = (s.connectivity || 'ACTIVE').toUpperCase();
      const badgeCls = conn === 'ACTIVE' ? 'badge-active' : (conn === 'OFFLINE' ? 'badge-offline' : 'badge-critical');
      const hiDisplay = s.heat_index !== null && s.heat_index !== undefined ? `${s.heat_index} °C` : '<span class="text-muted">N/A</span>';

      return `
        <div class="station-card" onclick="App.showStationModal('${s.station_id}')">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <div>
              <strong class="text-cyan fs-6">${s.station_id}</strong>
              <div class="fw-semibold text-light">${s.station_name}</div>
              <div class="text-muted small">${s.zone}</div>
            </div>
            <span class="badge-status ${badgeCls}">${conn}</span>
          </div>
          <div class="station-metrics-grid">
            <div class="metric-pill">
              <div class="metric-pill-label">Temp</div>
              <div class="metric-pill-value">${s.temperature !== null ? `${s.temperature}°C` : 'N/A'}</div>
            </div>
            <div class="metric-pill">
              <div class="metric-pill-label">Humidity</div>
              <div class="metric-pill-value">${s.humidity !== null ? `${s.humidity}%` : 'N/A'}</div>
            </div>
            <div class="metric-pill">
              <div class="metric-pill-label">Heat Index</div>
              <div class="metric-pill-value text-amber">${hiDisplay}</div>
            </div>
            <div class="metric-pill">
              <div class="metric-pill-label">PM2.5</div>
              <div class="metric-pill-value text-purple">${s.pm25 !== null ? s.pm25 : 'N/A'}</div>
            </div>
            <div class="metric-pill">
              <div class="metric-pill-label">PM10</div>
              <div class="metric-pill-value text-blue">${s.pm10 !== null ? s.pm10 : 'N/A'}</div>
            </div>
            <div class="metric-pill">
              <div class="metric-pill-label">Pressure</div>
              <div class="metric-pill-value">${s.pressure || '920'} hPa</div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  // ---------------------------------------------------------------------------
  // 2. Live Monitoring Section
  // ---------------------------------------------------------------------------
  async function loadLiveSection() {
    const stationId = document.getElementById('live-filter-station')?.value || '';
    const metric = document.getElementById('live-filter-metric')?.value || 'temperature';

    const params = { limit: 50 };
    if (stationId && stationId !== 'ALL') {
      params.station_id = stationId;
    }

    const res = await ApiService.getLatestTelemetry(params);
    if (!res.success) {
      console.warn('Failed to fetch live telemetry:', res.error);
      return;
    }

    const readings = res.data.readings || [];
    ChartManager.renderLiveMetricsChart('live-metrics-chart', readings, metric);

    // Stream table
    const tableBody = document.getElementById('live-telemetry-table-body');
    if (tableBody) {
      if (readings.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">No live telemetry available.</td></tr>';
      } else {
        tableBody.innerHTML = readings.slice(0, 15).map(r => `
          <tr>
            <td><strong class="text-light">${r.station_id}</strong></td>
            <td><span class="font-mono" style="font-size: 0.8rem;">${AlertManager.formatTime(r.timestamp)}</span></td>
            <td><span class="font-mono text-amber">${r.temperature_celsius !== null ? `${r.temperature_celsius} °C` : 'N/A'}</span></td>
            <td><span class="font-mono text-cyan">${r.humidity_percent !== null ? `${r.humidity_percent} %` : 'N/A'}</span></td>
            <td><span class="font-mono text-danger">${r.heat_index_celsius !== null ? `${r.heat_index_celsius} °C` : '<span class="text-muted">N/A</span>'}</span></td>
            <td><span class="font-mono text-purple">${r.pm25 !== null ? r.pm25 : 'N/A'}</span></td>
            <td><span class="font-mono text-blue">${r.pm10 !== null ? r.pm10 : 'N/A'}</span></td>
            <td><span class="badge-status ${r.sensor_status === 'ACTIVE' ? 'badge-active' : 'badge-warning'}">${r.sensor_status}</span></td>
          </tr>
        `).join('');
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 3. Historical Analytics Section
  // ---------------------------------------------------------------------------
  async function loadHistoricalAnalytics() {
    const stationId = document.getElementById('hist-filter-station')?.value || 'ST001';
    const metric = document.getElementById('hist-filter-measurement')?.value || 'temperature';
    const limit = document.getElementById('hist-filter-limit')?.value || '50';
    const order = document.getElementById('hist-filter-order')?.value || 'desc';

    const startVal = document.getElementById('hist-start-date')?.value;
    const endVal = document.getElementById('hist-end-date')?.value;

    const params = {
      limit: parseInt(limit, 10),
      order: order
    };

    if (metric && metric !== 'all') {
      params.measurement = metric;
    }
    if (startVal) {
      params.start = new Date(startVal).toISOString();
    }
    if (endVal) {
      params.end = new Date(endVal).toISOString();
    }

    const tableBody = document.getElementById('hist-table-body');
    if (tableBody) {
      tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4"><div class="loading-spinner"></div><div>Loading historical HBase partitions...</div></td></tr>';
    }

    const res = await ApiService.getStationTelemetry(stationId, params);
    if (!res.success) {
      if (tableBody) {
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger py-4"><i class="bi bi-exclamation-triangle"></i> ${res.error}</td></tr>`;
      }
      return;
    }

    const readings = res.data.readings || [];

    // Chart key mapping
    const metricKeyMap = {
      'temperature': 'temperature_celsius',
      'humidity': 'humidity_percent',
      'heat_index': 'heat_index_celsius',
      'pm25': 'pm25',
      'pm10': 'pm10',
      'pressure': 'atmospheric_pressure_hpa'
    };
    const key = metricKeyMap[metric] || 'temperature_celsius';
    ChartManager.renderHistoricalChart('historical-trend-chart', readings, key, metric.toUpperCase());

    // Analytics summary metrics
    const validVals = readings.map(r => r[key]).filter(v => v !== null && v !== undefined);
    if (validVals.length) {
      const min = Math.min(...validVals).toFixed(2);
      const max = Math.max(...validVals).toFixed(2);
      const avg = (validVals.reduce((a, b) => a + b, 0) / validVals.length).toFixed(2);
      document.getElementById('hist-stat-min').textContent = min;
      document.getElementById('hist-stat-max').textContent = max;
      document.getElementById('hist-stat-avg').textContent = avg;
      document.getElementById('hist-stat-count').textContent = validVals.length;
    } else {
      ['hist-stat-min', 'hist-stat-max', 'hist-stat-avg', 'hist-stat-count'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = 'N/A';
      });
    }

    // Historical Table
    if (tableBody) {
      if (readings.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No historical records in requested window.</td></tr>';
      } else {
        tableBody.innerHTML = readings.map(r => `
          <tr>
            <td><span class="font-mono small text-cyan">${r.row_key || r.station_id}</span></td>
            <td><span class="font-mono small">${AlertManager.formatTime(r.timestamp)}</span></td>
            <td><span class="font-mono">${r.temperature_celsius !== null ? `${r.temperature_celsius}°C` : 'N/A'}</span></td>
            <td><span class="font-mono">${r.humidity_percent !== null ? `${r.humidity_percent}%` : 'N/A'}</span></td>
            <td><span class="font-mono text-danger">${r.heat_index_celsius !== null ? `${r.heat_index_celsius}°C` : 'N/A'}</span></td>
            <td><span class="font-mono text-purple">${r.pm25 !== null ? r.pm25 : 'N/A'}</span></td>
            <td><span class="font-mono text-blue">${r.pm10 !== null ? r.pm10 : 'N/A'}</span></td>
          </tr>
        `).join('');
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 4. Air Quality Section
  // ---------------------------------------------------------------------------
  async function loadAirQualitySection() {
    const compRes = await ApiService.getStationComparison();
    if (!compRes.success) return;

    const comparison = (compRes.data && Array.isArray(compRes.data.rankings))
      ? compRes.data.rankings
      : (Array.isArray(compRes.data) ? compRes.data : []);
    ChartManager.renderAirQualityChart('air-quality-bar-chart', comparison);

    const tableBody = document.getElementById('aq-comparison-table-body');
    if (tableBody) {
      tableBody.innerHTML = comparison.map(s => {
        // India NAQI category assessment
        let aqiCat = 'UNKNOWN';
        let aqiBadge = 'bg-secondary';
        const p25 = s.pm25 || 0;
        const p10 = s.pm10 || 0;

        if (p25 <= 30 && p10 <= 50) { aqiCat = 'GOOD'; aqiBadge = 'bg-success'; }
        else if (p25 <= 60 && p10 <= 100) { aqiCat = 'SATISFACTORY'; aqiBadge = 'bg-info text-dark'; }
        else if (p25 <= 90 && p10 <= 250) { aqiCat = 'MODERATE'; aqiBadge = 'bg-warning text-dark'; }
        else if (p25 <= 120 && p10 <= 350) { aqiCat = 'POOR'; aqiBadge = 'bg-danger'; }
        else if (p25 <= 250 && p10 <= 430) { aqiCat = 'VERY POOR'; aqiBadge = 'bg-danger'; }
        else if (p25 > 250 || p10 > 430) { aqiCat = 'SEVERE'; aqiBadge = 'bg-dark border border-danger'; }

        return `
          <tr>
            <td><strong class="text-light">${s.station_id}</strong> - ${s.station_name}</td>
            <td><span class="text-muted small">${s.zone}</span></td>
            <td><span class="font-mono text-purple fw-bold">${s.pm25 !== null ? `${s.pm25} µg/m³` : 'N/A'}</span></td>
            <td><span class="font-mono text-blue fw-bold">${s.pm10 !== null ? `${s.pm10} µg/m³` : 'N/A'}</span></td>
            <td><span class="badge ${aqiBadge}">${aqiCat}</span></td>
            <td><span class="badge-status ${s.connectivity === 'ACTIVE' ? 'badge-active' : 'badge-warning'}">${s.connectivity}</span></td>
          </tr>
        `;
      }).join('');
    }
  }

  // ---------------------------------------------------------------------------
  // 5. Heat Risk Section
  // ---------------------------------------------------------------------------
  async function loadHeatRiskSection() {
    const compRes = await ApiService.getStationComparison();
    if (!compRes.success) return;

    const comparison = (compRes.data && Array.isArray(compRes.data.rankings))
      ? compRes.data.rankings
      : (Array.isArray(compRes.data) ? compRes.data : []);
    ChartManager.renderHeatRiskComparisonChart('heat-risk-comparison-chart', comparison);

    const tableBody = document.getElementById('heat-risk-table-body');
    if (tableBody) {
      tableBody.innerHTML = comparison.map(s => {
        const hi = s.heat_index;
        let riskBadge = 'badge-active';
        let riskLabel = 'NORMAL (< 32°C)';

        if (hi === null || hi === undefined) {
          riskBadge = 'badge-offline';
          riskLabel = 'NOT APPLICABLE / N/A';
        } else if (hi >= 44.0) {
          riskBadge = 'badge-critical';
          riskLabel = 'EXTREME DANGER (≥ 44°C)';
        } else if (hi >= 38.0) {
          riskBadge = 'badge-warning';
          riskLabel = 'DANGER / WARNING (38–44°C)';
        } else if (hi >= 32.0) {
          riskBadge = 'badge-warning';
          riskLabel = 'CAUTION (32–38°C)';
        }

        return `
          <tr>
            <td><strong class="text-light">${s.station_id}</strong> - ${s.station_name}</td>
            <td><span class="font-mono text-amber">${s.temperature !== null ? `${s.temperature} °C` : 'N/A'}</span></td>
            <td><span class="font-mono text-cyan">${s.humidity !== null ? `${s.humidity} %` : 'N/A'}</span></td>
            <td><span class="font-mono text-danger fw-bold">${hi !== null && hi !== undefined ? `${hi} °C` : '<span class="text-muted">N/A</span>'}</span></td>
            <td><span class="badge-status ${riskBadge}">${riskLabel}</span></td>
            <td><span class="badge bg-secondary font-mono">${s.active_unacknowledged_alerts}</span></td>
          </tr>
        `;
      }).join('');
    }
  }

  // ---------------------------------------------------------------------------
  // 6. Station Management & Deep Dive Modal
  // ---------------------------------------------------------------------------
  function renderStationManagementCards(stations) {
    const container = document.getElementById('stations-cards-container');
    if (!container) return;

    container.innerHTML = stations.map(s => `
      <div class="col-md-6 col-lg-4 mb-3">
        <div class="card-custom h-100">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <strong class="text-cyan fs-5">${s.station_id}</strong>
            <span class="badge-status ${s.connectivity === 'ACTIVE' ? 'badge-active' : 'badge-warning'}">${s.connectivity || 'ACTIVE'}</span>
          </div>
          <h6 class="text-light fw-bold">${s.station_name}</h6>
          <div class="text-muted small mb-3"><i class="bi bi-geo-alt"></i> ${s.zone}</div>
          <div class="p-2 mb-3 rounded" style="background-color: var(--bg-surface); font-size: 0.8rem;">
            <div><strong>Coordinates:</strong> <span class="font-mono text-cyan">${s.coordinates ? `${s.coordinates.latitude}, ${s.coordinates.longitude}` : '12.97, 77.59'}</span></div>
            <div><strong>Data Source:</strong> <span class="badge-simulated ms-1">SIMULATED</span></div>
            <div><strong>Last Contact:</strong> <span class="font-mono">${s.last_reading_time ? AlertManager.formatTime(s.last_reading_time) : 'Active'}</span></div>
          </div>
          <div class="d-flex justify-content-between">
            <button class="btn btn-sm btn-outline-custom w-100" onclick="App.showStationModal('${s.station_id}')">
              <i class="bi bi-search me-1"></i> Station Deep-Dive
            </button>
          </div>
        </div>
      </div>
    `).join('');
  }

  async function showStationModal(stationId) {
    const res = await ApiService.getStation(stationId);
    if (!res.success) {
      alert(`Could not load details for station ${stationId}`);
      return;
    }

    const data = res.data;
    const bodyEl = document.getElementById('station-detail-modal-body');
    const titleEl = document.getElementById('station-modal-title');

    if (titleEl) titleEl.textContent = `${data.station_id} — ${data.station_name}`;

    if (bodyEl) {
      const r = data.latest_reading || {};
      bodyEl.innerHTML = `
        <div class="row g-3">
          <div class="col-md-6">
            <div class="card-custom p-3">
              <h6 class="text-cyan"><i class="bi bi-info-circle me-1"></i> Station Attributes</h6>
              <ul class="list-unstyled small mb-0 mt-2">
                <li><strong>Zone:</strong> ${data.zone}</li>
                <li><strong>Coordinates:</strong> ${data.coordinates.latitude}, ${data.coordinates.longitude}</li>
                <li><strong>Status:</strong> <span class="badge-status badge-active">${data.status.connectivity}</span></li>
                <li><strong>Last Update:</strong> ${AlertManager.formatTime(data.status.last_reading_time)}</li>
              </ul>
            </div>
          </div>
          <div class="col-md-6">
            <div class="card-custom p-3">
              <h6 class="text-cyan"><i class="bi bi-speedometer2 me-1"></i> Latest Reading</h6>
              <div class="station-metrics-grid mt-2">
                <div class="metric-pill">
                  <div class="metric-pill-label">Temp</div>
                  <div class="metric-pill-value">${r.temperature_celsius !== undefined ? `${r.temperature_celsius}°C` : 'N/A'}</div>
                </div>
                <div class="metric-pill">
                  <div class="metric-pill-label">Humidity</div>
                  <div class="metric-pill-value">${r.humidity_percent !== undefined ? `${r.humidity_percent}%` : 'N/A'}</div>
                </div>
                <div class="metric-pill">
                  <div class="metric-pill-label">Heat Index</div>
                  <div class="metric-pill-value text-amber">${r.heat_index_celsius !== undefined && r.heat_index_celsius !== null ? `${r.heat_index_celsius}°C` : 'N/A'}</div>
                </div>
                <div class="metric-pill">
                  <div class="metric-pill-label">PM2.5</div>
                  <div class="metric-pill-value text-purple">${r.pm25 !== undefined ? r.pm25 : 'N/A'}</div>
                </div>
                <div class="metric-pill">
                  <div class="metric-pill-label">PM10</div>
                  <div class="metric-pill-value text-blue">${r.pm10 !== undefined ? r.pm10 : 'N/A'}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
    }

    const modalEl = document.getElementById('stationDetailModal');
    if (modalEl && typeof bootstrap !== 'undefined') {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  }

  // ---------------------------------------------------------------------------
  // 7. System Status Section
  // ---------------------------------------------------------------------------
  function renderSystemHealth(healthData) {
    const el = document.getElementById('system-health-content');
    if (!el) return;

    const tables = healthData.tables || {};
    el.innerHTML = `
      <div class="row g-3">
        <div class="col-md-4">
          <div class="card-custom">
            <div class="text-muted small">Flask Application</div>
            <div class="fs-4 fw-bold text-success font-mono">UP (v1.0.0)</div>
            <div class="small text-muted mt-1">Python 3.14.6 REST Engine</div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card-custom">
            <div class="text-muted small">Apache HBase Datastore</div>
            <div class="fs-4 fw-bold text-cyan font-mono">${healthData.hbase_version || '2.6.7-hadoop3'}</div>
            <div class="small text-muted mt-1">Stargate REST Gateway :8085</div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card-custom">
            <div class="text-muted small">Sensor Simulator</div>
            <div class="fs-4 fw-bold text-amber font-mono">${healthData.simulator_running ? 'RUNNING' : 'IDLE'}</div>
            <div class="small text-muted mt-1">5 Virtual Bengaluru Stations</div>
          </div>
        </div>
      </div>

      <div class="card-custom mt-3">
        <h6 class="text-light mb-3"><i class="bi bi-table me-2 text-cyan"></i> Apache HBase Managed Tables</h6>
        <div class="table-responsive-custom">
          <table class="table-custom">
            <thead>
              <tr>
                <th>Namespace & Table Name</th>
                <th>Status</th>
                <th>Storage Schema</th>
                <th>Primary Column Families</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong class="text-cyan font-mono">microclimate:readings</strong></td>
                <td><span class="badge-status ${tables['microclimate:readings'] ? 'badge-active' : 'badge-critical'}">${tables['microclimate:readings'] ? 'ONLINE' : 'DEGRADED'}</span></td>
                <td><span class="font-mono small">STATION#YYYYMMDD#REVERSE_TS_MS</span></td>
                <td><span class="badge bg-secondary">metrics</span> <span class="badge bg-secondary">metadata</span></td>
              </tr>
              <tr>
                <td><strong class="text-cyan font-mono">microclimate:alerts</strong></td>
                <td><span class="badge-status ${tables['microclimate:alerts'] ? 'badge-active' : 'badge-critical'}">${tables['microclimate:alerts'] ? 'ONLINE' : 'DEGRADED'}</span></td>
                <td><span class="font-mono small">STATION#REVERSE_TS_MS#ALERT_TYPE</span></td>
                <td><span class="badge bg-secondary">alert</span> <span class="badge bg-secondary">metadata</span></td>
              </tr>
              <tr>
                <td><strong class="text-cyan font-mono">microclimate:station_status</strong></td>
                <td><span class="badge-status ${tables['microclimate:station_status'] ? 'badge-active' : 'badge-critical'}">${tables['microclimate:station_status'] ? 'ONLINE' : 'DEGRADED'}</span></td>
                <td><span class="font-mono small">STATION</span></td>
                <td><span class="badge bg-secondary">status</span> <span class="badge bg-secondary">metadata</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // Expose public methods
  return {
    showStationModal,
    refreshAllData,
    switchSection
  };
})();
