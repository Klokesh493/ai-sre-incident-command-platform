"""Join a Splunk JSON results export to an incident case."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ops_platform.agent_loop import bounded_json
from ops_platform.domain import Case


def convert(case, exported):
    case = dict(case)
    case["splunk"] = [
        {"id": item["event_id"], "service": item["service"],
         "minute": int(float(item["_time"])) // 60,
         "signature": item["signature"], "severity": item["severity"]}
        for item in exported["results"]]
    return Case.model_validate(case).model_dump()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    print(json.dumps(convert(bounded_json(args.case), bounded_json(args.export)), indent=2))

if __name__ == "__main__":
    main()
