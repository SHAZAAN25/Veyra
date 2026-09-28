# VEYRA — Backend / UI API Contract

> **Contract Version:** 1.0.0  
> **Network Protocol:** HTTP REST + WebSocket (Localhost only)  
> **Binding:** `127.0.0.1` (Strictly prohibited: `0.0.0.0`)

---

## 1. Architectural Guardrails

The API provides the clean boundary between the VEYRA telemetry engine and presentation interfaces (Desktop GUI, Web/Overlay view).

1. **Localhost Exclusivity:** The API server binds exclusively to `127.0.0.1`. Requests originating from any other address are refused.
2. **State Exposure Only:** The API exposes verified, real application state. The API accepts NO endpoints allowing the UI or external callers to inject, fabricate, or overwrite telemetry metrics.
3. **No Arbitrary Command Execution:** The API provides only whitelisted, strictly bounded diagnostic triggers (`/api/v1/diagnostics/ping`, `/api/v1/diagnostics/traceroute`). Arbitrary command strings cannot be passed via the API.

---

## 2. Standard Response Envelope

All API endpoints return a standardized JSON envelope:

```json
{
  "status": "success",
  "data": { ... },
  "error": null,
  "timestamp_utc": "2026-09-28T15:30:00.000Z",
  "server_version": "0.1.0"
}
```

### Error Envelope

When an error occurs, HTTP status codes reflect the nature of the error (e.g., 400 for bad parameters, 503 for collector unavailable), and the payload provides typed error diagnostics:

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "COLLECTOR_UNAVAILABLE",
    "message": "Wi-Fi interface is currently disconnected or in airplane mode.",
    "details": {
      "interface": "Wi-Fi",
      "required_state": "CONNECTED"
    }
  },
  "timestamp_utc": "2026-09-28T15:30:00.000Z",
  "server_version": "0.1.0"
}
```

---

## 3. Core Planned Endpoints

### A. Real-Time Telemetry
- **`GET /api/v1/telemetry/current`**  
  Returns the most recent verified `Observation`, including all metric states, values, and freshness timestamps.
- **`GET /api/v1/telemetry/assessment`**  
  Returns the latest health assessment, stability score, and active alerts.
- **`WS /api/v1/telemetry/stream`**  
  WebSocket stream emitting live observations at the configured polling frequency (e.g. 2s in Normal Mode, 500ms in Gaming Mode).

### B. Historical Analytics
- **`GET /api/v1/history/summaries?metric={name}&range={24h|7d|30d}`**  
  Returns bucketed historical aggregations from SQLite for time-series chart rendering.
- **`GET /api/v1/history/incidents?limit=50`**  
  Returns recent incident records and root-cause summaries.

### C. Active Diagnostics
- **`POST /api/v1/diagnostics/run`**  
  Triggers a bounded diagnostic routine. Body: `{"tool": "traceroute", "target": "1.1.1.1"}`. Returns execution ID and runs asynchronously with execution timeouts.

### D. Preferences & Modes
- **`GET /api/v1/config`**  
  Returns current non-sensitive preferences (UI theme, mode, intervals).
- **`POST /api/v1/config/mode`**  
  Switches operational mode between `"normal"` and `"gaming"`. Requires zero application restart.

### E. Stage 5 Diagnostics, Gaming & Optimization Endpoints
- **`POST /api/v1/diagnostics/investigate`**  
  Runs a comprehensive cross-layer diagnostic investigation asynchronously, returning a run ID and graph node assessments.
- **`GET /api/v1/diagnostics/history`**  
  Returns historical diagnostic runs and individual probe results.
- **`GET /api/v1/gaming/session/current`**  
  Returns the active gaming session state, detected game, and live Session DNA.
- **`GET /api/v1/gaming/sessions`**  
  Returns historical gaming sessions and DNA summaries.
- **`GET /api/v1/optimization/opportunities`**  
  Returns active, evidence-backed optimization candidates with risk level and rollback plans.
- **`POST /api/v1/optimization/apply`**  
  Applies an approved optimization. Requires explicit confirmation payload: `{"opportunity_id": "...", "confirmed_by_user": true}`.
- **`POST /api/v1/optimization/rollback`**  
  Triggers a deterministic rollback of an active or regressed optimization run.
- **`POST /api/v1/ai/explain`**  
  Generates a structured, evidence-grounded Explain My PC report.
- **`POST /api/v1/ai/ask`**  
  Submits a question to Ask Veyra. Body: `{"question": "..."}`. Returns deterministic response with citations to local evidence.

---

## 4. Stage 6 Localhost API Security & Authentication Contract

### A. Zero Trust & Loopback Isolation
- The server binds strictly to loopback (`127.0.0.1`). Configuration attempts to bind to `0.0.0.0` or external network adapters are strictly rejected.
- **DNS Rebinding Defense:** The HTTP request `Host` header is validated against loopback values (`127.0.0.1`, `localhost`). Non-local `Host` headers are rejected with `403 Forbidden`.

### B. Bearer Token Lifecycle & Constant-Time Verification
- Authentication uses a 256-bit cryptographically secure random token (`secrets.token_urlsafe(32)`).
- Verification uses `hmac.compare_digest` to prevent timing attacks.
- Tokens are stored in a restricted local file (`.api_token` with `0600` permissions).
- Supports token rotation and revocation. Missing or corrupt tokens fail closed.

### C. Tiered Authorization Matrix
- **`READ_ONLY`:** Open for local read endpoints (`/api/v1/status`, `/api/v1/telemetry/current`, `/api/v1/telemetry/assessment`, `/api/v1/config`, `/api/v1/history/*`).
- **`SENSITIVE_READ`:** Requires Bearer token authentication (`/api/v1/gaming/*`).
- **`MUTATING`:** Requires Bearer token authentication and user authorization (`/api/v1/config/mode`, `/api/v1/diagnostics/*`, `/api/v1/ai/*`).
- **`PRIVILEGED`:** Requires Bearer token authentication, user confirmation payload, and operation authorization (`/api/v1/optimization/apply`, `/api/v1/optimization/rollback`).

### D. Request Bounds & Rate Limiting
- **Payload Size Bound:** Request bodies exceeding 1 MB are terminated with `413 Payload Too Large`.
- **Sliding-Window Rate Limiting:** Enforces maximum request thresholds (e.g. 5 requests/min for mutating actions, 60 requests/min for general read endpoints). Exceeding requests receive `429 Too Many Requests`.

### E. Safe Error Responses
- Errors follow standard envelopes: `{"success": false, "error": {"code": "...", "message": "..."}}`.
- Internal tracebacks, filesystem paths, and environment details are scrubbed from public envelopes.


