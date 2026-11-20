"""Replay the labeled domain scenarios and write verification evidence."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ops_platform.service import evaluate  # noqa: E402

cases = json.loads((ROOT / "examples/suite.json").read_text())
results = []
for entry in cases:
    report = evaluate(json.loads((ROOT / "examples" / entry["input"]).read_text()))
    passed = report["decision"] == entry["expected"] and report["stop"] == "evidence_complete"
    results.append({"name": entry["name"], "expected": entry["expected"],
                    "decision": report["decision"], "passed": passed})
path = ROOT / "reports/replay.json"
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(results, indent=2) + "\n")
print(f"{sum(row['passed'] for row in results)}/{len(results)} scenarios passed")
raise SystemExit(not all(row["passed"] for row in results))
