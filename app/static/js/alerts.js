/**
 * Alert Management Module for Urban Microclimate & Heat-Risk Intelligence System.
 * Manages alert querying, filtering, rendering, and HBase acknowledgement persistence.
 */
const AlertManager = (function () {
  let activeAlerts = [];
  let pendingAckAlertId = null;

  function formatTime(isoStr) {
    if (!isoStr) return 'N/A';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
             d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return isoStr;
    }
  }

  function getSeverityBadge(severity) {
    const sev = (severity || 'WARNING').toUpperCase();
    if (sev === 'CRITICAL') {
      return '<span class="badge-status badge-critical"><i class="bi bi-exclamation-octagon-fill"></i> CRITICAL</span>';
    }
    return '<span class="badge-status badge-warning"><i class="bi bi-exclamation-triangle-fill"></i> WARNING</span>';
  }

  function getApplicabilityBadge(applicability) {
    if (!applicability) return '';
    const status = applicability.status || '';

    if (status === 'LEGACY_UNVERIFIED') {
      return `<span class="badge-legacy" title="${applicability.note || 'Legacy unverified record'}"><i class="bi bi-clock-history"></i> LEGACY_UNVERIFIED</span>`;
    }
    if (status === 'UNSUPPORTED_EXTRAPOLATION' || applicability.is_valid === false) {
      return `<span class="badge-status badge-warning" title="${applicability.note || 'Unsupported regression domain'}"><i class="bi bi-shield-exclamation"></i> UNVALIDATED</span>`;
    }
    if (status === 'VALID' || applicability.is_valid === true) {
      return `<span class="badge-status badge-active" title="${applicability.note || 'Verified meteorological domain'}"><i class="bi bi-check2-circle"></i> VERIFIED</span>`;
    }
    return '';
  }

  async function loadAlerts(filters = {}) {
    const container = document.getElementById('alerts-table-body');
    if (!container) return;

    container.innerHTML = '<tr><td colspan="8" class="text-center py-4"><div class="loading-spinner"></div><div>Loading HBase alerts...</div></td></tr>';

    const res = await ApiService.getAlerts(filters);
    if (!res.success) {
      container.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4"><i class="bi bi-exclamation-triangle"></i> Failed to load alerts: ${res.error}</td></tr>`;
      return;
    }

    activeAlerts = res.data.alerts || [];
    renderAlertsTable(activeAlerts);

    // Update unacknowledged alerts counter
    const unackCount = activeAlerts.filter(a => !a.acknowledged).length;
    const badgeEl = document.getElementById('unack-alerts-count');
    if (badgeEl) {
      badgeEl.textContent = unackCount;
      badgeEl.className = unackCount > 0 ? 'badge bg-danger' : 'badge bg-secondary';
    }
  }

  function renderAlertsTable(alerts) {
    const container = document.getElementById('alerts-table-body');
    if (!container) return;

    if (!alerts || alerts.length === 0) {
      container.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4"><i class="bi bi-check-circle fs-3 d-block mb-2 text-success"></i> No alerts found matching criteria.</td></tr>';
      return;
    }

    container.innerHTML = alerts.map(a => {
      const ackBadge = a.acknowledged
        ? `<span class="badge-status badge-active" title="Note: ${a.acknowledgement_note || 'None'}"><i class="bi bi-check-circle"></i> Acknowledged</span>`
        : `<button class="btn btn-sm btn-outline-warning btn-ack" data-id="${a.alert_id}"><i class="bi bi-check2"></i> Acknowledge</button>`;

      const appBadge = getApplicabilityBadge(a.calculation_applicability);

      return `
        <tr>
          <td><span class="font-mono text-cyan" style="font-size: 0.8rem;" title="${a.alert_id}">${a.alert_id.split('#').slice(0, 2).join('#')}</span></td>
          <td><strong class="text-light">${a.station_id}</strong></td>
          <td><span class="font-mono" style="font-size: 0.8rem;">${formatTime(a.timestamp)}</span></td>
          <td>${getSeverityBadge(a.severity)}</td>
          <td><span class="font-mono" style="font-size: 0.8rem;">${a.type}</span></td>
          <td><strong class="text-light font-mono">${a.measurement}</strong> <span class="text-muted" style="font-size: 0.75rem;">(Thresh: ${a.threshold})</span></td>
          <td><div style="max-width: 260px; font-size: 0.8rem;">${a.message}</div></td>
          <td>${appBadge}</td>
          <td>${ackBadge}</td>
        </tr>
      `;
    }).join('');

    // Attach click listeners to acknowledge buttons
    document.querySelectorAll('.btn-ack').forEach(btn => {
      btn.addEventListener('click', function () {
        const id = this.getAttribute('data-id');
        promptAcknowledgeModal(id);
      });
    });
  }

  function promptAcknowledgeModal(alertId) {
    pendingAckAlertId = alertId;
    const targetAlert = activeAlerts.find(a => a.alert_id === alertId);
    
    const infoEl = document.getElementById('ack-alert-details');
    if (infoEl && targetAlert) {
      infoEl.innerHTML = `
        <div class="mb-2"><strong>Station:</strong> ${targetAlert.station_id} | <strong>Type:</strong> ${targetAlert.type}</div>
        <div class="mb-2"><strong>Severity:</strong> ${targetAlert.severity} | <strong>Value:</strong> ${targetAlert.measurement}</div>
        <div class="small text-muted font-mono">${targetAlert.alert_id}</div>
      `;
    }

    const modalEl = document.getElementById('acknowledgeModal');
    if (modalEl && typeof bootstrap !== 'undefined') {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  }

  async function submitAcknowledgement(note) {
    if (!pendingAckAlertId) return;

    const res = await ApiService.acknowledgeAlert(pendingAckAlertId, note);
    if (res.success) {
      // Close modal
      const modalEl = document.getElementById('acknowledgeModal');
      if (modalEl && typeof bootstrap !== 'undefined') {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }

      // Refresh alerts
      await loadAlerts();
    } else {
      alert(`Acknowledgement failed: ${res.error}`);
    }
  }

  function filterAlerts(filters = {}) {
    let filtered = [...activeAlerts];

    if (filters.station_id && filters.station_id !== 'ALL') {
      filtered = filtered.filter(a => a.station_id === filters.station_id);
    }
    if (filters.severity && filters.severity !== 'ALL') {
      filtered = filtered.filter(a => a.severity === filters.severity);
    }
    if (filters.acknowledged !== undefined && filters.acknowledged !== 'ALL') {
      const isAck = (filters.acknowledged === 'true');
      filtered = filtered.filter(a => a.acknowledged === isAck);
    }

    renderAlertsTable(filtered);
  }

  return {
    loadAlerts,
    filterAlerts,
    submitAcknowledgement,
    formatTime,
    getSeverityBadge
  };
})();
