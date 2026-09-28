# VEYRA — Security Threat Model
## Stage 6 Security, Privacy & Reliability Hardening

**Authoritative Root:** `<project-root>`  
**Document Status:** FROZEN & MANDATORY  
**Target Operating Environment:** Windows 10/11 Desktop (Local-First Engine)

---

## 1. System Overview & Security Philosophy

VEYRA operates strictly as a local-first Windows observability, diagnostics, and evidence-grounded optimization platform. 

The security posture adheres to the following non-negotiable principles:
1. **Zero Trust Between Subsystems:** No component implicitly trusts data from another component (UI, API, collectors, diagnostics, storage).
2. **Least Privilege:** VEYRA runs as a standard, non-administrative user process. Operations requiring elevation are strictly bounded and executed through an isolated helper with one-time authorization tokens.
3. **Fail-Closed Policy:** Any unauthenticated, unrecognized, or ambiguous operation is denied (`DENY`).
4. **Zero Cloud Exfiltration:** Telemetry, logs, snapshots, and user data remain on the local machine; zero external API keys or remote cloud servers are ever utilized.
5. **No Blind Trust in Localhost:** Requests originating from `127.0.0.1` must authenticate with cryptographically secure tokens.

---

## 2. Identified Assets

| Asset ID | Asset Name | Description | Sensitivity | Integrity Criticality |
|---|---|---|---|---|
| **A-01** | Telemetry Stream | Real-time hardware, network, and system measurements | Medium | High (Must never be fabricated) |
| **A-02** | Historical Summaries | 1-min to 1-day SQLite rollups | Low | High (Historical ground truth) |
| **A-03** | Incidents & Flight Recorder | Incident records, pre/during/after snapshots | Medium | High (Privacy sanitized) |
| **A-04** | Personal PC Baselines | Statistical baseline metrics per hour/day | Low | High (Must prevent contamination) |
| **A-05** | Optimization Snapshots | Pre-change subsystem configurations | High | Critical (Enables safe rollback) |
| **A-06** | Optimization State Machine | Active lifecycle state of optimization runs | Medium | Critical (Controls system tuning) |
| **A-07** | Gaming Profiles & Sessions | Configured profiles and Session DNA records | Low | Medium |
| **A-08** | Diagnostic Reports & Evidence | Cross-layer diagnostic results | Low | High |
| **A-09** | Configuration | User preferences, intervals, storage limits | Medium | High (Integrity validated) |
| **A-10** | Localhost API Tokens | Cryptographic Bearer tokens for localhost API | Critical | Critical (Access gatekeeper) |
| **A-11** | Privileged Operations | Narrow system commands (DNS flush, powercfg) | High | Critical (OS integrity barrier) |

---

## 3. Threat Actors

1. **TA-1: Malicious Local Application** — An unprivileged program running under the same or another user account attempting to abuse VEYRA's local API or trigger unapproved optimizations.
2. **TA-2: Rogue Web Page (DNS Rebinding / Localhost Fetch)** — A web browser tab attempting to send cross-origin requests to `http://127.0.0.1:8765` to exfiltrate telemetry or execute commands.
3. **TA-3: Malicious Configuration Injection** — A modified or corrupted `config.json` designed to invoke arbitrary binaries, cause path traversal, or force external network binding.
4. **TA-4: Path Traversal / Malicious Filename** — Input containing `../`, null bytes, or alternate data streams intended to write or read outside designated application directories.
5. **TA-5: Compromised Dependency / Supply Chain** — Vulnerabilities or malicious code introduced through third-party Python packages.
6. **TA-6: Accidental User Misuse / Double-Clicking** — User rapidly clicking actions, modifying files out-of-band, or terminating processes mid-optimization.
7. **TA-7: Storage Corruption / Interrupted Write** — Sudden power loss, blue screens, or disk-full conditions leaving SQLite in an inconsistent state.
8. **TA-8: Race Condition / Concurrency Attacker** — Concurrent requests attempting to execute contradictory optimizations or corrupt pre-change snapshots.
9. **TA-9: Privilege Escalation Attacker** — Malicious caller attempting to abuse VEYRA's privileged helper to execute arbitrary commands as Administrator.
10. **TA-10: Telemetry / AI Prompt Injector** — Adversarial strings injected via process names, Wi-Fi SSIDs, or DNS responses designed to alter AI reasoning or compromise logging.

---

## 4. Threat Matrix & Defense Strategy

