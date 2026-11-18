/**
 * Simulator Control Module for Urban Microclimate & Heat-Risk Intelligence System.
 * Manages simulator state, starting, stopping, and controlled anomaly injections.
 */
const SimulatorManager = (function () {
  let isProcessing = false;

  async function checkStatus() {
    const res = await ApiService.getSimulatorStatus();
    if (!res.success) {
      updateUIStatus(false, 'UNKNOWN');
      return null;
    }

    const data = res.data;
    updateUIStatus(data.running, data.execution_mode, data);
    return data;
  }

  function updateUIStatus(isRunning, mode, details = {}) {
    // Header status pill
    const headerPill = document.getElementById('header-sim-status');
    if (headerPill) {
      if (isRunning) {
        headerPill.innerHTML = '<span class="badge-status badge-active"><i class="bi bi-play-circle-fill"></i> Simulator Active</span>';
      } else {
        headerPill.innerHTML = '<span class="badge-status badge-offline"><i class="bi bi-stop-circle-fill"></i> Simulator Idle</span>';
      }
    }

    // Simulator panel widgets
    const statusTextEl = document.getElementById('sim-status-text');
    if (statusTextEl) {
      statusTextEl.textContent = isRunning ? 'RUNNING' : 'STOPPED';
      statusTextEl.className = isRunning ? 'badge bg-success font-mono' : 'badge bg-secondary font-mono';
    }

    const modeTextEl = document.getElementById('sim-mode-text');
    if (modeTextEl) modeTextEl.textContent = mode || 'N/A';

    const intervalEl = document.getElementById('sim-interval-text');
    if (intervalEl) intervalEl.textContent = (details.interval_seconds || 5.0) + 's';

    const countEl = document.getElementById('sim-readings-count');
    if (countEl && details.readings_generated !== undefined) {
      countEl.textContent = details.readings_generated;
    }

    // Toggle start/stop button states
    const startBtn = document.getElementById('btn-start-sim');
    const stopBtn = document.getElementById('btn-stop-sim');
    if (startBtn && stopBtn) {
      startBtn.disabled = isRunning;
      stopBtn.disabled = !isRunning;
    }
  }

  async function startSimulator(interval = 5.0) {
    if (isProcessing) return;
    isProcessing = true;
    showFeedback('Starting sensor simulation threads...', 'info');

    const res = await ApiService.controlSimulator({
      action: 'start',
      interval_seconds: parseFloat(interval) || 5.0
    });

    isProcessing = false;
    if (res.success) {
      showFeedback('Simulator started successfully! Ingesting telemetry into HBase.', 'success');
      await checkStatus();
    } else {
      showFeedback(`Failed to start simulator: ${res.error}`, 'danger');
    }
  }

  async function stopSimulator() {
    if (isProcessing) return;
    if (!confirm('Are you sure you want to stop the sensor simulator threads? Live telemetry ingestion will pause.')) {
      return;
    }

    isProcessing = true;
    showFeedback('Stopping sensor simulation...', 'info');

    const res = await ApiService.controlSimulator({ action: 'stop' });
    isProcessing = false;

    if (res.success) {
      showFeedback('Simulator stopped. Background workers shut down.', 'warning');
      await checkStatus();
    } else {
      showFeedback(`Failed to stop simulator: ${res.error}`, 'danger');
    }
  }

  async function injectAnomaly(stationId, anomalyType, durationTicks = 3) {
    if (isProcessing) return;
    isProcessing = true;
    showFeedback(`Injecting '${anomalyType}' anomaly on ${stationId}...`, 'info');

    const res = await ApiService.controlSimulator({
      action: 'inject_anomaly',
      station_id: stationId,
      anomaly_type: anomalyType,
      duration_ticks: parseInt(durationTicks, 10) || 3
    });

    isProcessing = false;
    if (res.success) {
      showFeedback(`Anomaly '${anomalyType}' successfully scheduled on ${stationId} for ${durationTicks} cycles.`, 'success');
    } else {
      showFeedback(`Anomaly injection failed: ${res.error}`, 'danger');
    }
  }

  function showFeedback(message, type = 'info') {
    const feedbackEl = document.getElementById('sim-feedback-msg');
    if (!feedbackEl) return;

    feedbackEl.className = `alert alert-${type} py-2 px-3 small`;
    feedbackEl.innerHTML = `<i class="bi bi-info-circle me-1"></i> ${message}`;
    feedbackEl.style.display = 'block';

    setTimeout(() => {
      if (feedbackEl) feedbackEl.style.display = 'none';
    }, 6000);
  }

  return {
    checkStatus,
    startSimulator,
    stopSimulator,
    injectAnomaly
  };
})();
