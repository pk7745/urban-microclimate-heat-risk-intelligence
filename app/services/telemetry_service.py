"""
Telemetry and Analytics Service for Urban Microclimate Monitoring.
Provides high-level data retrieval, historical multi-date querying,
alert management, and statistical analytics over Apache HBase tables.
"""
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union

from config import settings
from app.services.hbase_client import HBaseClient, RowKeyBuilder
from app.services.schema_manager import SchemaManager

logger = logging.getLogger(__name__)

# Valid measurement field mappings for filtering
MEASUREMENT_FIELD_MAP = {
    "temperature": "metrics:temperature_celsius",
    "temperature_celsius": "metrics:temperature_celsius",
    "humidity": "metrics:humidity_percent",
    "humidity_percent": "metrics:humidity_percent",
    "pm25": "metrics:pm25",
    "pm10": "metrics:pm10",
    "pressure": "metrics:atmospheric_pressure_hpa",
    "atmospheric_pressure_hpa": "metrics:atmospheric_pressure_hpa",
    "heat_index": "metrics:heat_index_celsius",
    "heat_index_celsius": "metrics:heat_index_celsius"
}

VALID_STATION_IDS = {s["id"] for s in settings.STATIONS}
VALID_SEVERITIES = {"WARNING", "CRITICAL", "INFO"}


