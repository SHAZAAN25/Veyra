# VEYRA — Reliability Model & Fault Tolerance Specification
## Stage 6 Reliability Engineering & Defensive Architecture

**Authoritative Root:** `<project-root>`  
**Document Status:** FROZEN & MANDATORY  
**Target Platform:** Windows 10 / Windows 11

---

## 1. Reliability Philosophy

VEYRA is built to run 24/7 in the background on end-user desktop machines without degrading performance, leaking memory, exhausting disk space, or corrupting state across sleep/wake cycles or unexpected system shutdowns.

The reliability architecture guarantees:
1. **Truthful State Recovery:** An interrupted operation is never falsely marked completed or successful.
2. **Graceful Degradation:** A failure in an optional subsystem (e.g. GPU collector, historical storage write) must never crash the core live telemetry loop.
3. **Bounded Execution:** Every external call, subprocess, lock acquisition, and database query has an explicit hard timeout.
4. **Clock Shift Immunity:** Durations and freshness calculations use monotonic time to eliminate vulnerabilities to wall-clock shifts, NTP syncs, or daylight saving transitions.

---

## 2. Failure Isolation Matrix

| Subsystem | Potential Failure Mode | Isolation Strategy & Defense | System Impact |
|---|---|---|---|
| **GPU Collector** | `nvidia-smi` missing, crashes, or hangs | Wrapped in safe subprocess with 3.0s timeout; caught in coordinator | GPU metrics marked `UNAVAILABLE`; CPU/RAM/Network unimpeded |
| **Network Probes** | Target unreachable, ICMP packet drop | Isolated probe threads; timeouts (3.0s); returns `AVAILABLE(None)` with 100% loss | Network reported degraded; application loop healthy |
| **Active Diagnostics** | Probe hangs, infinite traceroute | Asynchronous daemon worker with hard timeout & cancellation token | Diagnostics marked `FAILED` or `CANCELLED`; passive monitor unaffected |
| **SQLite Storage** | Disk full, database locked, corrupted file | SQLite `PRAGMA busy_timeout = 5000`; catch `DatabaseError`; switch to `STORAGE_DEGRADED` in RAM ring buffer | Live UI and monitoring remain 100% responsive |
| **Optimization Action** | Subprocess error, powercfg fails | `OptimizationExecutor` catches exception, marks run `FAILED`, attempts auto-rollback if applicable | OS left in verified pre-state; no crashes |
| **Localhost API** | Malformed HTTP request, rapid flood | Rate limiter drops excess; exception caught in route handler; returns 4xx/5xx JSON | Server continues serving; no process abort |

---

## 3. Concurrency & Deadlock Protection

1. **Optimization Concurrency Mutex (`OptimizationLock`):**
   - Optimization apply, verify, and rollback operations require an exclusive thread lock.
   - Any second optimization triggered while one is active immediately fails closed with `OptimizationConflictError`.
2. **Bounded Lock Waits:**
   - No thread is permitted to block indefinitely on a mutex. Lock acquisitions specify explicit timeouts (`timeout=5.0`).
3. **Database Concurrency:**
   - SQLite Write-Ahead Logging (WAL) mode enables concurrent readers while writes execute in serialized short transactions.
   - Busy timeout set to 5000ms.

---

## 4. Time Stability & Clock Jump Immunity

1. **Monotonic Clocks for Lifecycles:**
   - All durations, timeouts, stabilization windows, freshness calculations, and rate-limiting sliding windows use `time.monotonic()`.
   - Immune to system time changes, NTP adjustments, and Daylight Saving Time (DST) offsets.
2. **UTC Formatting for Display & Persistence:**
   - ISO 8601 UTC strings (`YYYY-MM-DDTHH:MM:SS.ffffffZ`) are strictly used for serialized storage timestamps to ensure chronological ordering.

---

## 5. Startup & Interrupted Operation Recovery

Upon application launch, the `OptimizationExecutor` runs `recover_interrupted_runs()`:
1. Queries storage for any optimization runs in non-terminal states (`APPLYING`, `SNAPSHOTTING`, `VERIFYING`, `ROLLING_BACK`).
2. Marks interrupted runs as `FAILED` or `ROLLBACK_REQUIRES_REVIEW` with descriptive crash recovery metadata.
3. Ensures that no incomplete run is mistakenly treated as verified or active.

---

## 6. Power Transitions & Sleep/Wake Handling

1. **Gap Detection:** The telemetry coordinator monitors elapsed monotonic time between cycles. If a gap > 15s is detected (indicating system sleep or hibernation), a `TIME_GAP_DETECTED` event is recorded.
2. **No False Incidents:** The incident evaluation engine ignores gap periods to avoid spuriously declaring packet loss or latency spikes due to system sleep.
3. **Gaming Session Finalization:** If a machine sleeps during an active gaming session, the session is closed cleanly with state `INTERRUPTED`.

---

## 7. Graceful Shutdown Protocol

When the application receives a termination signal (`SIGINT`, `SIGTERM`, or window close):
1. Stop telemetry coordinator and join background collector threads (max wait 2.0s).
2. Cancel any running active diagnostics and join diagnostic worker (max wait 2.0s).
3. Flush transient RAM measurement summaries to SQLite.
4. Close local API HTTP server cleanly.
5. Close SQLite database connection cleanly (`PRAGMA optimize` + WAL checkpoint).
