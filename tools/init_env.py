"""Create private local development credentials without replacing existing files."""
import os
from pathlib import Path
import secrets

destination = Path(".env")
try:
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
except FileExistsError:
    raise SystemExit(".env already exists; reuse it or edit it explicitly")
with os.fdopen(descriptor, "w") as target:
    for name in ("OPS_API_TOKEN", "MOCK_HEC_TOKEN", "GRAFANA_ADMIN_PASSWORD"):
        target.write(name + "=" + secrets.token_urlsafe(32) + "\n")
    target.write("OPS_MODEL=qwen2.5:0.5b\n")
print("Created .env with private permissions")
