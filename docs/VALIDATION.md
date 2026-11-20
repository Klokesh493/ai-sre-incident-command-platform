# Validation evidence

Verified on November 19, 2026 using Python 3.12.16.

| Check | Result |
| --- | --- |
| Domain and API tests | 29 passed |
| Labeled replay scenarios | 6 passed |
| Real local Qwen model runs | Passing and held cases returned complete evidence |
| Real HTTP API demo | Evaluation, idempotent retry, approval, export and bundle retrieval passed |
| Local HEC contract | Three workflow events accepted and the outbox drained |
| Live Prometheus | Successfully scraped this API alongside the four other project APIs |
| Prometheus alert rules | promtool configuration and rule tests passed |
| Ruff and Bandit | Lint and medium/high-severity source checks passed |
| Python dependency audit | 18 resolved runtime packages checked with no known advisories returned |
| Deployment configuration | Compose and Kubernetes YAML and Grafana dashboard JSON parsed |

[Checks output](../reports/checks.txt) · [Replay results](../reports/replay.json) · [HTTP demo](../reports/http-demo.json) · [Runtime verification](../reports/verification.json) · [Dependency audit](../reports/dependency-audit.json)

[Actual model passing case](../reports/live-ready.json) · [Actual model held case](../reports/live-hold.json)

Model reports were produced by qwen2.5:0.5b through a local Ollama server. Scripted replay tests validate repeatable policies and failure cases. Real model runs verify the inference path separately.

## Deployment scope

Docker is unavailable on the development host, so the Compose stack and images need a container startup check. Grafana provisioning was checked as configuration. Its UI was not run. Kubernetes resources were parsed and reviewed without a cluster apply. No managed cloud resources were provisioned. Splunk HEC was exercised against the local contract receiver. Live vendor indexing and PagerDuty delivery remain separate integration checks.

The current GitHub credential has repo scope and lacks workflow scope. The CI file is supplied at docs/github-actions/ci.yml. To activate it, grant the workflow scope through the normal authentication flow, then copy the reviewed template to .github/workflows/ci.yml.

```sh
gh auth refresh -h github.com -s workflow
```

CI execution has not been claimed for this repository.
