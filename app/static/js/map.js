/**
 * Leaflet Interactive Map Module for Bengaluru Urban Microclimate Stations.
 * Visualizes the 5 configured simulated stations on high-contrast dark tiles.
 */
const MapManager = (function () {
  let map = null;
  const markers = {};

  // Station Coordinates from config/settings.py
  const DEFAULT_COORDS = {
    'ST001': { lat: 12.9716, lon: 77.5946, name: 'Bengaluru Central', zone: 'Commercial / Urban Core' },
    'ST002': { lat: 12.9784, lon: 77.6408, name: 'Bengaluru East', zone: 'Tech Corridor / Dense Traffic' },
    'ST003': { lat: 12.9250, lon: 77.5938, name: 'Bengaluru South', zone: 'Residential / Green Canopy' },
    'ST004': { lat: 12.9750, lon: 77.5350, name: 'Bengaluru West', zone: 'Industrial / Transit Interchange' },
    'ST005': { lat: 13.0358, lon: 77.5970, name: 'Bengaluru North', zone: 'Highway / Peri-urban' }
  };

  function initMap(containerId = 'station-map') {
    const el = document.getElementById(containerId);
    if (!el || typeof L === 'undefined') {
      console.warn('Map container or Leaflet library unavailable.');
      return;
    }

    if (map) {
      map.invalidateSize();
      return;
    }

    // Centered on Bengaluru metropolitan region
    map = L.map(containerId, {
      center: [12.9716, 77.5946],
      zoom: 11,
      zoomControl: true,
      attributionControl: false
    });

    // Dark Matter basemap tiles (CartoDB)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 18,
      subdomains: 'abcd'
    }).addTo(map);

    // Initial default markers
    updateMarkers([]);
  }

  function getMarkerColor(station) {
    const conn = (station.connectivity || '').toUpperCase();
    const hi = station.heat_index;

    if (conn === 'OFFLINE') return 'grey';
    if (conn === 'ERROR' || (hi !== null && hi !== undefined && hi >= 44.0)) return 'red';
    if (conn === 'WARNING' || (hi !== null && hi !== undefined && hi >= 38.0)) return 'amber';
    return 'green';
  }

  function createCustomIcon(color) {
    const colorHex = color === 'red' ? '#ef4444' : (color === 'amber' ? '#f59e0b' : (color === 'grey' ? '#64748b' : '#10b981'));
    return L.divIcon({
      className: 'custom-station-marker',
      html: `<div style="
        width: 20px;
        height: 20px;
        background: ${colorHex};
        border: 2px solid #ffffff;
        border-radius: 50%;
        box-shadow: 0 0 10px ${colorHex};
        cursor: pointer;
      "></div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10],
      popupAnchor: [0, -12]
    });
  }

  function updateMarkers(stations = []) {
    if (!map || typeof L === 'undefined') return;

    const stationMap = {};
    stations.forEach(s => {
      stationMap[s.station_id] = s;
    });

    const bounds = [];

    // Ensure all 5 defined stations are rendered
    Object.keys(DEFAULT_COORDS).forEach(stId => {
      const def = DEFAULT_COORDS[stId];
      const live = stationMap[stId] || {};
      
      const lat = (live.coordinates && live.coordinates.latitude) || def.lat;
      const lon = (live.coordinates && live.coordinates.longitude) || def.lon;
      bounds.push([lat, lon]);

      const color = getMarkerColor(live);
      const icon = createCustomIcon(color);

      const tempStr = live.temperature !== undefined && live.temperature !== null ? `${live.temperature} °C` : 'N/A';
      const humStr = live.humidity !== undefined && live.humidity !== null ? `${live.humidity} %` : 'N/A';
      const hiStr = live.heat_index !== undefined && live.heat_index !== null ? `${live.heat_index} °C` : 'N/A';
      const pm25Str = live.pm25 !== undefined && live.pm25 !== null ? `${live.pm25} µg/m³` : 'N/A';
      const statusStr = (live.connectivity || 'ACTIVE').toUpperCase();

      const popupHtml = `
        <div style="font-family: var(--font-sans); min-width: 180px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <strong style="color: var(--color-cyan); font-size: 0.95rem;">${stId}</strong>
            <span class="badge-status ${statusStr === 'ACTIVE' ? 'badge-active' : (statusStr === 'OFFLINE' ? 'badge-offline' : 'badge-warning')}" style="font-size: 0.65rem;">
              ${statusStr}
            </span>
          </div>
          <div style="font-size: 0.85rem; font-weight: 600; color: #fff;">${live.station_name || def.name}</div>
          <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 8px;">${live.zone || def.zone}</div>
          <hr style="border-color: var(--border-color); margin: 6px 0;">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 0.75rem;">
            <div><span style="color: var(--text-muted);">Temp:</span> <strong style="color: #fff;">${tempStr}</strong></div>
            <div><span style="color: var(--text-muted);">Humidity:</span> <strong style="color: #fff;">${humStr}</strong></div>
            <div><span style="color: var(--text-muted);">Heat Index:</span> <strong style="color: #fff;">${hiStr}</strong></div>
            <div><span style="color: var(--text-muted);">PM2.5:</span> <strong style="color: #fff;">${pm25Str}</strong></div>
          </div>
          <div style="margin-top: 6px; font-size: 0.65rem; color: #60a5fa; text-transform: uppercase;">
            <i class="bi bi-broadcast"></i> SIMULATED STATION
          </div>
        </div>
      `;

      if (markers[stId]) {
        markers[stId].setLatLng([lat, lon]);
        markers[stId].setIcon(icon);
        markers[stId].setPopupContent(popupHtml);
      } else {
        const marker = L.marker([lat, lon], { icon: icon }).addTo(map);
        marker.bindPopup(popupHtml);
        markers[stId] = marker;
      }
    });

    if (bounds.length > 0 && !map._hasFittedBounds) {
      map.fitBounds(bounds, { padding: [30, 30] });
      map._hasFittedBounds = true;
    }
  }

  function resize() {
    if (map) {
      setTimeout(() => map.invalidateSize(), 200);
    }
  }

  return {
    initMap,
    updateMarkers,
    resize
  };
})();
