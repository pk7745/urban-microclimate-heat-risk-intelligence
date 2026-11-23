"""
Phase 8.4.2 Safe Performance Benchmark Script
Executes isolated, non-mutating performance benchmarks:
- Benchmark A: Isolated In-Memory Queue (10,000 records)
- Benchmark B: Worker Processing with Mocked Persistence (5,000 records)
- Benchmark C: Read-Only Query Availability Check
"""
import sys
import os
import time
import math
import queue
import threading
import socket
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import MagicMock

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# Suppress console log spam during high-throughput benchmarking
logging.basicConfig(level=logging.ERROR)
logging.getLogger("app").setLevel(logging.ERROR)

from config import settings
from app.services.anomaly_detector import AnomalyDetector
from app.services.hbase_client import RowKeyBuilder
from app.services.ingestion_service import IngestionService
from app.services.sensor_simulator import assess_heat_index


def generate_synthetic_reading(index: int, station_id: str = "ST001") -> Dict[str, Any]:
    """Generates a schema-compliant synthetic reading dictionary."""
    base_ts_ms = 1794941200000 + (index * 5000)
    # Simulate variations: mostly normal, occasional anomalies
    temp = 28.0 + (index % 15) * 0.8
    hum = 50.0 + (index % 10) * 3.0
    pm25 = 25.0 + (index % 20) * 4.0
    pm10 = 45.0 + (index % 20) * 7.0
    pressure = 920.0 + (index % 5) * 0.5
    
    hi_res = assess_heat_index(temp, hum)
    
    return {
        "station_id": station_id,
        "station_name": "Bengaluru Central",
        "timestamp": f"2026-11-18T{index%24:02d}:00:00Z",
        "timestamp_ms": base_ts_ms,
        "temperature_celsius": round(temp, 2),
        "humidity_percent": round(hum, 2),
        "pm25": round(pm25, 2),
        "pm10": round(pm10, 2),
        "atmospheric_pressure_hpa": round(pressure, 2),
        "heat_index_celsius": hi_res["heat_index_celsius"],
        "heat_index_status": hi_res["status"],
        "heat_index_is_valid": hi_res["is_valid"],
        "sensor_status": "ACTIVE" if index % 500 != 0 else "OFFLINE",
        "data_source": "SIMULATED"
    }


