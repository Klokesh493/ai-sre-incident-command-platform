import json
from pathlib import Path

import pytest

from ops_platform import domain
from ops_platform.service import evaluate

def fixture(name):
    return json.loads((Path("examples") / (name + ".json")).read_text())


def test_correlation_and_pagerduty_contract():
    report = evaluate(fixture("ready"))
    assert report["incidents"][0]["owner"] == "responder-a"
    events = json.loads(domain.bundle(report)["pagerduty-events.json"])
    assert events[0]["event_action"] == "trigger"
    assert events[0]["payload"]["severity"] == "critical"
    assert "routing_key" not in events[0]

def test_duplicate_minute_rejected():
    source = fixture("ready")
    source["telemetry"].append(dict(source["telemetry"][0], id="other"))
    with pytest.raises(ValueError):
        evaluate(source)

def test_future_log_rejected():
    source = fixture("ready")
    source["splunk"][0]["minute"] = 101
    with pytest.raises(ValueError):
        evaluate(source)

def test_exact_burn_threshold_pages():
    source = fixture("ready")
    for row in source["telemetry"]:
        row["errors"] = 100
    assert evaluate(source)["decision"] == "page"

def test_splunk_results_import():
    from tools.import_splunk import convert
    case = fixture("ready")
    source = {"results": [{"event_id": "splunk-42", "service": "checkout",
                          "_time": "6000", "signature": "db-timeout", "severity": "error"}]}
    imported = convert(case, source)
    assert evaluate(imported)["incidents"][0]["log_ids"] == ["splunk-42"]