class TelemetryService:
    """
    Encapsulates business logic and queries across microclimate HBase tables.
    """

    def __init__(self, hbase_client: Optional[HBaseClient] = None):
        self.hbase = hbase_client or HBaseClient()
        self.schema_mgr = SchemaManager(settings.HBASE_REST_URL)

    # -------------------------------------------------------------------------
    # 1. Health & Cluster Status
    # -------------------------------------------------------------------------
    def check_health(self, simulator_running: bool = False) -> Tuple[Dict[str, Any], int]:
        """
        Inspects HBase REST gateway connectivity, version, table readiness,
        and simulator state.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        health_data = {
            "app_status": "UP",
            "timestamp": now_utc,
            "hbase_connected": False,
            "hbase_version": None,
            "tables": {
                settings.TABLE_READINGS: False,
                settings.TABLE_ALERTS: False,
                settings.TABLE_STATION_STATUS: False
            },
            "simulator_running": simulator_running
        }

        # Check cluster version
        try:
            resp = self.hbase.session.get(
                f"{self.hbase.base_url}/version/cluster",
                headers={"Accept": "application/json"},
                timeout=self.hbase.timeout
            )
            if resp.status_code == 200:
                health_data["hbase_connected"] = True
                ver_info = resp.json()
                health_data["hbase_version"] = ver_info.get("Version", "Unknown")
            else:
                logger.warning("HBase cluster version returned HTTP %d", resp.status_code)
        except Exception as e:
            logger.error("HBase REST health check failed: %s", e)
            health_data["app_status"] = "DEGRADED"
            return health_data, 503

        # Check table existence
        try:
            for tbl in health_data["tables"].keys():
                health_data["tables"][tbl] = self.schema_mgr.table_exists(tbl)
            
            all_tables_up = all(health_data["tables"].values())
            if not all_tables_up:
                health_data["app_status"] = "DEGRADED"
                return health_data, 503
        except Exception as e:
            logger.error("HBase table verification failed: %s", e)
            health_data["app_status"] = "DEGRADED"
            return health_data, 503

        return health_data, 200

    # -------------------------------------------------------------------------
    # 2. Station Information
    # -------------------------------------------------------------------------
    def get_stations(self) -> List[Dict[str, Any]]:
        """
        Retrieves configured station metadata combined with live readings
        from microclimate:station_status.
        """
        stations_list = []
        for cfg in settings.STATIONS:
            st_id = cfg["id"]
            live_status = self.hbase.get_row(settings.TABLE_STATION_STATUS, st_id) or {}
            
            # Helper to cast floats safely
            def to_float(val):
                try:
                    return float(val) if val is not None else None
                except (ValueError, TypeError):
                    return None

            st_obj = {
                "station_id": st_id,
                "station_name": cfg["name"],
                "zone": cfg.get("zone", "Urban"),
                "coordinates": {
                    "latitude": cfg["latitude"],
                    "longitude": cfg["longitude"]
                },
                "connectivity": live_status.get("status:connectivity", "UNKNOWN"),
                "last_reading_time": live_status.get("status:last_reading_time"),
                "temperature": to_float(live_status.get("status:temperature")),
                "humidity": to_float(live_status.get("status:humidity")),
                "pm25": to_float(live_status.get("status:pm25")),
                "pm10": to_float(live_status.get("status:pm10")),
                "heat_index": to_float(live_status.get("status:heat_index")),
                "data_source": live_status.get("metadata:data_source", settings.DATA_SOURCE_LABEL)
            }
            stations_list.append(st_obj)
        return stations_list

    def get_station_by_id(self, station_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed information, latest reading, and recent alerts for a station.
        Returns None if station_id is unknown.
        """
        station_id = station_id.upper()
        cfg = next((s for s in settings.STATIONS if s["id"] == station_id), None)
        if not cfg:
            return None

        # Fetch status
        live_status = self.hbase.get_row(settings.TABLE_STATION_STATUS, station_id) or {}

        # Fetch latest reading
        latest_readings = self.get_latest_telemetry(station_id=station_id, limit=1)
        latest_reading = latest_readings[0] if latest_readings else None

        # Fetch recent alerts for this station
        recent_alerts = self.get_alerts(station_id=station_id, limit=5)

        return {
            "station_id": station_id,
            "station_name": cfg["name"],
            "zone": cfg.get("zone", "Urban"),
            "coordinates": {
                "latitude": cfg["latitude"],
                "longitude": cfg["longitude"]
            },
            "status": {
                "connectivity": live_status.get("status:connectivity", "UNKNOWN"),
                "last_reading_time": live_status.get("status:last_reading_time"),
                "last_updated": live_status.get("metadata:last_updated")
            },
            "latest_reading": latest_reading,
            "recent_alerts": recent_alerts
        }

    # -------------------------------------------------------------------------
    # 3. Telemetry Retrieval (Multi-Date Boundary Compliant)
    # -------------------------------------------------------------------------
    def get_latest_telemetry(self,
                             station_id: Optional[str] = None,
                             limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves the latest telemetry records, globally sorted by timestamp descending.
        Handles date partition boundaries by inspecting the current UTC date partition
        and preceding partitions (up to 7 days) until `limit` is fulfilled.
        """
        limit = max(1, min(limit, 500))
        target_stations = [station_id.upper()] if station_id else [s["id"] for s in settings.STATIONS]
        
        all_records: List[Dict[str, Any]] = []
        now_utc = datetime.now(timezone.utc)

        # Inspect up to 7 preceding UTC days
        lookback_days = 7

        for st in target_stations:
            st_records = []
            for day_offset in range(lookback_days):
                target_date = (now_utc - timedelta(days=day_offset)).strftime("%Y%m%d")
                prefix = f"{st}#{target_date}#"
                raw_rows = self.hbase.scan_prefix(settings.TABLE_READINGS, prefix, limit=limit)
                for r in raw_rows:
                    parsed = self._format_reading_row(r)
                    if parsed:
                        st_records.append(parsed)
                if len(st_records) >= limit:
                    break
            all_records.extend(st_records)

        # Sort globally by timestamp_ms descending
        all_records.sort(key=lambda x: x["timestamp_ms"], reverse=True)
        return all_records[:limit]

    def get_station_telemetry(self,
                              station_id: str,
                              start_iso: Optional[str] = None,
                              end_iso: Optional[str] = None,
                              measurement: Optional[str] = None,
                              limit: int = 50,
                              order: str = "desc") -> List[Dict[str, Any]]:
        """
        Retrieves historical telemetry for a specific station with support for:
        - Exact start and end timestamp filtering
        - Spanning multiple UTC date partitions correctly
        - Specific measurement filtering
        - Descending (newest first) or ascending (oldest first) sorting
        """
        station_id = station_id.upper()
        limit = max(1, min(limit, 1000))
        order = order.lower()
        if order not in ("asc", "desc"):
            order = "desc"

        # Parse start and end timestamps into UTC
        now_utc = datetime.now(timezone.utc)
        start_dt = self._parse_iso_to_utc(start_iso) if start_iso else (now_utc - timedelta(days=1))
        end_dt = self._parse_iso_to_utc(end_iso) if end_iso else (now_utc + timedelta(hours=1))

        if start_dt > end_dt:
            raise ValueError(f"start timestamp ({start_dt.isoformat()}) must be before end timestamp ({end_dt.isoformat()})")

        # Bound maximum historical range to 30 days to avoid unbounded scans
        if (end_dt - start_dt).days > 30:
            raise ValueError("Requested historical time range exceeds maximum allowed window of 30 days.")

        start_epoch_ms = int(start_dt.timestamp() * 1000)
        end_epoch_ms = int(end_dt.timestamp() * 1000)

        # Enumerate all UTC date partitions intersecting [start_dt, end_dt]
        date_partitions = []
        cur_date = start_dt.date()
        end_date = end_dt.date()
        while cur_date <= end_date:
            date_partitions.append(cur_date.strftime("%Y%m%d"))
            cur_date += timedelta(days=1)

        # Query each date partition
        merged_rows: List[Dict[str, Any]] = []
        for date_str in date_partitions:
            prefix = f"{station_id}#{date_str}#"
            raw_rows = self.hbase.scan_prefix(settings.TABLE_READINGS, prefix, limit=1000)
            for r in raw_rows:
                parsed = self._format_reading_row(r)
                if not parsed:
                    continue
                # Exact epoch filtering
                if start_epoch_ms <= parsed["timestamp_ms"] <= end_epoch_ms:
                    # Optional measurement projection/filtering
                    if measurement:
                        field_key = MEASUREMENT_FIELD_MAP.get(measurement.lower())
                        if field_key:
                            col_qual = field_key.split(":")[1]
                            if col_qual not in parsed or parsed[col_qual] is None:
                                continue
                    merged_rows.append(parsed)

        # Sort according to requested order
        reverse_sort = (order == "desc")
        merged_rows.sort(key=lambda x: x["timestamp_ms"], reverse=reverse_sort)

        # Apply limit after sorting
        return merged_rows[:limit]

    # -------------------------------------------------------------------------
    # 4. Alerts Management
    # -------------------------------------------------------------------------
    def get_alerts(self,
                   station_id: Optional[str] = None,
                   severity: Optional[str] = None,
                   acknowledged: Optional[Union[bool, str]] = None,
                   limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieves alerts from microclimate:alerts across stations,
        globally sorted newest-first by timestamp.
        """
        limit = max(1, min(limit, 500))
        target_stations = [station_id.upper()] if station_id else [s["id"] for s in settings.STATIONS]

        if severity:
            severity = severity.upper()
            if severity not in VALID_SEVERITIES:
                raise ValueError(f"Invalid severity '{severity}'. Allowed: {VALID_SEVERITIES}")

        ack_filter: Optional[bool] = None
        if acknowledged is not None:
            if isinstance(acknowledged, bool):
                ack_filter = acknowledged
            elif isinstance(acknowledged, str):
                ack_filter = acknowledged.lower() in ("true", "1", "yes")

        all_alerts: List[Dict[str, Any]] = []
        for st in target_stations:
            raw_alerts = self.hbase.scan_prefix(settings.TABLE_ALERTS, f"{st}#", limit=limit * 2)
            for r in raw_alerts:
                parsed = self._format_alert_row(r)
                if not parsed:
                    continue
                # Apply filters
                if severity and parsed["severity"] != severity:
                    continue
                if ack_filter is not None and parsed["acknowledged"] != ack_filter:
                    continue
                all_alerts.append(parsed)

        # Global sort by timestamp descending
        all_alerts.sort(key=lambda x: x["timestamp_ms"], reverse=True)
        return all_alerts[:limit]

    def acknowledge_alert(self, alert_id: str, note: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Acknowledges an alert by updating metadata:acknowledged to true.
        The alert_id is the exact HBase row key (STATION#REV_TS#ALERT_TYPE).
        """
        # Validate row key format
        try:
            RowKeyBuilder.parse_alert_key(alert_id)
        except ValueError as e:
            logger.warning("Invalid alert_id format '%s': %s", alert_id, e)
            return None

        # Check existing row
        existing = self.hbase.get_row(settings.TABLE_ALERTS, alert_id)
        if not existing:
            return None

        now_utc = datetime.now(timezone.utc).isoformat()
        ack_note = note.strip() if note else "Acknowledged via REST API"

        update_cols = {
            "metadata:acknowledged": "true",
            "metadata:acknowledged_at": now_utc,
            "metadata:acknowledgement_note": ack_note
        }

        success = self.hbase.put_row(settings.TABLE_ALERTS, alert_id, update_cols)
        if not success:
            logger.error("Failed to update acknowledgement on alert row '%s'", alert_id)
            return None

        # Return updated alert object
        updated_row = self.hbase.get_row(settings.TABLE_ALERTS, alert_id)
        return self._format_alert_row({"row_key": alert_id, **(updated_row or {})})

    # -------------------------------------------------------------------------
    # 5. Statistical Analytics
    # -------------------------------------------------------------------------
    def get_temperature_analytics(self, station_id: Optional[str] = None, days: int = 1) -> Dict[str, Any]:
        """
        Calculates aggregate temperature statistics (min, max, avg, std_dev, count)
        over the specified historical window.
        """
        days = max(1, min(days, 30))
        now_utc = datetime.now(timezone.utc)
        start_dt = now_utc - timedelta(days=days)

        stations = [station_id.upper()] if station_id else [s["id"] for s in settings.STATIONS]
        station_stats = {}
        all_temps = []

        for st in stations:
            readings = self.get_station_telemetry(
                station_id=st,
                start_iso=start_dt.isoformat(),
                end_iso=now_utc.isoformat(),
                measurement="temperature_celsius",
                limit=1000
            )
            temps = [r["temperature_celsius"] for r in readings if r.get("temperature_celsius") is not None]
            all_temps.extend(temps)
            station_stats[st] = self._calculate_basic_stats(temps)

        global_stats = self._calculate_basic_stats(all_temps)

        return {
            "time_window_days": days,
            "start_time": start_dt.isoformat(),
            "end_time": now_utc.isoformat(),
            "global_summary": global_stats,
            "station_breakdown": station_stats
        }

    def get_air_quality_analytics(self, station_id: Optional[str] = None, days: int = 1) -> Dict[str, Any]:
        """
        Calculates aggregate air quality statistics (PM2.5 and PM10)
        and estimates National Air Quality Index (NAQI) categories.
        """
        days = max(1, min(days, 30))
        now_utc = datetime.now(timezone.utc)
        start_dt = now_utc - timedelta(days=days)

        stations = [station_id.upper()] if station_id else [s["id"] for s in settings.STATIONS]
        station_stats = {}
        all_pm25 = []
        all_pm10 = []

        for st in stations:
            readings = self.get_station_telemetry(
                station_id=st,
                start_iso=start_dt.isoformat(),
                end_iso=now_utc.isoformat(),
                limit=1000
            )
            pm25_vals = [r["pm25"] for r in readings if r.get("pm25") is not None]
            pm10_vals = [r["pm10"] for r in readings if r.get("pm10") is not None]

            all_pm25.extend(pm25_vals)
            all_pm10.extend(pm10_vals)

            station_stats[st] = {
                "pm25": self._calculate_basic_stats(pm25_vals),
                "pm10": self._calculate_basic_stats(pm10_vals),
                "air_quality_category": self._classify_aqi_category(
                    pm25_vals[-1] if pm25_vals else None,
                    pm10_vals[-1] if pm10_vals else None
                )
            }

        return {
            "time_window_days": days,
            "start_time": start_dt.isoformat(),
            "end_time": now_utc.isoformat(),
            "global_summary": {
                "pm25": self._calculate_basic_stats(all_pm25),
                "pm10": self._calculate_basic_stats(all_pm10)
            },
            "station_breakdown": station_stats
        }

    def get_station_comparison(self) -> Dict[str, Any]:
        """
        Produces a side-by-side comparative table of all 5 stations,
        ranking them by current heat-risk index and air quality severity.
        """
        stations = self.get_stations()
        comparison = []

        for st in stations:
            st_id = st["station_id"]
            hi = st.get("heat_index")
            temp = st.get("temperature")
            pm25 = st.get("pm25")
            alerts = self.get_alerts(station_id=st_id, acknowledged=False, limit=50)

            risk_level = "NORMAL"
            if hi is not None:
                if hi >= 44.0:
                    risk_level = "EXTREME DANGER"
                elif hi >= 38.0:
                    risk_level = "DANGER / WARNING"
                elif hi >= 32.0:
                    risk_level = "CAUTION"

            comparison.append({
                "station_id": st_id,
                "station_name": st["station_name"],
                "zone": st["zone"],
                "connectivity": st["connectivity"],
                "temperature": temp,
                "humidity": st.get("humidity"),
                "pm25": pm25,
                "pm10": st.get("pm10"),
                "heat_index": hi,
                "heat_risk_level": risk_level,
                "active_unacknowledged_alerts": len(alerts),
                "last_reading_time": st.get("last_reading_time")
            })

        # Rank by heat index descending (highest heat stress first).
        # Explicit None check preserves valid numerical zero values (0.0°C),
        # while keeping missing/invalid values (None) at the bottom of descending rankings.
        comparison.sort(
            key=lambda x: x["heat_index"] if x.get("heat_index") is not None else float("-inf"),
            reverse=True
        )

        return {
            "comparison_timestamp": datetime.now(timezone.utc).isoformat(),
            "stations_count": len(comparison),
            "rankings": comparison
        }

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    @staticmethod
    def _parse_iso_to_utc(iso_str: str) -> datetime:
        """Parses ISO timestamp string or epoch ms to timezone-aware UTC datetime."""
        try:
            # Check if integer epoch ms
            if iso_str.isdigit():
                return datetime.fromtimestamp(int(iso_str) / 1000.0, tz=timezone.utc)
            # Parse ISO string
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception as e:
            raise ValueError(f"Invalid timestamp format '{iso_str}': {e}")

    @staticmethod
    def _format_reading_row(row_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parses raw HBase cell dictionary into clean JSON-serializable reading dict."""
        row_key = row_dict.get("row_key")
        if not row_key:
            return None
        try:
            parsed_key = RowKeyBuilder.parse_reading_key(row_key)
        except Exception:
            return None

        def to_f(key):
            val = row_dict.get(key)
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        return {
            "row_key": row_key,
            "station_id": row_dict.get("metadata:station_id", parsed_key["station_id"]),
            "station_name": row_dict.get("metadata:station_name"),
            "timestamp": row_dict.get("metadata:timestamp", parsed_key["datetime_utc"]),
            "timestamp_ms": parsed_key["timestamp_ms"],
            "temperature_celsius": to_f("metrics:temperature_celsius"),
            "humidity_percent": to_f("metrics:humidity_percent"),
            "pm25": to_f("metrics:pm25"),
            "pm10": to_f("metrics:pm10"),
            "atmospheric_pressure_hpa": to_f("metrics:atmospheric_pressure_hpa"),
            "heat_index_celsius": to_f("metrics:heat_index_celsius"),
            "sensor_status": row_dict.get("metadata:sensor_status", "ACTIVE"),
            "data_source": row_dict.get("metadata:data_source", settings.DATA_SOURCE_LABEL)
        }

    @staticmethod
    def _format_alert_row(row_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parses raw HBase alert row into clean alert dict.
        Enriches presentation with data provenance (SIMULATED), NWS applicability validity,
        and objective historical event classification.
        """
        row_key = row_dict.get("row_key")
        if not row_key:
            return None
        try:
            parsed_key = RowKeyBuilder.parse_alert_key(row_key)
        except Exception:
            return None

        ack_val = row_dict.get("metadata:acknowledged", "false")
        acknowledged = (ack_val.lower() == "true")
        alert_type = row_dict.get("alert:type", parsed_key["alert_type"])
        measurement_str = row_dict.get("alert:measurement")
        calc_status = row_dict.get("alert:calculation_status")
        origin_temp = row_dict.get("alert:origin_temp")
        origin_humidity = row_dict.get("alert:origin_humidity")

        # Assess calculation validity under NWS methodology and data provenance
        if alert_type == "HIGH_HEAT_INDEX":
            if calc_status is not None:
                origin_t_val = None
                origin_rh_val = None
                try:
                    if origin_temp is not None:
                        origin_t_val = float(origin_temp)
                    if origin_humidity is not None:
                        origin_rh_val = float(origin_humidity)
                except (ValueError, TypeError):
                    pass

                applicability = {
                    "is_valid": True,
                    "status": calc_status,
                    "origin_temp_celsius": origin_t_val,
                    "origin_humidity_percent": origin_rh_val,
                    "note": "Verified calculation with complete provenance."
                }
            else:
                # Legacy alert record without calculation metadata.
                # Per Phase 3.4 methodology, validity cannot be deduced from the output scalar alone.
                applicability = {
                    "is_valid": None,
                    "status": "LEGACY_UNVERIFIED",
                    "note": "Legacy alert record missing calculation provenance metadata; validity cannot be independently verified."
                }
        else:
            applicability = {
                "is_valid": True,
                "status": "VALIDATED_DOMAIN",
                "note": "Direct physical sensor metric."
            }

        # Event classification: Alert table records are historical event logs
        event_status = "HISTORICAL_ACKNOWLEDGED" if acknowledged else "HISTORICAL_UNACKNOWLEDGED"

        return {
            "alert_id": row_key,
            "station_id": row_dict.get("metadata:station_id", parsed_key["station_id"]),
            "type": alert_type,
            "severity": row_dict.get("alert:severity", "WARNING"),
            "measurement": measurement_str,
            "threshold": row_dict.get("alert:threshold"),
            "message": row_dict.get("alert:message"),
            "timestamp": row_dict.get("metadata:timestamp"),
            "timestamp_ms": parsed_key["timestamp_ms"],
            "acknowledged": acknowledged,
            "acknowledged_at": row_dict.get("metadata:acknowledged_at"),
            "acknowledgement_note": row_dict.get("metadata:acknowledgement_note"),
            "data_source": row_dict.get("metadata:data_source", settings.DATA_SOURCE_LABEL),
            "event_status": event_status,
            "calculation_applicability": applicability
        }

    @staticmethod
    def _calculate_basic_stats(numbers: List[float]) -> Dict[str, Any]:
        """Calculates count, min, max, average, and standard deviation."""
        valid_nums = [n for n in numbers if n is not None and not math.isnan(n)]
        count = len(valid_nums)
        if count == 0:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "average": None,
                "std_dev": None
            }

        min_val = round(min(valid_nums), 2)
        max_val = round(max(valid_nums), 2)
        avg_val = round(sum(valid_nums) / count, 2)
        variance = sum((x - avg_val) ** 2 for x in valid_nums) / count
        std_dev = round(math.sqrt(variance), 2)

        return {
            "count": count,
            "min": min_val,
            "max": max_val,
            "average": avg_val,
            "std_dev": std_dev
        }

    @staticmethod
    def _classify_aqi_category(pm25: Optional[float], pm10: Optional[float]) -> str:
        """Determines approximate Air Quality category based on India National AQI breakpoints."""
        if pm25 is None and pm10 is None:
            return "UNKNOWN"
        p25 = pm25 or 0.0
        p10 = pm10 or 0.0

        if p25 <= 30 and p10 <= 50:
            return "GOOD"
        elif p25 <= 60 and p10 <= 100:
            return "SATISFACTORY"
        elif p25 <= 90 and p10 <= 250:
            return "MODERATE"
        elif p25 <= 120 and p10 <= 350:
            return "POOR"
        elif p25 <= 250 and p10 <= 430:
            return "VERY POOR"
        else:
            return "SEVERE"
