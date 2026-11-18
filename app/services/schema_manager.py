"""
HBase Schema Manager for Urban Microclimate System.
Responsible for idempotent creation and verification of namespaces and tables.
"""
import logging
import requests
from typing import Dict, Any, List

from config import settings

logger = logging.getLogger(__name__)


class SchemaManager:
    """Manages the creation and verification of HBase namespaces and tables."""

    def __init__(self, base_url: str = settings.HBASE_REST_URL):
        self.base_url = base_url.rstrip("/")

    def get_namespaces(self) -> List[str]:
        """Returns the list of existing HBase namespaces."""
        url = f"{self.base_url}/namespaces"
        try:
            r = requests.get(url, headers={"Accept": "application/json"}, timeout=5)
            if r.status_code == 200:
                data = r.json()
                return data.get("Namespace", [])
        except requests.RequestException as e:
            logger.error("Failed to query HBase namespaces: %s", e)
        return []

    def ensure_namespace(self, namespace: str = settings.HBASE_NAMESPACE) -> bool:
        """Ensures the specified namespace exists."""
        namespaces = self.get_namespaces()
        if namespace in namespaces:
            logger.info("Namespace '%s' already exists.", namespace)
            return True

        logger.info("Creating namespace '%s'...", namespace)
        url = f"{self.base_url}/namespaces/{namespace}"
        try:
            r = requests.post(url, headers={"Accept": "application/json"}, timeout=5)
            if r.status_code in (200, 201):
                logger.info("Namespace '%s' created successfully.", namespace)
                return True
            logger.error("Failed to create namespace '%s': HTTP %d %s", namespace, r.status_code, r.text)
            return False
        except requests.RequestException as e:
            logger.error("Error creating namespace '%s': %s", namespace, e)
            return False

    def table_exists(self, table_name: str) -> bool:
        """Checks if a table exists by fetching its schema."""
        url = f"{self.base_url}/{table_name}/schema"
        try:
            r = requests.get(url, headers={"Accept": "application/json"}, timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def create_table(self, table_name: str, column_families: List[str]) -> bool:
        """Creates a table with specified column families if it doesn't already exist."""
        if self.table_exists(table_name):
            logger.info("Table '%s' already exists. Skipping creation.", table_name)
            return True

        logger.info("Creating table '%s' with column families %s...", table_name, column_families)
        schema = {
            "name": table_name,
            "ColumnSchema": [{"name": cf} for cf in column_families]
        }
        url = f"{self.base_url}/{table_name}/schema"
        try:
            r = requests.put(
                url,
                json=schema,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=10
            )
            if r.status_code in (200, 201):
                logger.info("Table '%s' created successfully.", table_name)
                return True
            logger.error("Failed to create table '%s': HTTP %d %s", table_name, r.status_code, r.text)
            return False
        except requests.RequestException as e:
            logger.error("Error creating table '%s': %s", table_name, e)
            return False

    def init_schema(self) -> Dict[str, bool]:
        """Initializes the entire schema for the microclimate project."""
        results = {}
        ns_ok = self.ensure_namespace(settings.HBASE_NAMESPACE)
        results[settings.HBASE_NAMESPACE] = ns_ok

        # 1. microclimate:readings (metrics, metadata)
        results[settings.TABLE_READINGS] = self.create_table(
            settings.TABLE_READINGS,
            [settings.CF_READINGS_METRICS, settings.CF_READINGS_METADATA]
        )

        # 2. microclimate:alerts (alert, metadata)
        results[settings.TABLE_ALERTS] = self.create_table(
            settings.TABLE_ALERTS,
            [settings.CF_ALERTS_ALERT, settings.CF_ALERTS_METADATA]
        )

        # 3. microclimate:station_status (status, metadata)
        results[settings.TABLE_STATION_STATUS] = self.create_table(
            settings.TABLE_STATION_STATUS,
            [settings.CF_STATUS_STATUS, settings.CF_STATUS_METADATA]
        )

        return results
