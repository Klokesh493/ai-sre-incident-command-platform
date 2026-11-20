"""Exercise evaluate, retry, approve, export, and audit delivery through a running API."""
import json
import os
from pathlib import Path

import httpx

def main():
    root = Path(__file__).resolve().parents[1]
    token = os.environ["OPS_API_TOKEN"]
    base = os.environ.get("OPS_URL", "http://127.0.0.1:8000")
    mode = os.environ.get("DEMO_MODE", "replay")
    payload = {"case": json.loads((root / "examples/ready.json").read_text()), "mode": mode}
    import uuid
    key = str(uuid.uuid4())
    headers = {"Authorization": "Bearer " + token, "Idempotency-Key": key}
    with httpx.Client(base_url=base, headers=headers, timeout=180) as client:
        first = client.post("/v1/runs", json=payload)
        first.raise_for_status()
        run = first.json()
        retry = client.post("/v1/runs", json=payload)
        retry.raise_for_status()
        assert run["id"] == retry.json()["id"]
        for version, action in ((1, "approve"), (2, "export")):
            response = client.post(f"/v1/runs/{run['id']}/transitions",
                                   json={"expected_version": version, "action": action})
            response.raise_for_status()
        bundle = client.get(f"/v1/runs/{run['id']}/bundle")
        bundle.raise_for_status()
        audit = client.post("/v1/integrations/splunk/flush")
        if audit.status_code not in {200, 503}:
            audit.raise_for_status()
        print(json.dumps({"decision": run["report"]["decision"],
                          "state": "exported", "mode": mode,
                          "files": sorted(bundle.json()["files"]),
                          "hec": audit.json()}, indent=2))

if __name__ == "__main__":
    main()
