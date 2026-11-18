"""
Unit tests for HBase Row-Key Architecture.
Verifies format, uniqueness, reverse timestamp lexicographical sorting, and key parsing.
"""
import time
from datetime import datetime, timezone
import pytest
from app.services.hbase_client import RowKeyBuilder, MAX_REVERSE_EPOCH_MS


def test_row_key_format():
    station_id = "ST001"
    now_ms = 1794937200000
    key = RowKeyBuilder.build_reading_key(station_id, now_ms)

    assert key.startswith("ST001#")
    parts = key.split("#")
    assert len(parts) == 3
    assert parts[0] == "ST001"
    assert len(parts[1]) == 8  # YYYYMMDD
    assert len(parts[2]) == 13  # 13-digit zero-padded reverse timestamp


def test_row_key_parsing():
    station_id = "ST002"
    now_ms = 1794937250000
    key = RowKeyBuilder.build_reading_key(station_id, now_ms)

    parsed = RowKeyBuilder.parse_reading_key(key)
    assert parsed["station_id"] == "ST002"
    assert parsed["timestamp_ms"] == now_ms
    assert "datetime_utc" in parsed


def test_reverse_timestamp_lexicographical_ordering():
    """
    CRITICAL PROPERTY:
    Newer readings MUST sort lexicographically BEFORE older readings in HBase scans.
    """
    station_id = "ST001"
    t1_old = 1794937000000
    t2_mid = 1794937005000
    t3_new = 1794937010000

    k1 = RowKeyBuilder.build_reading_key(station_id, t1_old)
    k2 = RowKeyBuilder.build_reading_key(station_id, t2_mid)
    k3 = RowKeyBuilder.build_reading_key(station_id, t3_new)

    keys = [k1, k2, k3]
    sorted_keys = sorted(keys)

    # In HBase scan order, newest reading (k3) must be first!
    assert sorted_keys[0] == k3
    assert sorted_keys[1] == k2
    assert sorted_keys[2] == k1


def test_alert_row_key():
    key = RowKeyBuilder.build_alert_key("ST003", "HIGH_TEMPERATURE", 1794937000000)
    assert key.startswith("ST003#")
    assert key.endswith("#HIGH_TEMPERATURE")
    parsed = RowKeyBuilder.parse_alert_key(key)
    assert parsed["station_id"] == "ST003"
    assert parsed["alert_type"] == "HIGH_TEMPERATURE"
    assert parsed["timestamp_ms"] == 1794937000000


def test_status_row_key():
    key = RowKeyBuilder.build_status_key("ST005")
    assert key == "ST005"
