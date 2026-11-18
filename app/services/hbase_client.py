"""
HBase REST Client and Row-Key Architecture Manager.
Provides Base64 encoding/decoding, resilient HTTP communication, row-key generation,
and CRUD operations for Apache HBase over the Stargate REST gateway.
"""
import base64
import json
import logging
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from config import settings

logger = logging.getLogger(__name__)

# Maximum epoch milliseconds constant for 13-digit reverse timestamps (covers up to Nov 2286)
MAX_REVERSE_EPOCH_MS = 9999999999999


class RowKeyBuilder:
    """
    Constructs and parses station-centric, time-oriented HBase row keys.
    Design:
    - Readings: <station_id>#<YYYYMMDD>#<reverse_timestamp_ms>
      * Avoids monotonically increasing hot-spotting on cluster writes by sharding on station_id.
      * Reverse timestamp ensures newest readings sort FIRST for constant-time recent telemetry retrieval.
    - Alerts: <station_id>#<reverse_timestamp_ms>#<alert_type>
    - Status: <station_id>
    """

    @staticmethod
    def build_reading_key(station_id: str, timestamp_ms: int) -> str:
        """Constructs an HBase row key for microclimate:readings."""
        dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
        date_str = dt.strftime("%Y%m%d")
        rev_ts = f"{MAX_REVERSE_EPOCH_MS - timestamp_ms:013d}"
        return f"{station_id}#{date_str}#{rev_ts}"

    @staticmethod
    def parse_reading_key(row_key: str) -> Dict[str, Any]:
        """Parses an HBase reading row key back into its components."""
        parts = row_key.split("#")
        if len(parts) != 3:
            raise ValueError(f"Invalid reading row key format: {row_key}")
        station_id, date_str, rev_ts_str = parts
        timestamp_ms = MAX_REVERSE_EPOCH_MS - int(rev_ts_str)
        return {
            "station_id": station_id,
            "date": date_str,
            "timestamp_ms": timestamp_ms,
            "datetime_utc": datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).isoformat()
        }

    @staticmethod
    def build_alert_key(station_id: str, alert_type: str, timestamp_ms: int) -> str:
        """Constructs an HBase row key for microclimate:alerts."""
        rev_ts = f"{MAX_REVERSE_EPOCH_MS - timestamp_ms:013d}"
        return f"{station_id}#{rev_ts}#{alert_type}"

    @staticmethod
    def parse_alert_key(row_key: str) -> Dict[str, Any]:
        """Parses an HBase alert row key."""
        parts = row_key.split("#")
        if len(parts) != 3:
            raise ValueError(f"Invalid alert row key format: {row_key}")
        station_id, rev_ts_str, alert_type = parts
        timestamp_ms = MAX_REVERSE_EPOCH_MS - int(rev_ts_str)
        return {
            "station_id": station_id,
            "timestamp_ms": timestamp_ms,
            "alert_type": alert_type
        }

    @staticmethod
    def build_status_key(station_id: str) -> str:
        """Constructs an HBase row key for microclimate:station_status."""
        return station_id


class HBaseClient:
    """
    Robust HTTP client for interacting with Apache HBase REST (Stargate) API.
    """

    def __init__(self, base_url: str = settings.HBASE_REST_URL, timeout: int = 5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=settings.INGESTION_RETRY_ATTEMPTS,
            backoff_factor=settings.INGESTION_RETRY_BACKOFF,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    @staticmethod
    def encode_b64(val: Any) -> str:
        """Encodes any value to Base64 string."""
        if val is None:
            return ""
        if isinstance(val, bytes):
            return base64.b64encode(val).decode("utf-8")
        return base64.b64encode(str(val).encode("utf-8")).decode("utf-8")

    @staticmethod
    def decode_b64(val: str) -> str:
        """Decodes a Base64 string back to UTF-8 text."""
        if not val:
            return ""
        return base64.b64decode(val.encode("utf-8")).decode("utf-8", errors="replace")

    def put_row(self, table: str, row_key: str, columns: Dict[str, Any]) -> bool:
        """
        Inserts or updates a single row with column mappings.
        columns format: {"family:qualifier": value, ...}
        """
        row_b64 = self.encode_b64(row_key)
        cells = []
        for col_name, col_val in columns.items():
            cells.append({
                "column": self.encode_b64(col_name),
                "$": self.encode_b64(col_val)
            })

        payload = {
            "Row": [{
                "key": row_b64,
                "Cell": cells
            }]
        }

        quoted_key = urllib.parse.quote(row_key, safe='')
        url = f"{self.base_url}/{table}/{quoted_key}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        try:
            resp = self.session.put(url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code in (200, 201):
                return True
            logger.error("HBase put_row failed on table '%s' key '%s': HTTP %d: %s",
                         table, row_key, resp.status_code, resp.text)
            return False
        except requests.RequestException as e:
            logger.error("HBase network error on put_row for '%s': %s", row_key, e)
            return False

    def get_row(self, table: str, row_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single row by row_key, decoding Base64 cells.
        Returns flattened dict: {"family:qualifier": value, ...}
        """
        quoted_key = urllib.parse.quote(row_key, safe='')
        url = f"{self.base_url}/{table}/{quoted_key}"
        headers = {"Accept": "application/json"}
        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 404:
                return None
            if resp.status_code == 200:
                data = resp.json()
                result = {}
                for row in data.get("Row", []):
                    for cell in row.get("Cell", []):
                        col = self.decode_b64(cell.get("column", ""))
                        val = self.decode_b64(cell.get("$", ""))
                        result[col] = val
                return result
            logger.warning("HBase get_row '%s' on '%s' failed: HTTP %d", row_key, table, resp.status_code)
            return None
        except requests.RequestException as e:
            logger.error("HBase network error on get_row '%s': %s", row_key, e)
            return None

    def scan_prefix(self, table: str, prefix: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scans rows matching a row key prefix using the glob wildcard prefix endpoint.
        Returns list of dicts with 'row_key' and decoded column values.
        """
        quoted_prefix = urllib.parse.quote(prefix, safe='')
        url = f"{self.base_url}/{table}/{quoted_prefix}*"
        headers = {"Accept": "application/json"}
        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 404:
                return []
            if resp.status_code == 200:
                data = resp.json()
                rows = []
                for row_item in data.get("Row", [])[:limit]:
                    r_key = self.decode_b64(row_item.get("key", ""))
                    row_dict = {"row_key": r_key}
                    for cell in row_item.get("Cell", []):
                        col = self.decode_b64(cell.get("column", ""))
                        val = self.decode_b64(cell.get("$", ""))
                        row_dict[col] = val
                    rows.append(row_dict)
                return rows
            logger.warning("HBase scan_prefix on '%s' failed: HTTP %d", table, resp.status_code)
            return []
        except requests.RequestException as e:
            logger.error("HBase network error on scan_prefix for '%s': %s", table, e)
            return []
