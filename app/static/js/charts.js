/**
 * Chart Manager for Urban Microclimate & Heat-Risk Intelligence System.
 * Encapsulates Chart.js instances, color palettes, responsive configurations,
 * and handles missing data gracefully without plotting zeros.
 */
const ChartManager = (function () {
  const instances = {};

  const COLORS = {
    cyan: '#00d2ff',
    blue: '#3b82f6',
    green: '#10b981',
    amber: '#f59e0b',
    red: '#ef4444',
    purple: '#a855f7',
    grid: '#1e3152',
    text: '#94a3b8',
    card: '#15223c'
  };

  // Base options for dark command center
  function getBaseOptions(titleText = '', yAxisLabel = '') {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            color: COLORS.text,
            font: { family: 'Inter', size: 12 }
          }
        },
        title: {
          display: !!titleText,
          text: titleText,
          color: '#f8fafc',
          font: { family: 'Inter', size: 14, weight: '600' },
          padding: { bottom: 15 }
        },
        tooltip: {
          backgroundColor: COLORS.card,
          borderColor: COLORS.grid,
          borderWidth: 1,
          titleColor: '#f8fafc',
          bodyColor: '#e2e8f0',
          titleFont: { family: 'Inter', weight: '600' },
          bodyFont: { family: 'SF Mono' },
          padding: 10
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(30, 49, 82, 0.4)' },
          ticks: { color: COLORS.text, font: { family: 'Inter', size: 11 }, maxRotation: 45 }
        },
        y: {
          grid: { color: 'rgba(30, 49, 82, 0.6)' },
          ticks: { color: COLORS.text, font: { family: 'SF Mono', size: 11 } },
          title: {
            display: !!yAxisLabel,
            text: yAxisLabel,
            color: COLORS.text,
            font: { family: 'Inter', size: 12 }
          }
        }
      }
    };
  }

  function destroyChart(canvasId) {
    if (instances[canvasId]) {
      instances[canvasId].destroy();
      delete instances[canvasId];
    }
  }

  return {
    // 1. Overview Live Telemetry Chart
    renderOverviewChart(canvasId, readings = []) {
      const canvas = document.getElementById(canvasId);
      if (!canvas || typeof Chart === 'undefined') return;
      destroyChart(canvasId);

      // Sort chronological
      const sorted = [...readings].sort((a, b) => a.timestamp_ms - b.timestamp_ms);
      const labels = sorted.map(r => {
        const d = new Date(r.timestamp_ms);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      });

      const temps = sorted.map(r => r.temperature_celsius);
      const hums = sorted.map(r => r.humidity_percent);
      const pm25s = sorted.map(r => r.pm25);

      const ctx = canvas.getContext('2d');
      instances[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Temperature (°C)',
              data: temps,
              borderColor: COLORS.amber,
              backgroundColor: 'rgba(245, 158, 11, 0.1)',
              borderWidth: 2,
              tension: 0.3,
              spanGaps: false,
              pointRadius: 2
            },
            {
              label: 'Humidity (%)',
              data: hums,
              borderColor: COLORS.cyan,
              backgroundColor: 'rgba(0, 210, 255, 0.1)',
              borderWidth: 2,
              tension: 0.3,
              spanGaps: false,
              pointRadius: 2
            },
            {
              label: 'PM2.5 (µg/m³)',
              data: pm25s,
              borderColor: COLORS.purple,
              backgroundColor: 'rgba(168, 85, 247, 0.1)',
              borderWidth: 2,
              tension: 0.3,
              spanGaps: false,
              pointRadius: 2
            }
          ]
        },
        options: getBaseOptions('Citywide Real-time Environmental Trends', 'Measurement Units')
      });
    },

    // 2. Live Monitoring Section Multi-Metric Time Series
    renderLiveMetricsChart(canvasId, readings = [], measurement = 'temperature') {
      const canvas = document.getElementById(canvasId);
      if (!canvas || typeof Chart === 'undefined') return;
      destroyChart(canvasId);

      const sorted = [...readings].sort((a, b) => a.timestamp_ms - b.timestamp_ms);
      const labels = sorted.map(r => {
        const d = new Date(r.timestamp_ms);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      });

      let datasetConfig = {};
      let yLabel = '';

      switch (measurement) {
        case 'temperature':
          datasetConfig = {
            label: 'Ambient Air Temperature (°C)',
            data: sorted.map(r => r.temperature_celsius),
            borderColor: COLORS.amber,
            backgroundColor: 'rgba(245, 158, 11, 0.15)'
          };
          yLabel = 'Temperature (°C)';
          break;
        case 'humidity':
          datasetConfig = {
            label: 'Relative Humidity (%)',
            data: sorted.map(r => r.humidity_percent),
            borderColor: COLORS.cyan,
            backgroundColor: 'rgba(0, 210, 255, 0.15)'
          };
          yLabel = 'Relative Humidity (%)';
          break;
        case 'heat_index':
          datasetConfig = {
            label: 'NOAA Heat Index / Apparent Temp (°C)',
            data: sorted.map(r => r.heat_index_celsius),
            borderColor: COLORS.red,
            backgroundColor: 'rgba(239, 68, 68, 0.15)'
          };
          yLabel = 'Apparent Temp (°C)';
          break;
        case 'pm25':
          datasetConfig = {
            label: 'PM2.5 Fine Particulates (µg/m³)',
            data: sorted.map(r => r.pm25),
            borderColor: COLORS.purple,
            backgroundColor: 'rgba(168, 85, 247, 0.15)'
          };
          yLabel = 'PM2.5 (µg/m³)';
          break;
        case 'pm10':
          datasetConfig = {
            label: 'PM10 Coarse Particulates (µg/m³)',
            data: sorted.map(r => r.pm10),
            borderColor: COLORS.blue,
            backgroundColor: 'rgba(59, 130, 246, 0.15)'
          };
          yLabel = 'PM10 (µg/m³)';
          break;
        default:
          datasetConfig = {
            label: 'Sensor Reading',
            data: sorted.map(r => r.temperature_celsius),
            borderColor: COLORS.green,
            backgroundColor: 'rgba(16, 185, 129, 0.15)'
          };
          yLabel = 'Value';
      }

      const ctx = canvas.getContext('2d');
      instances[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            ...datasetConfig,
            borderWidth: 2,
            tension: 0.25,
            fill: true,
            spanGaps: false,
            pointRadius: 3,
            pointHoverRadius: 6
          }]
        },
        options: getBaseOptions(`Live Telemetry: ${datasetConfig.label}`, yLabel)
      });
    },

    // 3. Historical Telemetry Chart
    renderHistoricalChart(canvasId, readings = [], metric = 'temperature_celsius', labelName = 'Temperature (°C)') {
      const canvas = document.getElementById(canvasId);
      if (!canvas || typeof Chart === 'undefined') return;
      destroyChart(canvasId);

      const sorted = [...readings].sort((a, b) => a.timestamp_ms - b.timestamp_ms);
      const labels = sorted.map(r => {
        const d = new Date(r.timestamp_ms);
        return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
               d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      });

      const values = sorted.map(r => r[metric] !== undefined ? r[metric] : null);

      const ctx = canvas.getContext('2d');
      instances[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            label: labelName,
            data: values,
            borderColor: COLORS.cyan,
            backgroundColor: 'rgba(0, 210, 255, 0.08)',
            borderWidth: 2,
            fill: true,
            spanGaps: false,
            pointRadius: sorted.length > 50 ? 1 : 3
          }]
        },
        options: getBaseOptions(`Historical Analytics: ${labelName}`, labelName)
      });
    },

    // 4. Air Quality Station Breakdown Bar Chart
    renderAirQualityChart(canvasId, stationComparison = []) {
      const canvas = document.getElementById(canvasId);
      if (!canvas || typeof Chart === 'undefined') return;
      destroyChart(canvasId);

      const list = (stationComparison && Array.isArray(stationComparison.rankings))
        ? stationComparison.rankings
        : (Array.isArray(stationComparison) ? stationComparison : []);

      const labels = list.map(s => s.station_name || s.station_id);
      const pm25s = list.map(s => s.pm25);
      const pm10s = list.map(s => s.pm10);

      const ctx = canvas.getContext('2d');
      instances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'PM2.5 (Fine Particulates)',
              data: pm25s,
              backgroundColor: 'rgba(168, 85, 247, 0.7)',
              borderColor: COLORS.purple,
              borderWidth: 1,
              borderRadius: 4
            },
            {
              label: 'PM10 (Coarse Particulates)',
              data: pm10s,
              backgroundColor: 'rgba(59, 130, 246, 0.7)',
              borderColor: COLORS.blue,
              borderWidth: 1,
              borderRadius: 4
            }
          ]
        },
        options: getBaseOptions('Comparative Particulate Matter Concentrations (µg/m³)', 'Concentration (µg/m³)')
      });
    },

    // 5. Heat Risk Comparison Chart (Sensible Temp vs Apparent Heat Index)
    renderHeatRiskComparisonChart(canvasId, stationComparison = []) {
      const canvas = document.getElementById(canvasId);
      if (!canvas || typeof Chart === 'undefined') return;
      destroyChart(canvasId);

      const list = (stationComparison && Array.isArray(stationComparison.rankings))
        ? stationComparison.rankings
        : (Array.isArray(stationComparison) ? stationComparison : []);

      const labels = list.map(s => s.station_name || s.station_id);
      const temps = list.map(s => s.temperature);
      const heatIndices = list.map(s => s.heat_index);

      const ctx = canvas.getContext('2d');
      instances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Ambient Dry-Bulb Temperature (°C)',
              data: temps,
              backgroundColor: 'rgba(245, 158, 11, 0.7)',
              borderColor: COLORS.amber,
              borderWidth: 1,
              borderRadius: 4
            },
            {
              label: 'Apparent Heat Index (°C)',
              data: heatIndices,
              backgroundColor: 'rgba(239, 68, 68, 0.7)',
              borderColor: COLORS.red,
              borderWidth: 1,
              borderRadius: 4
            }
          ]
        },
        options: getBaseOptions('Sensible Temperature vs Physiological Heat Index (°C)', 'Temperature (°C)')
      });
    }
  };
})();
