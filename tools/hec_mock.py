"""Small HEC protocol receiver for local contract testing."""
import hmac
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict

class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourcetype: str
    event: dict


def create_app():
    token = os.environ.get("MOCK_HEC_TOKEN", "")
    if len(token) < 24:
        raise ValueError("MOCK_HEC_TOKEN must contain at least 24 characters")
    app = FastAPI(title="Local Splunk HEC contract receiver")
    seen = set()

    @app.post("/services/collector/event")
    def receive(payload: Envelope, authorization: str = Header(default="")):
        if not hmac.compare_digest(authorization, "Splunk " + token):
            raise HTTPException(status_code=401)
        seen.add(payload.event["id"])
        return {"text": "Success", "code": 0}

    @app.get("/received")
    def received(authorization: str = Header(default="")):
        if not hmac.compare_digest(authorization, "Splunk " + token):
            raise HTTPException(status_code=401)
        return {"unique_events": len(seen)}

    return app
