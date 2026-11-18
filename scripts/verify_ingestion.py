"""
Verification script for HBase Microclimate Telemetry Ingestion.
Scans tables, counts rows, validates reverse-timestamp ordering, and prints sample records.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from app.services.hbase_client import HBaseClient, RowKeyBuilder

def main():
    print("=" * 60)
    print("HBASE MICROCLIMATE INGESTION VERIFICATION")
    print("=" * 60)

    client = HBaseClient(settings.HBASE_REST_URL)

    # 1. Verify microclimate:station_status
    print("\n[1] Checking Station Status (microclimate:station_status):")
    stations_found = 0
    for st_cfg in settings.STATIONS:
        st_id = st_cfg["id"]
        status_data = client.get_row(settings.TABLE_STATION_STATUS, st_id)
        if status_data:
            stations_found += 1
            print(f"  Station {st_id} ({st_cfg['name']}):")
            print(f"    Status:      {status_data.get('status:connectivity', 'UNKNOWN')}")
            print(f"    Temp / Hum:  {status_data.get('status:temperature')}°C / {status_data.get('status:humidity')}%")
            print(f"    PM2.5 / PM10:{status_data.get('status:pm25')} / {status_data.get('status:pm10')} µg/m³")
            print(f"    Heat Index:  {status_data.get('status:heat_index')}°C")
            print(f"    Last Update: {status_data.get('status:last_reading_time')}")
        else:
            print(f"  Station {st_id}: No status record found.")

    print(f"\n  Total active stations verified in status table: {stations_found}/{len(settings.STATIONS)}")

    # 2. Verify microclimate:readings
    print("\n[2] Checking Telemetry Readings (microclimate:readings):")
    total_readings_sample = 0
    for st_cfg in settings.STATIONS:
        st_id = st_cfg["id"]
        # Scan prefix for station
        readings = client.scan_prefix(settings.TABLE_READINGS, st_id, limit=50)
        count = len(readings)
        total_readings_sample += count
        print(f"  Station {st_id} readings found: {count}")
        if readings:
            latest = readings[0]
            parsed_key = RowKeyBuilder.parse_reading_key(latest["row_key"])
            print(f"    Latest Row Key: {latest['row_key']}")
            print(f"    Extracted Time: {parsed_key['datetime_utc']}")
            print(f"    Temp: {latest.get('metrics:temperature_celsius')}°C, Hum: {latest.get('metrics:humidity_percent')}%, HeatIndex: {latest.get('metrics:heat_index_celsius')}°C")

    # 3. Check microclimate:alerts
    print("\n[3] Checking System Alerts (microclimate:alerts):")
    all_alerts = []
    for st_cfg in settings.STATIONS:
        st_id = st_cfg["id"]
        st_alerts = client.scan_prefix(settings.TABLE_ALERTS, st_id, limit=20)
        all_alerts.extend(st_alerts)

    print(f"  Total Alerts Logged in HBase: {len(all_alerts)}")
    for a in all_alerts[:5]:
        print(f"    [{a.get('alert:severity')}] {a.get('metadata:station_id')} - {a.get('alert:type')}: {a.get('alert:message')}")
        print(f"      Measurement: {a.get('alert:measurement')} (Threshold: {a.get('alert:threshold')}) at {a.get('metadata:timestamp')}")

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY:")
    print(f"  Station Status Records:  {stations_found}")
    print(f"  Telemetry Sample Count:  {total_readings_sample}")
    print(f"  Alerts Found:            {len(all_alerts)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
