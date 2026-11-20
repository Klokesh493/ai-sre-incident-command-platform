"""API entry points for evidence collection and approval-controlled exports."""
from contextlib import asynccontextmanager
from dataclasses import dataclass
import hmac
import json
import logging
import os
from pathlib import Path
import re
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from . import domain
from .agent_loop import Ollama, Replay, investigate
from .storage import Conflict, Store
from .middleware import BodyLimitMiddleware

LOG = logging.getLogger("ops_platform")


@dataclass
class Settings:
    token: str
    database: str = "data/platform.sqlite3"
    model: str = "qwen2.5:0.5b"
    model_port: int = 11434
    hec_url: str = ""
    hec_token: str = ""
    model_host: str = "127.0.0.1"

    @classmethod
    def environment(cls):
        return cls(os.environ.get("OPS_API_TOKEN", ""),
                   os.environ.get("OPS_DATABASE", "data/platform.sqlite3"),
                   os.environ.get("OPS_MODEL", "qwen2.5:0.5b"),
                   int(os.environ.get("OPS_MODEL_PORT", "11434")),
                   os.environ.get("SPLUNK_HEC_URL", ""),
                   os.environ.get("SPLUNK_HEC_TOKEN", ""),
                   os.environ.get("OPS_MODEL_HOST", "127.0.0.1"))


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case: domain.Case
    mode: Literal["replay", "ollama"] = "replay"
    budget: int = Field(default=3, strict=True, ge=1, le=3)


class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(strict=True, ge=1)
    action: Literal["approve", "export"]


def evaluate(source, mode="replay", budget=3, model="qwen2.5:0.5b", port=11434, host="127.0.0.1"):
    case = domain.Case.model_validate(source)
    probes, decide = domain.prepare(case)
    planner = Ollama(model, port, host) if mode == "ollama" else Replay(domain.SOURCES)
    report = investigate(probes, set(domain.SOURCES), budget, planner, domain.BRIEF, decide)
    # A partial agent trace must never authorize an export.
    if report["stop"] != "evidence_complete":
        report["ready"] = False
    return report


def check_hec_url(url):
    parsed = urlsplit(url)
    local = parsed.hostname in {"127.0.0.1", "localhost", "hec-mock"}
    if (parsed.scheme != "https" and not (parsed.scheme == "http" and local)
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/services/collector/event"):
        raise ValueError("HEC requires HTTPS or local HTTP and the event collector path")


def flush_outbox(store, settings, client=None):
    """Return counts accepted by HEC. Failed events remain pending for retry."""
    import httpx

    check_hec_url(settings.hec_url)
    if not settings.hec_token:
        raise ValueError("SPLUNK_HEC_TOKEN is required")
    accepted = 0
    events = store.pending()
    with (client or httpx.Client(timeout=5, follow_redirects=False)) as transport:
        for event in events:
            try:
                result = transport.post(settings.hec_url,
                                        headers={"Authorization": "Splunk " + settings.hec_token},
                                        json={"sourcetype": "ops:audit", "event": event})
                result.raise_for_status()
                if result.json().get("code") != 0:
                    continue
            except (httpx.HTTPError, ValueError, AttributeError):
                continue
            store.delivered(event["id"])
            accepted += 1
    return {"accepted": accepted, "attempted": len(events), "pending": len(store.pending())}


def create_app(settings=None):
    settings = settings or Settings.environment()
    if len(settings.token) < 24 or settings.token.startswith("replace-"):
        raise ValueError("Set OPS_API_TOKEN to a randomly generated value of at least 24 characters")
    if not 1 <= settings.model_port <= 65535:
        raise ValueError("OPS_MODEL_PORT must be a valid TCP port")
    Ollama(settings.model, settings.model_port, settings.model_host)
    if settings.hec_url:
        check_hec_url(settings.hec_url)
    registry = CollectorRegistry()
    runs = Counter("ops_evaluations", "New evaluations", ["decision"], registry=registry)
    latency = Histogram("ops_evaluation_seconds", "Agent evaluation latency", registry=registry)

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(settings.database)
        yield

    app = FastAPI(title=domain.TITLE, version="1.0.0", lifespan=lifespan)
    app.state.settings = settings

    def authorize(authorization: str = Header(default="")):
        if not hmac.compare_digest(authorization, "Bearer " + settings.token):
            raise HTTPException(status_code=401, detail="valid bearer token required")

    app.add_middleware(BodyLimitMiddleware)

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/readyz")
    def readiness(request: Request):
        # Readiness includes the persistent store used by workflow operations.
        request.app.state.store.pending()
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return Response(json.dumps({"detail": str(exc)}), status_code=409,
                        media_type="application/json")

    @app.exception_handler(KeyError)
    async def missing_handler(request, exc):
        return Response('{"detail":"run not found"}', status_code=404,
                        media_type="application/json")

    @app.post("/v1/runs", dependencies=[Depends(authorize)])
    def start(payload: Evaluation, request: Request,
              idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=80)):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", idempotency_key):
            raise HTTPException(status_code=422, detail="invalid idempotency key")
        store = request.app.state.store
        source = payload.model_dump(mode="json")
        source["model"] = settings.model if payload.mode == "ollama" else None
        digest = store.digest(source)
        existing = store.find(idempotency_key, digest)
        if existing:
            return existing
        with latency.time():
            report = evaluate(source["case"], payload.mode, payload.budget,
                              settings.model, settings.model_port, settings.model_host)
        result = store.create(idempotency_key, digest, report)
        runs.labels(report["decision"]).inc()
        LOG.info(json.dumps({"event": "evaluation", "run_id": result["id"],
                             "decision": report["decision"]}))
        return result

    @app.get("/v1/runs/{run_id}", dependencies=[Depends(authorize)])
    def get(run_id: str, request: Request):
        return request.app.state.store.get(run_id)

    @app.post("/v1/runs/{run_id}/transitions", dependencies=[Depends(authorize)])
    def transition(run_id: str, payload: Transition, request: Request):
        return request.app.state.store.transition(run_id, payload.expected_version, payload.action)

    @app.get("/v1/runs/{run_id}/bundle", dependencies=[Depends(authorize)])
    def bundle(run_id: str, request: Request):
        run = request.app.state.store.get(run_id)
        if run["state"] != "exported":
            raise HTTPException(status_code=409, detail="approve and export this run first")
        return {"run_id": run_id, "files": domain.bundle(run["report"])}

    @app.post("/v1/integrations/splunk/flush", dependencies=[Depends(authorize)])
    def flush(request: Request):
        if not settings.hec_url or not settings.hec_token:
            raise HTTPException(status_code=503, detail="configure Splunk HEC before flushing")
        return flush_outbox(request.app.state.store, settings)

    return app


def main():
    import argparse

    parser = argparse.ArgumentParser(description=domain.BRIEF)
    parser.add_argument("case", type=Path)
    parser.add_argument("--mode", choices=["replay", "ollama"], default="replay")
    parser.add_argument("--model", default="qwen2.5:0.5b")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--host", choices=["127.0.0.1", "localhost", "ollama"], default="127.0.0.1")
    args = parser.parse_args()
    from .agent_loop import bounded_json
    result = evaluate(bounded_json(args.case), args.mode, model=args.model, port=args.port, host=args.host)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["stop"] == "evidence_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
