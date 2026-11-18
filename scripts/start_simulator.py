"""
Command-line runner to launch real-time Sensor Simulation & HBase Ingestion.
Supports continuous execution, graceful shutdown via Ctrl+C, duration limits,
and scheduled anomaly demonstration.
"""
import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from app.services.sensor_simulator import SensorSimulatorManager
from app.services.ingestion_service import IngestionService
from app.services.schema_manager import SchemaManager

# Configure logging to console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.SIMULATOR_LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("SimulatorRunner")

PID_FILE = settings.BASE_DIR / "simulator.pid"


def main():
    parser = argparse.ArgumentParser(description="Urban Microclimate Sensor Simulator & Ingestor")
    parser.add_argument("--interval", type=float, default=settings.SIMULATOR_INTERVAL_SECONDS,
                        help="Reading interval in seconds per station (default: 5.0)")
    parser.add_argument("--duration", type=int, default=0,
                        help="Run duration in seconds (0 = run indefinitely until Ctrl+C)")
    parser.add_argument("--cycles", type=int, default=0,
                        help="Run for N reading cycles per station, then stop (0 = disabled)")
    parser.add_argument("--demo-anomalies", action="store_true", default=False,
                        help="Automatically inject test anomalies after 2 cycles to demonstrate alert detection")
    args = parser.parse_args()

    # Write PID file for process management
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    logger.info("Verifying HBase schema before starting ingestion...")
    schema_mgr = SchemaManager(settings.HBASE_REST_URL)
    schema_mgr.init_schema()

    logger.info("Initializing Ingestion Service...")
    ingestor = IngestionService()
    ingestor.start()

    logger.info("Initializing Sensor Simulator Manager (interval=%.1fs)...", args.interval)
    simulator = SensorSimulatorManager(
        interval_seconds=args.interval,
        on_reading_callback=ingestor.submit_reading
    )

    # Graceful shutdown handler
    stop_requested = False

    def handle_exit(signum, frame):
        nonlocal stop_requested
        logger.info("\nTermination signal received. Initiating graceful shutdown...")
        stop_requested = True

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    simulator.start()
    start_time = time.time()
    logger.info("System running. Press Ctrl+C or run 'stop_simulator.py' to stop.")

    cycle_count = 0
    anomaly_injected = False

    try:
        while not stop_requested:
            time.sleep(1.0)
            elapsed = time.time() - start_time
            stats = ingestor.get_stats()

            # Optional anomaly demonstration
            if args.demo_anomalies and not anomaly_injected and elapsed >= (args.interval * 2):
                logger.info(">>> DEMO: Injecting HIGH_TEMPERATURE on ST001 and ELEVATED_PM25 on ST004 <<<")
                simulator.trigger_anomaly("ST001", "HIGH_TEMPERATURE", duration_ticks=3)
                simulator.trigger_anomaly("ST004", "ELEVATED_PM25", duration_ticks=3)
                anomaly_injected = True

            # Check limits
            if args.duration > 0 and elapsed >= args.duration:
                logger.info("Reached target duration of %ds.", args.duration)
                break

            if args.cycles > 0 and stats["total_ingested"] >= (args.cycles * len(settings.STATIONS)):
                logger.info("Reached target cycles (%d per station, total %d).",
                            args.cycles, stats["total_ingested"])
                break

    finally:
        logger.info("Halting simulator...")
        simulator.stop()
        logger.info("Draining ingestion queue...")
        ingestor.stop()

        # Remove PID file
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except Exception:
                pass

        final_stats = ingestor.get_stats()
        print("\n" + "="*50)
        print("SIMULATION RUN SUMMARY:")
        print(f"  Stations Active:    {len(settings.STATIONS)}")
        print(f"  Total Generated:    {simulator.generated_count}")
        print(f"  Total Ingested:     {final_stats['total_ingested']}")
        print(f"  Total Failed:       {final_stats['total_failed']}")
        print(f"  Alerts Created:     {final_stats['alerts_created']}")
        print(f"  Remaining Queue:    {final_stats['queue_size']}")
        print("="*50)


if __name__ == "__main__":
    main()
