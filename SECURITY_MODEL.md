# VEYRA — Security Model & Architecture
## Stage 6 Security Hardening Specification

**Authoritative Root:** `<project-root>`  
**Document Status:** FROZEN & MANDATORY  
**Target Platform:** Windows 10 / Windows 11

---

## 1. Core Principles

1. **Local-First & Isolated:** VEYRA binds exclusively to `127.0.0.1`. Requests originating from any other address are dropped immediately.
2. **Least Privilege Process Model:** The primary VEYRA application and UI run strictly under standard user privileges. Elevated operations are isolated to a narrow, vetted helper with single-use authorization nonces.
3. **Defense-in-Depth & Fail Closed:** Every subsystem independently validates inputs, enforces timeouts, checks state, and denies unverified actions.
4. **Immutable Brand Identity:** Visual assets are locked by cryptographic SHA-256 manifests.

---

## 2. Privilege Architecture & Helper

```
+-----------------------------------------------------------+
|               Main VEYRA Process (Non-Admin)              |
|                                                           |
|  [ UI Screen ] -> [ User Approval Modal ]                |
|                          |                                |
|                          v                                |
|             [ Optimization Opportunity ]                  |
|                          |                                |
|                          v                                |
|             [ Privileged Authorization Token ]            |
|             - One-Time UUID Nonce                         |
|             - Operation ID from Allowlist                 |
|             - Validated Parameters                        |
|             - 60-Second TTL                               |
+--------------------------|--------------------------------+
                           |
                           v (Validated Request)
+-----------------------------------------------------------+
|           Narrow Privileged Helper (Isolated)            |
|                                                           |
|  1. Verify token & single-use nonce (Anti-Replay)         |
|  2. Check Operation ID against strict Allowlist           |
|  3. Validate parameter types, bounds, and schemes         |
|  4. Execute bounded Windows command (shell=False)         |
|  5. Relinquish privileges & return structured result      |
+-----------------------------------------------------------+
```

### Approved Privileged Operations Allowlist:
1. `OP_DNS_CACHE_FLUSH`: Clears Windows local DNS resolver cache (`ipconfig /flushdns`).
2. `OP_PROCESS_PRIORITY_HINT`: Modifies background worker process priority to idle/below-normal to relieve foreground contention.
3. `OP_POWER_SCHEME_TUNE`: Applies validated Windows power scheme GUID (High Performance / Balanced) via `powercfg`.

Any operation ID not in the allowlist results in immediate rejection (`DENY`).

---

## 3. Localhost API Security & Token Lifecycle

1. **Authentication Token:**
   - 256-bit cryptographically secure token (`secrets.token_urlsafe(32)`).
   - Stored in local file `.veyra_api_token` with user-only read/write access.
   - Header: `Authorization: Bearer <token>` or `X-Veyra-Token: <token>`.
   - Constant-time verification using `hmac.compare_digest`.
2. **Endpoint Authorization Levels:**
   - `READ_ONLY`: Public telemetry summary (`/api/v1/status`, `/api/v1/telemetry/current`).
   - `SENSITIVE_READ`: Historical logs, incidents, flight recorder (`/api/v1/history/*`). Requires authentication.
   - `MUTATING`: Configuration changes, mode switching (`/api/v1/config/*`). Requires authentication.
   - `PRIVILEGED`: System tuning, optimizations, diagnostics (`/api/v1/optimization/*`, `/api/v1/diagnostics/*`). Requires authentication, validated confirmation payload, and authorization nonce.
3. **DNS Rebinding Protection:**
   - `Host` header must strictly match `127.0.0.1`, `localhost`, or configured local port.
   - Any external or spoofed host header returns `403 Forbidden`.
4. **Rate Limiting & Payload Bounds:**
   - Sliding-window rate limiter per client IP.
   - Maximum request body size capped at 1 MB (`413 Payload Too Large`).

---

## 4. Subprocess Execution Security

1. `shell=False` is strictly enforced across all subprocess invocations.
2. Binary allowlist: Only approved binaries can be invoked (`ping`, `powershell.exe`, `netsh`, `ipconfig`, `systeminfo`, `powercfg`, `nvidia-smi`, `wmic`).
3. Argument validation: Shell metacharacters (`&`, `|`, `;`, `` ` ``, `$`, `>`, `<`, `\n`, `\r`) are rejected.
4. Execution timeouts: Hard limits on every call (default 3.0s to 10.0s).
5. Output bounds: Stdout and stderr capped at 64 KB to eliminate buffer exhaustion.

---

## 5. Storage Security & Resilience

1. SQLite WAL mode with parameterized queries exclusively. Zero string concatenation.
2. Startup integrity validation via `PRAGMA integrity_check`.
3. Database corruption fallback: If SQLite encounters unrecoverable corruption or read-only filesystem errors, the storage layer transitions gracefully to `STORAGE_DEGRADED` in memory, emitting critical telemetry while keeping live PC monitoring active.

---

## 6. Optimization Snapshot Integrity & Replay Protection

1. Snapshots are cryptographically signed with HMAC-SHA256 upon creation.
2. Before any rollback action is permitted, the snapshot HMAC is verified against current stored data.
3. Pre-rollback verification compares current system state to expected post-change state. If external modifications have occurred, the rollback is suspended with `ROLLBACK_REQUIRES_REVIEW`.
4. Process-wide `OptimizationLock` prevents concurrent optimizations or racing experiments.