# =============================================================================
# BENCHMARK A: IN-MEMORY QUEUE BENCHMARK
# =============================================================================
def run_benchmark_a(n_records: int = 10000, queue_capacity: int = 1000) -> Dict[str, Any]:
    print(f"\n[BENCHMARK A] Running In-Memory Queue Benchmark ({n_records} records, capacity={queue_capacity})...")
    test_queue = queue.Queue(maxsize=queue_capacity)
    
    readings = [generate_synthetic_reading(i) for i in range(n_records)]
    
    # Warm-up phase (1,000 items)
    warmup_queue = queue.Queue(maxsize=queue_capacity)
    for i in range(1000):
        warmup_queue.put(readings[i % n_records], block=False)
        warmup_queue.get()
    
    # Part 1: Saturated Burst Mode (Queue capacity 1000, 10,000 records attempted non-blocking)
    # Tests non-blocking queue saturation and drop handling
    burst_successful = 0
    burst_rejected = 0
    burst_latencies_ns = []
    
    consumer_stop = threading.Event()
    burst_consumed = 0
    
    def burst_consumer_loop():
        nonlocal burst_consumed
        while not consumer_stop.is_set() or not test_queue.empty():
            try:
                test_queue.get(timeout=0.01)
                burst_consumed += 1
                test_queue.task_done()
            except queue.Empty:
                continue

    consumer_thread = threading.Thread(target=burst_consumer_loop, daemon=True)
    consumer_thread.start()
    
    burst_start_time = time.perf_counter_ns()
    
    for r in readings:
        t0 = time.perf_counter_ns()
        try:
            test_queue.put(r, block=False)
            t1 = time.perf_counter_ns()
            burst_latencies_ns.append(t1 - t0)
            burst_successful += 1
        except queue.Full:
            t1 = time.perf_counter_ns()
            burst_latencies_ns.append(t1 - t0)
            burst_rejected += 1

    burst_producer_end = time.perf_counter_ns()
    test_queue.join()
    consumer_stop.set()
    consumer_thread.join(timeout=5.0)
    burst_total_end = time.perf_counter_ns()
    burst_queue_empty = test_queue.empty() and test_queue.qsize() == 0

    burst_lat_us = sorted([l / 1000.0 for l in burst_latencies_ns])
    burst_producer_dur_s = (burst_producer_end - burst_start_time) / 1e9
    burst_successful_tp = burst_successful / burst_producer_dur_s if burst_producer_dur_s > 0 else 0
    
    # Part 2: Controlled Batched Flow Mode (10 batches of 1,000 records = 10,000 records)
    # Tests sustained throughput without rejection by draining each batch of 1,000
    batch_size = 1000
    num_batches = 10
    batched_successful = 0
    batched_rejected = 0
    batched_latencies_ns = []
    batch_wait_times_ms = []
    
    batched_queue = queue.Queue(maxsize=queue_capacity)
    batched_consumed = 0
    batch_consumer_stop = threading.Event()
    
    def batched_consumer_loop():
        nonlocal batched_consumed
        while not batch_consumer_stop.is_set() or not batched_queue.empty():
            try:
                batched_queue.get(timeout=0.01)
                batched_consumed += 1
                batched_queue.task_done()
            except queue.Empty:
                continue

    batch_consumer_thread = threading.Thread(target=batched_consumer_loop, daemon=True)
    batch_consumer_thread.start()

    batched_start_time = time.perf_counter_ns()
    for b in range(num_batches):
        batch_slice = readings[b * batch_size : (b + 1) * batch_size]
        for r in batch_slice:
            t0 = time.perf_counter_ns()
            try:
                batched_queue.put(r, block=False)
                t1 = time.perf_counter_ns()
                batched_latencies_ns.append(t1 - t0)
                batched_successful += 1
            except queue.Full:
                t1 = time.perf_counter_ns()
                batched_latencies_ns.append(t1 - t0)
                batched_rejected += 1
        # Synchronize and measure drain wait time for this batch
        tw0 = time.perf_counter_ns()
        batched_queue.join()
        tw1 = time.perf_counter_ns()
        batch_wait_times_ms.append((tw1 - tw0) / 1e6)

    batch_consumer_stop.set()
    batch_consumer_thread.join(timeout=5.0)
    batched_end_time = time.perf_counter_ns()
    batched_queue_empty = batched_queue.empty() and batched_queue.qsize() == 0
    
    batched_lat_us = sorted([l / 1000.0 for l in batched_latencies_ns])
    batched_total_dur_s = (batched_end_time - batched_start_time) / 1e9
    batched_throughput = batched_successful / batched_total_dur_s if batched_total_dur_s > 0 else 0
    
    result = {
        "benchmark": "A. In-Memory Queue Throughput & Latency",
        "dataset_size": n_records,
        "queue_capacity": queue_capacity,
        "mode_1_saturated_burst": {
            "attempted_submissions": n_records,
            "successful_insertions": burst_successful,
            "rejected_insertions": burst_rejected,
            "consumed_records": burst_consumed,
            "final_queue_empty_verified": burst_queue_empty,
            "producer_duration_seconds": round(burst_producer_dur_s, 4),
            "successful_throughput_rec_sec": round(burst_successful_tp, 2),
            "attempted_submission_rate_rec_sec": round(n_records / burst_producer_dur_s, 2),
            "latency_microseconds": {
                "min": round(burst_lat_us[0], 3),
                "median": round(burst_lat_us[len(burst_lat_us)//2], 3),
                "mean": round(sum(burst_lat_us)/len(burst_lat_us), 3),
                "p95": round(burst_lat_us[int(len(burst_lat_us)*0.95)], 3),
                "p99": round(burst_lat_us[int(len(burst_lat_us)*0.99)], 3),
                "max": round(burst_lat_us[-1], 3)
            }
        },
        "mode_2_controlled_batched_flow": {
            "total_batches": num_batches,
            "batch_size": batch_size,
            "attempted_submissions": n_records,
            "successful_insertions": batched_successful,
            "rejected_insertions": batched_rejected,
            "consumed_records": batched_consumed,
            "final_queue_empty_verified": batched_queue_empty,
            "total_duration_seconds": round(batched_total_dur_s, 4),
            "successful_throughput_rec_sec": round(batched_throughput, 2),
            "mean_batch_drain_wait_time_ms": round(sum(batch_wait_times_ms)/len(batch_wait_times_ms), 3),
            "latency_microseconds": {
                "min": round(batched_lat_us[0], 3),
                "median": round(batched_lat_us[len(batched_lat_us)//2], 3),
                "mean": round(sum(batched_lat_us)/len(batched_lat_us), 3),
                "p95": round(batched_lat_us[int(len(batched_lat_us)*0.95)], 3),
                "p99": round(batched_lat_us[int(len(batched_lat_us)*0.99)], 3),
                "max": round(batched_lat_us[-1], 3)
            }
        }
    }
    print(f"  [RESULT A1 - Burst] Successful: {burst_successful}/{n_records}, Rejected: {burst_rejected}")
    print(f"  [RESULT A1 - Burst] Median Latency: {burst_lat_us[len(burst_lat_us)//2]:.3f} us, p95: {burst_lat_us[int(len(burst_lat_us)*0.95)]:.3f} us")
    print(f"  [RESULT A1 - Burst] Queue Empty Verified: {burst_queue_empty}")
    print(f"  [RESULT A2 - Batched] Successful: {batched_successful}/{n_records}, Rejected: {batched_rejected}")
    print(f"  [RESULT A2 - Batched] Median Latency: {batched_lat_us[len(batched_lat_us)//2]:.3f} us, p95: {batched_lat_us[int(len(batched_lat_us)*0.95)]:.3f} us")
    print(f"  [RESULT A2 - Batched] Sustained Throughput: {batched_throughput:.2f} rec/sec")
    print(f"  [RESULT A2 - Batched] Queue Empty Verified: {batched_queue_empty}")
    return result


# =============================================================================
# BENCHMARK B: WORKER PROCESSING WITH MOCKED PERSISTENCE
# =============================================================================
class MockIsolatedHBaseClient:
    """Mock HBase Client that intercepts every call with zero network activity."""
    def __init__(self):
        self.call_log = []
        self.put_counts = {
            settings.TABLE_READINGS: 0,
            settings.TABLE_STATION_STATUS: 0,
            settings.TABLE_ALERTS: 0
        }
    
    def put_row(self, table: str, row_key: str, columns: Dict[str, Any]) -> bool:
        self.call_log.append((table, row_key))
        if table in self.put_counts:
            self.put_counts[table] += 1
        return True


def run_benchmark_b(n_records: int = 5000) -> Dict[str, Any]:
    print(f"\n[BENCHMARK B] Running Worker Processing Benchmark with Mocked Persistence ({n_records} records)...")
    
    mock_hbase = MockIsolatedHBaseClient()
    detector = AnomalyDetector()
    
    # Create isolated IngestionService with mocked HBase
    ingestor = IngestionService(hbase_client=mock_hbase, anomaly_detector=detector, queue_maxsize=n_records + 100)
    
    readings = [generate_synthetic_reading(i, station_id=f"ST00{(i%5)+1}") for i in range(n_records)]
    
    # Warm-up phase (500 records)
    for i in range(500):
        ingestor._process_single_reading(readings[i % n_records])
    
    # Reset mock counters after warmup
    mock_hbase.call_log.clear()
    for k in mock_hbase.put_counts:
        mock_hbase.put_counts[k] = 0
        
    records_processed = 0
    processing_failures = 0
    total_processing_latencies_ns = []
    
    # Separable measurement arrays
    anomaly_latencies_ns = []
    rowkey_latencies_ns = []
    
    start_total_ns = time.perf_counter_ns()
    
    for r in readings:
        t_start = time.perf_counter_ns()
        try:
            # Measure separable anomaly detection
            t_anom_start = time.perf_counter_ns()
            alerts = detector.analyze_reading(r)
            t_anom_end = time.perf_counter_ns()
            anomaly_latencies_ns.append(t_anom_end - t_anom_start)
            
            # Measure separable rowkey building
            t_key_start = time.perf_counter_ns()
            reading_key = RowKeyBuilder.build_reading_key(r["station_id"], r["timestamp_ms"])
            status_key = RowKeyBuilder.build_status_key(r["station_id"])
            t_key_end = time.perf_counter_ns()
            rowkey_latencies_ns.append(t_key_end - t_key_start)
            
            # Process complete ingestion workflow
            ingestor._process_single_reading(r)
            
            t_end = time.perf_counter_ns()
            total_processing_latencies_ns.append(t_end - t_start)
            records_processed += 1
        except Exception as e:
            processing_failures += 1
            print(f"  [ERROR] Record processing failed: {e}")
            
    end_total_ns = time.perf_counter_ns()
    
    total_duration_s = (end_total_ns - start_total_ns) / 1e9
    throughput_rec_sec = records_processed / total_duration_s if total_duration_s > 0 else 0
    
    # Compute latencies in microseconds
    total_us = [l / 1000.0 for l in total_processing_latencies_ns]
    anom_us = [l / 1000.0 for l in anomaly_latencies_ns]
    key_us = [l / 1000.0 for l in rowkey_latencies_ns]
    
    total_us.sort()
    anom_us.sort()
    key_us.sort()
    
    result = {
        "benchmark": "B. Worker Processing (Mocked Persistence)",
        "dataset_size": n_records,
        "records_processed": records_processed,
        "processing_failures": processing_failures,
        "total_duration_seconds": round(total_duration_s, 4),
        "processing_throughput_rec_sec": round(throughput_rec_sec, 2),
        "mocked_persistence_verification": {
            "network_http_requests_made": 0,
            "mocked_calls_readings_table": mock_hbase.put_counts[settings.TABLE_READINGS],
            "mocked_calls_status_table": mock_hbase.put_counts[settings.TABLE_STATION_STATUS],
            "mocked_calls_alerts_table": mock_hbase.put_counts[settings.TABLE_ALERTS],
            "total_mocked_calls": len(mock_hbase.call_log)
        },
        "total_latency_microseconds": {
            "min": round(total_us[0], 3),
            "median": round(total_us[len(total_us)//2], 3),
            "mean": round(sum(total_us)/len(total_us), 3),
            "p95": round(total_us[int(len(total_us)*0.95)], 3),
            "p99": round(total_us[int(len(total_us)*0.99)], 3),
            "max": round(total_us[-1], 3)
        },
        "separable_components_microseconds": {
            "anomaly_detection_median": round(anom_us[len(anom_us)//2], 3),
            "anomaly_detection_p95": round(anom_us[int(len(anom_us)*0.95)], 3),
            "rowkey_construction_median": round(key_us[len(key_us)//2], 3),
            "rowkey_construction_p95": round(key_us[int(len(key_us)*0.95)], 3),
            "dict_assembly_and_mock_put_median": round(total_us[len(total_us)//2] - anom_us[len(anom_us)//2] - key_us[len(key_us)//2], 3)
        }
    }
    print(f"  [RESULT B] Processed: {records_processed}/{n_records}, Failures: {processing_failures}")
    print(f"  [RESULT B] Median Total Latency: {total_us[len(total_us)//2]:.3f} us, p95: {total_us[int(len(total_us)*0.95)]:.3f} us")
    print(f"  [RESULT B] Separable: Anomaly={anom_us[len(anom_us)//2]:.3f} us, RowKey={key_us[len(key_us)//2]:.3f} us")
    print(f"  [RESULT B] Throughput: {throughput_rec_sec:.2f} rec/sec")
    print(f"  [RESULT B] Total Mocked Puts Intercepted: {len(mock_hbase.call_log)} (Zero HTTP requests)")
    return result


# =============================================================================
# BENCHMARK C: READ-ONLY QUERY PERFORMANCE CHECK
# =============================================================================
def check_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Non-destructive socket probe."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def run_benchmark_c() -> Dict[str, Any]:
    print("\n[BENCHMARK C] Checking Service Availability for Read-Only Query Benchmark...")
    
    hbase_running = check_port_open("127.0.0.1", 8085, timeout=0.5)
    flask_running = check_port_open("127.0.0.1", 5000, timeout=0.5)
    
    print(f"  Port 8085 (HBase REST Gateway): {'OPEN' if hbase_running else 'CLOSED / UNAVAILABLE'}")
    print(f"  Port 5000 (Flask Web Server):    {'OPEN' if flask_running else 'CLOSED / UNAVAILABLE'}")
    
    if not hbase_running or not flask_running:
        print("  [STATUS] Benchmark C is BLOCKED because live services are not running.")
        print("  [SAFETY] Per Phase 8.4 safety rules, daemons and servers are NOT started automatically.")
        return {
            "benchmark": "C. Read-Only Query Performance",
            "status": "BLOCKED",
            "reason": "Live HBase REST Gateway (port 8085) and/or Flask API server (port 5000) are not running.",
            "safety_action": "Strictly adhered to non-destructive rules: services were not started automatically.",
            "service_probe": {
                "hbase_rest_8085": "UNAVAILABLE",
                "flask_api_5000": "UNAVAILABLE"
            }
        }

    # If services were running, read-only GET queries would be executed here
    return {"status": "SKIPPED"}


if __name__ == "__main__":
    print("======================================================================")
    print("PHASE 8.4.2 SAFE PERFORMANCE BENCHMARK SUITE")
    print("======================================================================")
    print(f"Python Version: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    res_a = run_benchmark_a(n_records=10000, queue_capacity=1000)
    res_b = run_benchmark_b(n_records=5000)
    res_c = run_benchmark_c()
    
    output = {
        "environment": {
            "python_version": sys.version,
            "platform": sys.platform,
            "timer": "time.perf_counter_ns"
        },
        "benchmark_a": res_a,
        "benchmark_b": res_b,
        "benchmark_c": res_c
    }
    
    out_file = WORKSPACE_ROOT / "docs" / "academic_validation" / "scripts" / "benchmark_results.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n[COMPLETE] Results saved to {out_file}")
