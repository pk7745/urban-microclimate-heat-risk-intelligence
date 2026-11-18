"""
REST API Routes for Urban Microclimate & Heat-Risk Intelligence System.
"""
import logging
from flask import Blueprint, request
from typing import Dict, Any

from app.utils.response import api_success, api_error
from app.services.telemetry_service import TelemetryService, VALID_STATION_IDS, MEASUREMENT_FIELD_MAP
from app.services.simulator_service import SimulatorController

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# Lazy-loaded service singletons
_telemetry_service = None
_simulator_controller = None


def get_telemetry_service() -> TelemetryService:
    global _telemetry_service
    if _telemetry_service is None:
        _telemetry_service = TelemetryService()
    return _telemetry_service


def get_simulator_controller() -> SimulatorController:
    global _simulator_controller
    if _simulator_controller is None:
        _simulator_controller = SimulatorController()
    return _simulator_controller


# -----------------------------------------------------------------------------
# 1. Health Endpoint
# -----------------------------------------------------------------------------
@api_bp.route("/health", methods=["GET"])
def health_check():
    """
    GET /api/v1/health
    Returns overall application health, HBase REST connectivity, table availability,
    and simulator running status.
    """
    telemetry = get_telemetry_service()
    sim_ctrl = get_simulator_controller()

    sim_status = sim_ctrl.get_status()
    health_data, status_code = telemetry.check_health(simulator_running=sim_status["running"])

    if status_code == 200:
        return api_success(data=health_data, message="System and HBase are operational")
    else:
        return api_error(
            message="HBase database or tables are unavailable or degraded",
            error_code="SERVICE_UNAVAILABLE",
            status_code=503,
            details=health_data
        )


# -----------------------------------------------------------------------------
# 2. Stations Endpoints
# -----------------------------------------------------------------------------
@api_bp.route("/stations", methods=["GET"])
def list_stations():
    """
    GET /api/v1/stations
    Returns all 5 stations with static metadata and live telemetry from microclimate:station_status.
    """
    try:
        telemetry = get_telemetry_service()
        stations = telemetry.get_stations()
        return api_success(
            data={"stations": stations, "total": len(stations)},
            message="Station metadata and live status retrieved"
        )
    except Exception as e:
        logger.error("Error retrieving stations: %s", e)
        return api_error(f"Failed to retrieve stations: {str(e)}", error_code="INTERNAL_ERROR", status_code=500)


@api_bp.route("/stations/<station_id>", methods=["GET"])
def get_station(station_id: str):
    """
    GET /api/v1/stations/<station_id>
    Returns detailed station metadata, latest reading, and recent alerts.
    """
    station_id = station_id.upper()
    if station_id not in VALID_STATION_IDS:
        return api_error(
            f"Unknown station_id '{station_id}'. Allowed: {sorted(list(VALID_STATION_IDS))}",
            error_code="STATION_NOT_FOUND",
            status_code=404
        )

    try:
        telemetry = get_telemetry_service()
        station_data = telemetry.get_station_by_id(station_id)
        if not station_data:
            return api_error(f"Station '{station_id}' not found", error_code="STATION_NOT_FOUND", status_code=404)

        return api_success(data=station_data)
    except Exception as e:
        logger.error("Error retrieving station %s: %s", station_id, e)
        return api_error(f"Error fetching station details: {str(e)}", error_code="INTERNAL_ERROR", status_code=500)


