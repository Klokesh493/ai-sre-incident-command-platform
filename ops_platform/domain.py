"""Incident correlation across SLO buckets, exported Splunk signals, and on-call coverage."""
import json
from typing import List, Literal

from pydantic import Field, model_validator

from .agent_loop import Probe
from .contracts import Count, Identifier, Positive, Record, unique

TITLE = "AI SRE Incident Command Platform"
BRIEF = "Review incident telemetry, matching Splunk exports, and active on-call coverage."
SOURCES = ["telemetry", "splunk", "oncall"]


class Bucket(Record):
    id: Identifier
    service: Identifier
    minute: Count
    requests: Positive
    errors: Count

    @model_validator(mode="after")
    def totals(self):
        if self.errors > self.requests:
            raise ValueError("errors exceed requests")
        return self


class Log(Record):
    id: Identifier
    service: Identifier
    minute: Count
    signature: Identifier
    severity: Literal["info", "error"]


class Shift(Record):
    service: Identifier
    owner: Identifier
    start_minute: Count
    end_minute: Positive

    @model_validator(mode="after")
    def interval(self):
        if self.end_minute <= self.start_minute:
            raise ValueError("on-call shift must have positive duration")
        return self


class Case(Record):
    now_minute: Count
    window_minutes: Positive = Field(default=3, le=60)
    error_budget_ppm: Positive = Field(default=1000, le=999999)
    burn_threshold: Positive = 10
    telemetry: List[Bucket] = Field(min_length=1, max_length=250)
    splunk: List[Log] = Field(max_length=250)
    oncall: List[Shift] = Field(max_length=100)

    @model_validator(mode="after")
    def identities(self):
        unique([b.id for b in self.telemetry], "bucket ids")
        unique([(b.service, b.minute) for b in self.telemetry], "service minute buckets")
        unique([log.id for log in self.splunk], "log ids")
        if any(b.minute > self.now_minute for b in self.telemetry) or any(
                log.minute > self.now_minute for log in self.splunk):
            raise ValueError("telemetry is from the future")
        return self


def prepare(case):
    source = case.model_dump()
    source["telemetry"] = {"buckets": source["telemetry"], "now_minute": case.now_minute,
                           "window_minutes": case.window_minutes,
                           "error_budget_ppm": case.error_budget_ppm,
                           "burn_threshold": case.burn_threshold}
    probes = [Probe(key, "Read " + key + " evidence", lambda key=key: source[key])
              for key in SOURCES]

    def decide(evidence):
        incidents, review = [], []
        expected = set(range(max(0, case.now_minute - case.window_minutes + 1), case.now_minute + 1))
        services = sorted({b.service for b in case.telemetry})
        for service in services:
            buckets = [b for b in case.telemetry if b.service == service and b.minute in expected]
            if {b.minute for b in buckets} != expected or len(expected) != case.window_minutes:
                review.append({"service": service, "reason": "incomplete telemetry window"})
                continue
            requests = sum(b.requests for b in buckets)
            errors = sum(b.errors for b in buckets)
            breach = errors * 1000000 >= requests * case.error_budget_ppm * case.burn_threshold
            if not breach:
                continue
            owners = {s.owner for s in case.oncall if s.service == service
                      and s.start_minute <= case.now_minute < s.end_minute}
            logs = [log for log in case.splunk if log.service == service
                    and log.minute in expected and log.severity == "error"]
            if len(owners) != 1 or not logs:
                review.append({"service": service, "reason": "ambiguous coverage or missing Splunk evidence"})
                continue
            incidents.append({"service": service, "owner": next(iter(owners)), "errors": errors,
                              "requests": requests, "log_ids": sorted(log.id for log in logs)})
        decision = "review" if review else ("page" if incidents else "observe")
        return {"decision": decision, "ready": not review, "citations": SOURCES,
                "incidents": incidents, "review": review,
                "reason": "Review incomplete evidence before exporting events." if review
                          else "Correlated SLO and log evidence has an unambiguous owner."}

    return probes, decide


def bundle(report):
    # Routing credentials are supplied by the operator's sender, outside this bundle.
    events = [{"event_action": "trigger", "dedup_key": "slo-" + item["service"],
               "payload": {"summary": "SLO burn requires review for " + item["service"],
                           "source": item["service"], "severity": "critical",
                           "custom_details": item}} for item in report["incidents"]]
    return {"pagerduty-events.json": json.dumps(events, indent=2)}
