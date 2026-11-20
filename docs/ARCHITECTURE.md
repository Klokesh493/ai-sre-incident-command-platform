# Architecture

## Domain data flow

```mermaid
flowchart TD
    SLO["Service request and error buckets"] --> Agent["AI evidence collection"]
    Logs["Splunk JSON export adapter"] --> Agent
    Coverage["On-call coverage intervals"] --> Agent
    Agent --> Correlate["Window completeness and integer burn math"]
    Correlate --> Owner["Unique active owner and matching logs"]
    Owner --> Review["Human approval"]
    Review --> Export["PagerDuty event payload bundle"]
```

Burn thresholds use integer cross-multiplication, preserving exact boundary behavior without floating-point drift. Coverage intervals include the start and exclude the end, so the handoff minute belongs to the next shift. Missing minutes and ambiguous coverage require review.

## API and persistence

```mermaid
sequenceDiagram
    participant User as Operator
    participant API as FastAPI
    participant AI as Bounded agent
    participant DB as SQLite
    participant HEC as Audit receiver
    User->>API: POST run with idempotency key
    API->>AI: Strict validated evidence case
    AI-->>API: Cited policy report
    API->>DB: Commit report and audit event atomically
    User->>API: Approve expected version 1
    API->>DB: Compare version and transition
    User->>API: Export expected version 2
    API->>DB: Record exported state
    User->>API: Retrieve bundle
    API-->>User: Domain output documents
    User->>API: Flush audit outbox
    API->>HEC: HEC event envelope
    HEC-->>API: Success code 0
    API->>DB: Mark receiver acceptance
```

Every workflow command checks the current version inside a BEGIN IMMEDIATE transaction. Competing requests with one idempotency key commit one report. Reusing that key with different input returns HTTP 409. Agent inference happens outside the transaction, so simultaneous retries can perform duplicate read-only model calls while persistence remains consistent.

The outbox offers at-least-once delivery. A crash after receiver acceptance and before the local acknowledgment can resend an event. Consumers can deduplicate by event ID. Reports and their input evidence are immutable after creation. Corrected evidence requires a new run.

## Trust boundaries

Pydantic validates request records before the model sees them. The agent receives evidence as data and can select only remaining probe names. Missing probes or invalid model responses prevent approval. Human approval exports documents for subsequent review. Kubernetes manifests are returned as text and remote infrastructure actions require an external operator or controller.

Metrics have bounded decision labels and contain no service identifiers. The audit sender exports workflow metadata. SQLite contains the full captured domain evidence and needs appropriate backup and access controls when real records are supplied.
