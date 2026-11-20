# Engineering case study

## Engineering problem

A responder needs a coherent incident, supporting logs, and a current owner before triggering an escalation. Missing telemetry or overlapping coverage can create a misleading page.

## Design choices

Burn thresholds use integer cross-multiplication, preserving exact boundary behavior without floating-point drift. Coverage intervals include the start and exclude the end, so the handoff minute belongs to the next shift. Missing minutes and ambiguous coverage require review.

## Implementation

I built an incident command API that correlates complete SLO windows with normalized Splunk error exports, resolves a unique active on-call owner, and exports a reviewed PagerDuty event payload.

The API and CLI share ops_platform.service.evaluate. Domain contracts and decisions live in ops_platform/domain.py. SQLite persistence is implemented in ops_platform/storage.py. Prometheus metrics are created per API instance. The deployment directory contains the supplied observability and Kubernetes configuration.

## Technical challenges

The incident scenario pages only with a complete telemetry window, a matching error log, and one current owner. A missing minute, ended shift, overlapping owners, or missing log holds the export.

Retry handling also matters across all workflows. A duplicate client request reuses its report, while stale approvals fail with HTTP 409. An unavailable model records an incomplete report that cannot be approved. HEC failures leave audit events pending.

## Validation results

6 labeled domain scenarios passed. The actual local Qwen run returned page for ready.json and review for hold.json. Captured reports include the model name, probe trace, content digests, and cited evidence. API and domain tests cover the decision policy and workflow failure cases. [Validation details](VALIDATION.md)

## Lessons learned

Escalation quality depends on evidence completeness and ownership, as well as the error-rate threshold.

## Remaining scope

Splunk log ingestion is verified against a JSON results export contract. The PagerDuty bundle omits routing credentials and requires an operator's sender. Live Splunk search and PagerDuty event delivery require service access.
