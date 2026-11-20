"""Transactional reports, optimistic workflow transitions, and audit outbox."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid


class Conflict(Exception):
    """The command conflicts with an existing request or workflow version."""


class Store:
    def __init__(self, filename):
        self.filename = str(filename)
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                    request_hash TEXT NOT NULL, state TEXT NOT NULL,
                    version INTEGER NOT NULL, report TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
                    kind TEXT NOT NULL, version INTEGER NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(run_id, version)
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.filename, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def digest(payload):
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def decode(row):
        return {"id": row["id"], "state": row["state"], "version": row["version"],
                "report": json.loads(row["report"])}

    def find(self, request_key, request_hash):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE request_key=?", (request_key,)).fetchone()
            if row and row["request_hash"] != request_hash:
                raise Conflict("idempotency key already belongs to a different request")
            return self.decode(row) if row else None

    def create(self, request_key, request_hash, report):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE request_key=?", (request_key,)).fetchone()
            if row:
                if row["request_hash"] != request_hash:
                    raise Conflict("idempotency key already belongs to a different request")
                return self.decode(row)
            run_id = str(uuid.uuid4())
            state = "evaluated"
            db.execute("INSERT INTO runs VALUES (?, ?, ?, ?, 1, ?)",
                       (run_id, request_key, request_hash, state, json.dumps(report, allow_nan=False)))
            db.execute("INSERT INTO events(id,run_id,kind,version) VALUES (?,?,'evaluated',1)",
                       (str(uuid.uuid4()), run_id))
            return {"id": run_id, "state": state, "version": 1, "report": report}

    def get(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            return self.decode(row)

    def transition(self, run_id, expected_version, action):
        transitions = {"approve": ("evaluated", "approved"), "export": ("approved", "exported")}
        origin, target = transitions[action]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            report = json.loads(row["report"])
            if row["version"] != expected_version or row["state"] != origin:
                raise Conflict("workflow changed; fetch the current version before retrying")
            if report["stop"] != "evidence_complete" or not report["ready"]:
                raise Conflict("policy requires review; create a new evaluation with corrected evidence")
            db.execute("UPDATE runs SET state=?,version=version+1 WHERE id=?", (target, run_id))
            db.execute("INSERT INTO events(id,run_id,kind,version) VALUES (?,?,?,?)",
                       (str(uuid.uuid4()), run_id, target, expected_version + 1))
        return self.get(run_id)

    def pending(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,run_id,kind,version FROM events WHERE delivered=0 ORDER BY rowid LIMIT 100")]

    def delivered(self, event_id):
        with self.connect() as db:
            db.execute("UPDATE events SET delivered=1 WHERE id=?", (event_id,))