# -----------------------------------------------------------------------------
# 3. Telemetry Endpoints
# -----------------------------------------------------------------------------
@api_bp.route("/telemetry/latest", methods=["GET"])
def get_latest_telemetry():
    """
    GET /api/v1/telemetry/latest?station_id=ST001&limit=50
    Returns the newest available telemetry globally sorted descending by timestamp.
    """
    station_id = request.args.get("station_id")
    if station_id:
        station_id = station_id.upper()
        if station_id not in VALID_STATION_IDS:
            return api_error(
                f"Invalid station_id '{station_id}'. Allowed: {sorted(list(VALID_STATION_IDS))}",
                error_code="INVALID_PARAMETER",
                status_code=400
            )

    limit_str = request.args.get("limit", "50")
    try:
        limit = int(limit_str)
        if limit < 1 or limit > 500:
            return api_error("limit must be an integer between 1 and 500", error_code="INVALID_LIMIT", status_code=400)
    except ValueError:
        return api_error("limit must be a valid integer", error_code="INVALID_LIMIT", status_code=400)

    try:
        telemetry = get_telemetry_service()
        readings = telemetry.get_latest_telemetry(station_id=station_id, limit=limit)
        return api_success(
            data={"readings": readings, "count": len(readings)},
            meta={"station_filter": station_id, "limit": limit}
        )
    except Exception as e:
        logger.error("Error retrieving latest telemetry: %s", e)
        return api_error(f"Failed to fetch latest telemetry: {str(e)}", error_code="INTERNAL_ERROR", status_code=500)


@api_bp.route("/telemetry/<station_id>", methods=["GET"])
def get_station_telemetry(station_id: str):
    """
    GET /api/v1/telemetry/<station_id>?start=...&end=...&measurement=...&limit=50&order=desc
    Retrieves historical telemetry spanning multiple dates with exact timestamp filtering.
    """
    station_id = station_id.upper()
    if station_id not in VALID_STATION_IDS:
        return api_error(
            f"Invalid station_id '{station_id}'. Allowed: {sorted(list(VALID_STATION_IDS))}",
            error_code="STATION_NOT_FOUND",
            status_code=404
        )

    start_iso = request.args.get("start")
    end_iso = request.args.get("end")
    measurement = request.args.get("measurement")
    order = request.args.get("order", "desc").lower()

    if order not in ("asc", "desc"):
        return api_error("order must be either 'asc' or 'desc'", error_code="INVALID_ORDER", status_code=400)

    if measurement and measurement.lower() not in MEASUREMENT_FIELD_MAP:
        return api_error(
            f"Invalid measurement '{measurement}'. Allowed: {sorted(list(MEASUREMENT_FIELD_MAP.keys()))}",
            error_code="INVALID_MEASUREMENT",
            status_code=400
        )

    limit_str = request.args.get("limit", "50")
    try:
        limit = int(limit_str)
        if limit < 1 or limit > 1000:
            return api_error("limit must be an integer between 1 and 1000", error_code="INVALID_LIMIT", status_code=400)
    except ValueError:
        return api_error("limit must be a valid integer", error_code="INVALID_LIMIT", status_code=400)

    try:
        telemetry = get_telemetry_service()
        readings = telemetry.get_station_telemetry(
            station_id=station_id,
            start_iso=start_iso,
            end_iso=end_iso,
            measurement=measurement,
            limit=limit,
            order=order
        )
        return api_success(
            data={"station_id": station_id, "readings": readings, "count": len(readings)},
            meta={"start": start_iso, "end": end_iso, "measurement": measurement, "order": order, "limit": limit}
        )
    except ValueError as ve:
        return api_error(str(ve), error_code="INVALID_PARAMETERS", status_code=400)
    except Exception as e:
        logger.error("Error retrieving historical telemetry for %s: %s", station_id, e)
        return api_error(f"Failed to retrieve telemetry: {str(e)}", error_code="INTERNAL_ERROR", status_code=500)


