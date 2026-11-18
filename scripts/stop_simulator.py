"""
Graceful shutdown utility for the running Sensor Simulator process.
"""
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings

PID_FILE = settings.BASE_DIR / "simulator.pid"

def main():
    if not PID_FILE.exists():
        print("No active simulator.pid found. The simulator may not be running.")
        sys.exit(0)

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
    except Exception as e:
        print(f"Error reading {PID_FILE}: {e}")
        sys.exit(1)

    print(f"Signaling simulator process (PID {pid}) to terminate gracefully...")
    try:
        # On Windows, os.kill(pid, signal.CTRL_C_EVENT) or SIGTERM
        os.kill(pid, signal.SIGTERM)
        print("Signal delivered. Waiting for process to exit...")
        for _ in range(10):
            time.sleep(0.5)
            # Check if still running
            try:
                os.kill(pid, 0)
            except OSError:
                print("Simulator process exited cleanly.")
                break
        else:
            print("Process did not exit within 5s, sending taskkill force...")
            os.system(f"taskkill /F /PID {pid} >nul 2>&1")
    except OSError as e:
        print(f"Process PID {pid} was already stopped or inaccessible: {e}")

    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except Exception:
            pass

if __name__ == "__main__":
    main()