| Threat ID | Targeted Asset | Attack Vector & Description | Impact | Likelihood | Mitigation Controls | Verification Test | Residual Risk |
|---|---|---|---|---|---|---|---|
| **T-01** | Local API / Telemetry | Cross-origin browser script or local script accesses localhost API without credentials. | High | High | Cryptographically strong 256-bit API token; `Host` header validation (`127.0.0.1`/`localhost`); constant-time comparison. | `test_api_token_authentication_required`, `test_host_header_dns_rebinding_defense` | Negligible |
| **T-02** | Privileged Helper / OS | Malicious request supplies arbitrary command to privileged helper to gain admin rights. | Critical | Medium | Narrow allowlist of fixed operations (`OP_DNS_CACHE_FLUSH`, `OP_PROCESS_PRIORITY_HINT`, `OP_POWER_SCHEME_TUNE`); rejects arbitrary paths/commands; one-time authorization tokens. | `test_privileged_helper_denies_unknown_operation`, `test_privileged_helper_rejects_arbitrary_commands` | Negligible |
| **T-03** | Subprocess Execution | Malicious process name or diagnostic target injects shell metacharacters (`&`, `\|`, `;`). | High | Medium | `shell=False` strictly enforced; argument lists; allowlist of approved executables; input regex validation; 64KB output cap. | `test_subprocess_shell_injection_prevented`, `test_subprocess_unknown_executable_denied` | Low |
| **T-04** | File System / Storage | Export or snapshot path contains `../../` or absolute path escaping sandbox. | High | Medium | Canonical path resolution (`os.path.realpath`, `os.path.commonpath`); rejects `..`, null bytes, UNC paths, and colons. | `test_path_traversal_directory_escape_rejected`, `test_null_byte_path_rejected` | Negligible |
| **T-05** | Optimization Snapshots | Stale or tampered snapshot applied during rollback, corrupting system state. | Critical | Low | HMAC-SHA256 snapshot signing; pre-rollback state verification; transition to `ROLLBACK_REQUIRES_REVIEW` on mismatch. | `test_snapshot_tamper_detection`, `test_rollback_state_mismatch_requires_review` | Negligible |
| **T-06** | System Optimization | Concurrent optimization requests execute simultaneously, causing race conditions. | High | Medium | Process-wide `OptimizationLock`; rejects concurrent optimization attempts with `OptimizationConflictError`. | `test_concurrent_optimization_conflict_rejected` | Negligible |
| **T-07** | Localhost API | Request flooding / brute-force attacks against API or diagnostic triggers. | Medium | Medium | Sliding-window `ApiRateLimiter` per IP and endpoint; max request body size limited to 1 MB. | `test_api_rate_limiter_throttles_bursts`, `test_oversized_payload_rejected` | Low |
| **T-08** | Flight Recorder / Logs | Sensitive credentials, tokens, or private keys logged or saved in snapshots. | High | Medium | Centralized `SecretScanner` with keyword & entropy matching; automated redaction (`[REDACTED]`); log newline injection stripping. | `test_centralized_secret_scanner_redaction`, `test_log_injection_sanitization` | Low |
| **T-09** | SQLite Storage | Database corrupted by crash or disk-full condition during active write. | Medium | Medium | SQLite WAL mode; `PRAGMA busy_timeout = 5000`; startup `integrity_check`; graceful fallback to `STORAGE_DEGRADED` in RAM. | `test_database_corruption_graceful_degradation`, `test_disk_full_storage_pressure_handled` | Low |
| **T-10** | Ask Veyra / AI | Malicious process name injects instructions to execute commands or override reasoning. | Medium | Low | Telemetry wrapped in untrusted data delimiters; AI engine has ZERO execution capabilities; deterministic rules ground all responses. | `test_ai_prompt_injection_boundary`, `test_ai_action_isolation` | Negligible |

---

## 5. Trust Boundaries

```
[ UNTRUSTED WORLD / OS NETWORK / WEB ]
                 │
                 ▼ (Filtered ICMP / DNS / Process Metadata)
     [ LOCAL PROCESS ENVIRONMENT ]
                 │
  ┌──────────────┴──────────────┐
  │ Localhost API (Token Auth)  │
  └──────────────┬──────────────┘
                 │
                 ▼ (Validated Envelopes & Strict Nonces)
      [ VEYRA APPLICATION CORE ]
        │         │          │
        ▼         ▼          ▼
   [COLLECTORS] [STORAGE] [DIAGNOSTICS]
        │         │          │
        └─────────┼──────────┘
                  │
                  ▼ (One-Time Token & Narrow Allowlist)
        [ PRIVILEGED HELPER ]
                  │
                  ▼
         [ WINDOWS OS / KERNEL ]
```

---

## 6. Summary of Residual Risk

All high-impact attack vectors (arbitrary command execution, privilege abuse, unauthenticated localhost exploitation, path traversal, snapshot tampering, and credential leakage) are mitigated through active, automated defenses and verified by negative tests. Residual risks are limited to operating-system-level physical machine compromise, which is outside VEYRA's threat boundary.