# -----------------------------------------------------------------------------
# 4. Alerts Endpoints
# -----------------------------------------------------------------------------
@api_bp.route("/alerts", methods=["GET"])
def list_alerts():
    """
    GET /api/v1/alerts?station_id=...&severity=...&acknowledged=...&limit=20
    Retrieves system alerts globally sorted newest-first by timestamp.
    """
    station_id = request.args.get("station_id")
    if station_id:
        station_id = station_id.upper()
        if station_id not in VALID_STATION_IDS:
            return api_error(
                f"Invalid station_id '{station_id}'. Allowed: {sorted(list(VALID_STATION_IDS))}",
                error_code="INVALID_PARAMETER",
                status_code=400
            )

    severity = request.args.get("severity")
    acknowledged = request.args.get("acknowledged")

    limit_str = request.args.get("limit", "20")
    try:
        limit = int(limit_str)
        if limit < 1 or limit > 500:
            return api_error("limit must be an integer between 1 and 500", error_code="INVALID_LIMIT", status_code=400)
    except ValueError:
        return api_error("limit must be a valid integer", error_code="INVALID_LIMIT", status_code=400)

    try:
        telemetry = get_telemetry_service()
        alerts = telemetry.get_alerts(
            station_id=station_id,
            severity=severity,
            acknowledged=acknowledged,
            limit=limit
        )
        return api_success(
            data={"alerts": alerts, "count": len(alerts)},
            meta={"station_filter": station_id, "severity_filter": severity, "acknowledged_filter": acknowledged, "limit": limit}
        )
    except ValueError as ve:
        return api_error(str(ve), error_code="INVALID_PARAMETER", status_code=400)
    except Exception as e:
        logger.error("Error retrieving alerts: %s", e)
        return api_error(f"Failed to fetch alerts: {str(e)}", error_code="INTERNAL_ERROR", status_code=500)


@api_bp.route("/alerts/<path:alert_id>/acknowledge", methods=["POST"])
def acknowledge_alert(alert_id: str):
    """
    POST /api/v1/alerts/<alert_id>/acknowledge
    Acknowledges an alert in HBase without mutating other fields.
    The alert_id is the exact HBase row key: STATION#REV_TS#ALERT_TYPE.
    """
    body = request.get_json(silent=True) or {}
    note = body.get("note")

    try:
        telemetry = get_telemetry_service()
        updated_alert = telemetry.acknowledge_alert(alert_id, note=note)
        if not updated_alert:
            return api_error(
                f"Alert with id '{alert_id}' not found or could not be acknowledged",
                error_code="ALERT_NOT_FOUND",
                status_code=404
            )

        return api_success(
            data=updated_alert,
            message=f"Alert '{alert_id}' acknowledged successfully"
        )
    except Exception as e:
        logger.error("Error acknowledging alert %s: %s", alert_id, e)
        return api_error(f"Acknowledgement failed: {str(e)}", error_code="INTERNAL_ERROR", status_code=500)


# -----------------------------------------------------------------------------
# 5. Analytics Endpoints
# -----------------------------------------------------------------------------
@api_bp.route("/analytics/temperature", methods=["GET"])
def get_temperature_analytics():
    """
    GET /api/v1/analytics/temperature?station_id=...&days=1
    Returns statistical metrics (min, max, avg, std_dev) for temperature.
    """
    station_id = request.args.get("station_id")
    if station_id:
        station_id = station_id.upper()
        if station_id not in VALID_STATION_IDS:
            return api_error(f"Invalid station_id '{station_id}'", error_code="INVALID_PARAMETER", status_code=400)

    days_str = request.args.get("days", "1")
    try:
        days = int(days_str)
        if days < 1 or days > 30:
            return api_error("days must be between 1 and 30", error_code="INVALID_PARAMETER", status_code=400)
    except ValueError:
        return api_error("days must be a valid integer", error_code="INVALID_PARAMETER", status_code=400)

    try:
        telemetry = get_telemetry_service()
        stats = telemetry.get_temperature_analytics(station_id=station_id, days=days)
        return api_success(data=stats)
    except Exception as e:
        logger.error("Error calculating temperature analytics: %s", e)
        return api_error(f"Analytics calculation failed: {str(e)}", error_code="INTERNAL_ERROR", status_code=500)


