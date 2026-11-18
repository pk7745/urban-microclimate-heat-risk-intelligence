"""
Executable script to create and verify HBase microclimate namespace and tables.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.schema_manager import SchemaManager
from config import settings

def main():
    print(f"Initializing HBase Schema on {settings.HBASE_REST_URL}...")
    mgr = SchemaManager(settings.HBASE_REST_URL)
    results = mgr.init_schema()
    print("\nInitialization Results:")
    all_ok = True
    for item, status in results.items():
        status_str = "SUCCESS" if status else "FAILED"
        print(f"  [{status_str}] {item}")
        if not status:
            all_ok = False

    if all_ok:
        print("\nAll HBase schema components exist and are ready!")
        sys.exit(0)
    else:
        print("\nSome schema components failed to initialize.")
        sys.exit(1)

if __name__ == "__main__":
    main()
