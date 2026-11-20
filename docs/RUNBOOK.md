# Operations runbook

## Local API workflow

Create and load .env, install the development requirements, then start make serve. Open /docs for request schemas. Run python tools/http_demo.py to exercise the ready fixture through the entire API lifecycle.

1. Submit POST /v1/runs with an Idempotency-Key header and a case.
2. Inspect the decision, citations, trace and ready fields.
3. Approve through POST /v1/runs/{id}/transitions with action approve and expected_version 1.
4. Export through the same route with action export and expected_version 2.
5. Retrieve GET /v1/runs/{id}/bundle.
6. Review the returned documents before using them in another system.

Export records document generation. It does not establish that a remote deployment or operational action completed.

## Model runs

The CLI defaults to a scripted replay. Use --mode ollama for real model selection. API clients set mode to ollama in the request. Missing model responses and invalid tool choices leave the run in review. The model has at most three calls and cannot approve a run.

## Splunk audit delivery

For the local contract receiver, export MOCK_HEC_TOKEN from .env and start the following process in a separate terminal.

```sh
python -m uvicorn tools.hec_mock:create_app --factory --host 127.0.0.1 --port 18088
```

Before starting the API, set SPLUNK_HEC_URL=http://127.0.0.1:18088/services/collector/event and SPLUNK_HEC_TOKEN to the same local receiver token. The HTTP demo flushes the audit outbox. For a real receiver, configure its HTTPS event endpoint and a narrowly scoped HEC token. The SPL examples are in deploy/splunk-searches.spl.

A code 0 response marks acceptance. Indexing acknowledgment and real search verification are separate vendor checks. Delivery can repeat after a crash, so downstream consumers should deduplicate event.id.

## Observe

Inspect /healthz, /readyz and /metrics. In Compose, check Prometheus targets and the provisioned Grafana dashboard. Run promtool check rules deploy/prometheus/rules.yml and promtool test rules deploy/prometheus/rules.test.yml when promtool is installed.

## Kubernetes

Build an image with docker build -t ops-platform:local . and load it into the chosen local cluster. In the target namespace, create a Secret named ops-platform with the api-token key using your local generated credential. Apply deploy/kubernetes/workload.yaml after selecting a storage class. Use kubectl port-forward service/ops-platform 8000:8000 to reach the API locally.

The workload uses one replica and Recreate updates because SQLite and its volume have one writer deployment. The supplied Kubernetes path runs replay mode. A cluster Ollama endpoint and network policy require cluster-specific configuration before live AI calls.

## Recovery

Stop the API before copying the SQLite database for a simple local backup. A running-database backup should use SQLite's backup API so WAL contents remain consistent. Restore to a private volume, restart one replica, and fetch an existing run to verify persistence.

Retry a pending HEC flush after receiver recovery. For a held run, create a new evaluation with corrected evidence. Immutable report history preserves the reason the earlier decision was held.
