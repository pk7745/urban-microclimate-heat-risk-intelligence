import os
import re

workspace_dir = r"C:\Users\pky45\.gemini\antigravity\scratch\urban-microclimate-hbase"
docs_dir = os.path.join(workspace_dir, "docs", "academic_validation")

core_docs = [
    "PHASE_8_4_6_FINAL_TECHNICAL_EVALUATION.md",
    "PHASE_8_4_5_API_DASHBOARD_EVALUATION.md",
    "PHASE_8_4_4_HEAT_INDEX_ANOMALY_ACCURACY.md",
    "PHASE_8_4_3_3_RELIABILITY_SYNTHESIS.md",
    "PHASE_8_4_3_2_RELIABILITY_FINDING_VERIFICATION.md",
    "PHASE_8_4_3_1_RELIABILITY_RESULTS.md",
    "PHASE_8_4_2_PERFORMANCE_RESULTS.md",
    "PHASE_8_4_1_EVALUATION_DESIGN.md",
    "PHASE_8_3_RESEARCH_COMPARISON.md",
    "PHASE_8_2_LITERATURE_REVIEW.md",
    "PHASE_8_1_PROJECT_BASELINE.md",
    "ACADEMIC_AUDIT_CORRECTIONS.md"
]

checks = [
    ("40.77", "40.77"),
    ("40.774647", "40.774647"),
    ("0.004647", "0.004647"),
    ("25/25", "25/25"),
    ("additive", "additive"),
    ("HI_avg", "HI_avg"),
    ("simulated", "simulated"),
    ("RF-01", "RF-01"),
    ("RF-02", "RF-02"),
    ("RF-03", "RF-03"),
    ("RF-04", "RF-04"),
    ("RF-05", "RF-05"),
    ("RF-06", "RF-06"),
    ("RF-07", "RF-07"),
    ("RF-08", "RF-08")
]

print("=== AUDIT CONSISTENCY CHECK ===")
for doc in core_docs:
    p = os.path.join(docs_dir, doc)
    if not os.path.exists(p):
        print(f"MISSING: {doc}")
        continue
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    found_items = [lbl for lbl, target in checks if target in txt]
    print(f"{doc}: found {len(found_items)}/{len(checks)} markers -> {', '.join(found_items[:6])}...")

print("\n=== SCANNING FOR DISALLOWED/OBSOLETE VALUES ===")
# Check for old typo 40.784647 or old 40.78
for doc in core_docs:
    p = os.path.join(docs_dir, doc)
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    if "40.784647" in txt:
        print(f"WARNING: {doc} contains 40.784647!")
    if "40.78" in txt:
        # Check context
        for line in txt.splitlines():
            if "40.78" in line and "40.77" not in line:
                print(f"  Context in {doc}: {line.strip()}")

print("\nAudit consistency check completed.")