@api_bp.route("/analytics/air-quality", methods=["GET"])
def get_air_quality_analytics():
    """
    GET /api/v1/analytics/air-quality?station_id=...&days=1
    Returns aggregate PM2.5 and PM10 statistics and AQI classification.
    """
    station_id = request.args.get("station_id")
    if station_id:
        station_id = station_id.upper()
        if station_id not in VALID_STATION_IDS:
            return api_error(f"Invalid station_id '{station_id}'", error_code="INVALID_PARAMETER", status_code=400)

    days_str = request.args.get("days", "1")
    try:
        days = int(days_str)
        if days < 1 or days > 30:
            return api_error("days must be between 1 and 30", error_code="INVALID_PARAMETER", status_code=400)
    except ValueError:
        return api_error("days must be a valid integer", error_code="INVALID_PARAMETER", status_code=400)

    try:
        telemetry = get_telemetry_service()
        stats = telemetry.get_air_quality_analytics(station_id=station_id, days=days)
        return api_success(data=stats)
    except Exception as e:
        logger.error("Error calculating air quality analytics: %s", e)
        return api_error(f"Analytics calculation failed: {str(e)}", error_code="INTERNAL_ERROR", status_code=500)


@api_bp.route("/analytics/station-comparison", methods=["GET"])
def get_station_comparison():
    """
    GET /api/v1/analytics/station-comparison
    Returns side-by-side comparative rankings of all 5 stations by Heat-Risk Index.
    """
    try:
        telemetry = get_telemetry_service()
        comparison = telemetry.get_station_comparison()
        return api_success(data=comparison)
    except Exception as e:
        logger.error("Error generating station comparison: %s", e)
        return api_error(f"Comparison calculation failed: {str(e)}", error_code="INTERNAL_ERROR", status_code=500)


# -----------------------------------------------------------------------------
# 6. Simulator Control Endpoints
# -----------------------------------------------------------------------------
@api_bp.route("/simulator/status", methods=["GET"])
def get_simulator_status():
    """
    GET /api/v1/simulator/status
    Returns the execution state, generated counts, and queue statistics of the virtual stations.
    """
    sim_ctrl = get_simulator_controller()
    status = sim_ctrl.get_status()
    return api_success(data=status)


@api_bp.route("/simulator/control", methods=["POST"])
def control_simulator():
    """
    POST /api/v1/simulator/control
    JSON payload:
    {
        "action": "start" | "stop" | "inject_anomaly",
        "interval_seconds": 5.0,
        "station_id": "ST001",
        "anomaly_type": "HIGH_TEMPERATURE",
        "duration_ticks": 3
    }
    """
    data = request.get_json(silent=True)
    if not data or "action" not in data:
        return api_error("Missing required 'action' in JSON body", error_code="MISSING_ACTION", status_code=400)

    action = data.get("action", "").lower().strip()
    sim_ctrl = get_simulator_controller()

    if action == "start":
        interval = data.get("interval_seconds")
        success, msg = sim_ctrl.start(interval_seconds=interval)
        if success:
            return api_success(data=sim_ctrl.get_status(), message=msg)
        else:
            return api_error(msg, error_code="SIMULATOR_START_FAILED", status_code=400)

    elif action == "stop":
        success, msg = sim_ctrl.stop()
        if success:
            return api_success(data=sim_ctrl.get_status(), message=msg)
        else:
            return api_error(msg, error_code="SIMULATOR_STOP_FAILED", status_code=400)

    elif action == "inject_anomaly":
        station_id = data.get("station_id")
        anomaly_type = data.get("anomaly_type")
        duration_ticks = data.get("duration_ticks", 3)

        if not station_id or not anomaly_type:
            return api_error("station_id and anomaly_type are required for inject_anomaly", error_code="MISSING_PARAMETERS", status_code=400)

        success, msg = sim_ctrl.inject_anomaly(station_id, anomaly_type, duration_ticks=duration_ticks)
        if success:
            return api_success(data=sim_ctrl.get_status(), message=msg)
        else:
            return api_error(msg, error_code="ANOMALY_INJECTION_FAILED", status_code=400)

    else:
        return api_error(
            f"Invalid action '{action}'. Supported actions: 'start', 'stop', 'inject_anomaly'",
            error_code="INVALID_ACTION",
            status_code=400
        )
