/**
 * API Service Client for Urban Microclimate & Heat-Risk Intelligence System.
 * Handles centralized REST communication, URL building, error handling, and parameter parsing.
 */
const ApiService = (function () {
  const BASE_URL = '/api/v1';

  async function request(endpoint, options = {}) {
    const url = `${BASE_URL}${endpoint}`;
    const defaultHeaders = {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    };

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {})
      }
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();

      if (!response.ok) {
        const errorMsg = (data && data.error && typeof data.error === 'object' && data.error.message)
          ? data.error.message
          : (data && data.message ? data.message : `HTTP Error ${response.status}`);
        const errorCode = (data && data.error && typeof data.error === 'object' && data.error.code)
          ? data.error.code
          : null;
        return {
          success: false,
          status: response.status,
          error: errorMsg,
          code: errorCode,
          details: data.details || null
        };
      }

      return {
        success: true,
        status: response.status,
        data: data.data,
        message: data.message,
        meta: data.meta || null
      };
    } catch (err) {
      console.error(`[API Network Error] ${url}:`, err);
      return {
        success: false,
        status: 0,
        error: 'Network connection failed. Backend or HBase may be unreachable.',
        details: err.message
      };
    }
  }

  function toQueryString(params = {}) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        query.append(key, value);
      }
    }
    const qStr = query.toString();
    return qStr ? `?${qStr}` : '';
  }

  return {
    // 1. Health
    async getHealth() {
      return await request('/health');
    },

    // 2. Stations
    async getStations() {
      return await request('/stations');
    },

    async getStation(stationId) {
      return await request(`/stations/${encodeURIComponent(stationId)}`);
    },

    // 3. Telemetry
    async getLatestTelemetry(params = {}) {
      return await request(`/telemetry/latest${toQueryString(params)}`);
    },

    async getStationTelemetry(stationId, params = {}) {
      return await request(`/telemetry/${encodeURIComponent(stationId)}${toQueryString(params)}`);
    },

    // 4. Alerts
    async getAlerts(params = {}) {
      return await request(`/alerts${toQueryString(params)}`);
    },

    async acknowledgeAlert(alertId, note = null) {
      // alertId is STATION#REV_TS#TYPE - safe-encode for path
      const encodedId = encodeURIComponent(alertId);
      return await request(`/alerts/${encodedId}/acknowledge`, {
        method: 'POST',
        body: JSON.stringify({ note: note || 'Acknowledged via Dashboard UI' })
      });
    },

    // 5. Analytics
    async getTemperatureAnalytics(params = {}) {
      return await request(`/analytics/temperature${toQueryString(params)}`);
    },

    async getAirQualityAnalytics(params = {}) {
      return await request(`/analytics/air-quality${toQueryString(params)}`);
    },

    async getStationComparison() {
      return await request('/analytics/station-comparison');
    },

    // 6. Simulator Control
    async getSimulatorStatus() {
      return await request('/simulator/status');
    },

    async controlSimulator(payload) {
      return await request('/simulator/control', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
    }
  };
})();
