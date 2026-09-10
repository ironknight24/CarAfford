# CarAfford Observability, Monitoring & Health Probes

This guide details the monitoring, telemetry, correlation tracking, and logging architecture of the **CarAfford** application.

---

## 1. Health Probes

CarAfford provides structured health check endpoints compliant with standard Kubernetes, AWS ECS, GCP Cloud Run, and Docker healthcheck contracts.

### Endpoints

| Endpoint | Method | Response | Status Codes | Usage |
| :--- | :--- | :--- | :--- | :--- |
| `/health/live` | `GET` | `{"status": "alive", "timestamp": "..."}` | `200` | Liveness probe: verifies process is responding. |
| `/health/ready` | `GET` | `{"status": "ready", "checks": {"database": "healthy", "redis": "healthy"}}` | `200` (Ready), `503` (Degraded) | Readiness probe: validates downstream connectivity before routing traffic. |
| `/health/metrics` | `GET` | `{"status": "ok", "version": "1.0.0", "system": {...}}` | `200` | System metrics, memory usage, and application statistics. |

---

## 2. Request Correlation & Distributed Tracing

Every inbound request is assigned a unique `X-Request-ID` UUID:
- If the incoming client supplies an `X-Request-ID` header, the backend honors and propagates it.
- If missing, the backend generates a new `UUIDv4`.
- The Request ID is injected into every response header, log entry, and error response payload.

### Standardized Error Payload Example

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Invalid loan tenure specified.",
    "request_id": "c7f6984e-3c22-48df-b59a-8e2b86bb8468",
    "details": null
  }
}
```

---

## 3. Structured Logging

Application logs use standard structured formatting:
```text
2026-09-10 00:45:12,345 [INFO] [carafford] Initializing CarAfford in [PRODUCTION] environment...
2026-09-10 00:45:14,789 [INFO] [carafford] Database migrations up to date.
```
All fatal exceptions and unhandled 500 errors log tracebacks with associated Request IDs for rapid triage in Datadog, CloudWatch, or ELK stacks.
