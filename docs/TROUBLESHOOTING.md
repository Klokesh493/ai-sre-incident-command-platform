# Troubleshooting

| Symptom | Check and response |
| --- | --- |
| API refuses startup | Generate OPS_API_TOKEN using tools/init_env.py and load .env in the current shell |
| HTTP 401 | Send Authorization with the same bearer credential used by the API |
| HTTP 409 on retry | Keep the original idempotency key for identical input and fetch the current workflow version |
| HTTP 409 on approval | Inspect ready, missing, blockers or review fields and create a corrected evaluation |
| HTTP 413 or 422 | Reduce the input size and inspect the strict API schema at /docs |
| model_error | Check Ollama, the local host allowlist, model installation and OPS_MODEL_PORT |
| Missing evidence | Use a budget of 3 and inspect the trace for rejected model actions |
| HEC events remain pending | Verify destination path, token, HTTPS trust and receiver code. Retry the flush after recovery |
| Dashboard has no series | Check the API /metrics endpoint and Prometheus targets, then create an evaluation |
| Kubernetes PVC stays Pending | Configure a default storage class or supply an appropriate persistent volume |
| Replica restart loses data | Confirm OPS_DATABASE points into the persistent volume and back up the SQLite database |

Use synthetic fixtures to reproduce a failure before changing production telemetry or policies. The domain report explains which gate held the request.
