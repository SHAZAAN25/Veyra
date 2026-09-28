# VEYRA — System Architecture Specification

> **Architecture Status:** FROZEN  
> **Target Platform:** Windows (Local-First Desktop Engine)

---

## 1. System Philosophy & Pipeline

VEYRA is a high-precision, real-time desktop telemetry and diagnostics platform designed for local network and system observability.

The architecture enforces a strict unidirectional pipeline:

```
[ HARDWARE / OS / NETWORK ]
              │
              ▼ (Real Execution Only)
       [ COLLECTORS ]
              │
              ▼ (Atomic Observations)
        [ ANALYZER ]
         │        │
         │        ▼ (Degradation / Anomaly Events)
         │  [ INCIDENTS ]
         ▼
     [ STORAGE ] ◄── (RAM Buffer ──► Compact SQLite Rollups)
         │
         ▼ (State Exposure)
       [ API ]   (Localhost Only: 127.0.0.1)
         │
         ▼ (Presentation Layer)
       [  UI  ]
```

---

## 2. Component Boundaries & Responsibilities

| Component | Responsibility | Boundary Restrictions |
|---|---|---|
| **Collectors** (`collectors/`) | Collect real hardware, network, and system measurements. | NEVER fabricate data. NEVER present UI. NEVER evaluate thresholds or trigger alerts. |
| **Analyzer** (`analyzer/`) | Evaluates verified observations, calculates health scores, detects anomalies. | Operates ONLY on verified observations from collectors. NEVER executes system commands directly. |
| **Storage** (`storage/`) | Manages fast RAM buffer and compact historical rollups in SQLite. | NEVER stores continuous raw telemetry permanently. NEVER contains UI or presentation logic. |
| **API** (`app/api/`) | Exposes application state, historical metrics, and triggers diagnostics. | Binds strictly to `127.0.0.1`. Validates all requests. Read-only for telemetry state. |
| **UI** (`app/ui/`) | Renders metrics, graphs, incidents, and mode switching (Normal/Gaming). | Strictly presentation. MUST NEVER execute shell commands, run ping loops, or act as the monitoring engine. |
| **Diagnostics** (`diagnostics/`) | Performs on-demand, explicit diagnostic routines (traceroute, DNS test). | Executed strictly on user demand or explicit trigger. Strictly bounded by execution timeouts. |

---

## 3. Dependency Direction

Dependencies flow strictly inward:

- `UI` depends on `API` (HTTP / WebSocket).
- `API` depends on `Analyzer`, `Storage`, and `Diagnostics`.
- `Analyzer` depends on `contracts` and verified `Observations`.
- `Storage` depends on `contracts`.
- `Collectors` depend on `contracts` and safe OS execution utilities (`app/core/security.py`).
- Foundational core (`app/core/`) has **ZERO** dependencies on collectors, storage, or UI.

---

## 4. Frozen Directory Structure

```
<project-root>
│
├── app/                  # Application core, API, and UI presentation
│   ├── core/             # Contracts, branding integrity, security, logging, time, config
│   ├── api/              # Localhost API endpoints (Stage 4)
│   └── ui/               # Desktop UI & renderer (Stage 4)
├── collectors/           # Hardware, system, and network collectors (Stage 1)
├── analyzer/             # Telemetry assessment, incident intelligence, and baseline engines (Stage 2)
├── storage/              # RAM buffer and compact SQLite rollups (Stage 3)
├── diagnostics/          # On-demand diagnostic runners (Stage 5)
├── tests/                # Automated unit, integration, and contract tests
├── config/               # Configuration defaults and profiles
├── assets/
│   └── branding/         # Locked branding assets and branding_manifest.json
│       ├── normal/       # Locked Cyan assets (Normal Mode)
│       └── gaming/       # Locked Crimson assets (Gaming Mode)
├── run.py                # Main application entry point
├── requirements.txt      # Disciplined dependencies
├── PROJECT_RULES.md      # Non-negotiable project rules
├── ARCHITECTURE.md       # Frozen architecture specification
├── DATA_CONTRACT.md      # Telemetry lifecycle and integrity contract
├── MEASUREMENT_CONTRACT.md # Collector measurement specifications
├── STORAGE_CONTRACT.md   # Compaction and retention specification
├── API_CONTRACT.md       # Localhost REST & WebSocket API specification
├── UI_DESIGN_SYSTEM.md   # Locked design system and palette tokens
├── TEST_STRATEGY.md      # Test pyramid and validation strategy
├── CONTRIBUTING.md          # Contributor guidelines and workflow
└── .gitignore            # Git exclusions
```

---

## 5. Architectural Invariants

1. **Localhost Isolation:** The application binds strictly to loopback (`127.0.0.1`). Network exposure via `0.0.0.0` is prohibited by configuration validation and security tests.
2. **Safe Command Execution:** All external subprocess invocations use strict list arguments, `shell=False`, and hard execution timeouts to eliminate command injection risks.
3. **Immutability of Brand Identity:** Official branding assets under `assets/branding/` are locked by SHA-256 digests recorded in `branding_manifest.json` and checked during startup and testing.
4. **Zero Fabrication:** Never fabricate telemetry, synthetic FPS, or simulated sensor temperatures. Missing or unsupported data is explicitly marked `Unavailable` or `Unsupported`.
5. **Safe Reversible Optimization:** All optimization candidates are evidence-backed, require explicit user confirmation, snapshot before change, statistically verify outcomes, and automatically roll back on sustained regression.
6. **Local Deterministic AI:** Explain My PC and Ask Veyra operate 100% locally on structured deterministic evidence packages without external cloud API dependencies or keys.

---

## 6. Stage 5 Architecture Extensions

### 6.1 Advanced Diagnostics (`diagnostics/`)
- `diagnostics/contracts.py`: Diagnostic layers, probe results, cross-layer graph nodes, and diagnostic reports.
- `diagnostics/probes.py`: Controlled execution probes for System, Adapter, Wi-Fi, Gateway, DNS, and Internet layers.
- `diagnostics/investigator.py`: `CrossLayerInvestigator` evaluating topology nodes and determining root causes with deterministic confidence.
- `diagnostics/runner.py`: `DiagnosticRunner` managing asynchronous probe execution, timeout boundaries, cancellation, and SQLite persistence.

### 6.2 Hardware Bottleneck Investigation (`analyzer/bottleneck/`)
- `analyzer/bottleneck/investigator.py`: `BottleneckInvestigator` analyzing CPU pressure, GPU limits, RAM/VRAM pressure, storage saturation, thermal limitations (only from genuine sensors), and background workload interference.

### 6.3 Gaming Intelligence & Session DNA (`analyzer/gaming/`)
- `analyzer/gaming/contracts.py`: Game identities, gaming session lifecycle states, ratings, and `GamingSessionDNA`.
- `analyzer/gaming/detector.py`: `GameDetector` identifying active game processes from running process metadata.
- `analyzer/gaming/session_engine.py`: `GamingSessionEngine` tracking session state machines, circular telemetry buffers, and generating deterministic Session DNA without synthetic FPS.
- `analyzer/gaming/profile_manager.py`: `GameProfileManager` managing game-specific performance baselines and target configurations.

### 6.4 Safe Optimization Engine & Automatic Rollback Guardian (`optimization/`)
- `optimization/contracts.py`: Optimization states, opportunity models, pre-change snapshot definitions, and verification criteria.
- `optimization/snapshots.py`: `SnapshotManager` capturing pre-change configuration with strict privacy rejection for secrets/tokens.
- `optimization/actions.py`: Concrete, reversible system actions (DNS flush, process priority hints, power scheme adjustments).
- `optimization/opportunities.py`: `OptimizationOpportunityEngine` generating evidence-backed optimization recommendations.
- `optimization/verification.py`: `VerificationEngine` executing statistical pre- vs post-change verification with stabilization windows.
- `optimization/rollback_guardian.py`: `AutomaticRollbackGuardian` triggering deterministic rollback on verified performance regression.
- `optimization/ab_testing.py`: `OptimizationABTestingEngine` comparing baseline window A against test window B while detecting confounders (e.g., workload shifts).
- `optimization/executor.py`: `OptimizationExecutor` orchestrating user approval, snapshotting, execution, verification, rollback, and startup crash recovery.

### 6.5 Explain My PC & Ask Veyra (`analyzer/ai/`)
- `analyzer/ai/contracts.py`: AI response classifications, structured citations, and evidence packages.
- `analyzer/ai/explain_my_pc.py`: `ExplainMyPCEngine` synthesizing telemetry, baselines, incidents, bottlenecks, and timeline events into clear, structured explanations.
- `analyzer/ai/ask_veyra.py`: `AskVeyraEngine` providing deterministic question answering grounded strictly in Veyra's local measurement data without hallucinations or cloud dependencies.

---

## 7. Stage 6 Security, Privacy, Privilege & Reliability Architecture

### 7.1 Least-Privilege Separation Architecture (`app/core/privilege.py`)
- **Non-Elevated Execution:** The main VEYRA GUI and telemetry services execute as standard, unprivileged desktop processes.
- **Narrow Privileged Helper:** Privileged actions are isolated to `PrivilegedHelper`, executing only allowlisted operations (`PrivilegedOperationAllowlist`).
- **Cryptographic Anti-Replay Tokens:** Every privileged request requires a `PrivilegeAuthorizationToken` containing an operation ID, unique UUID nonce, caller PID validation, parameter hash, and a 60-second time-to-live. Once consumed, nonces are retired to prevent replay attacks.
- **Zero Generic Sudo:** Arbitrary shell commands, script execution, and unverified paths are rejected with explicit denial.

### 7.2 Localhost API Hardening (`app/api/`)
- **256-Bit Bearer Token Authentication (`app/api/auth.py`):** Cryptographically strong random tokens generated via `secrets.token_urlsafe(32)`. Token persistence adheres to Windows user-profile isolation (`0600` permissions) and constant-time verification (`hmac.compare_digest`).
- **Tiered Endpoint Authorization:** Endpoints are categorized into `READ_ONLY`, `SENSITIVE_READ`, `MUTATING`, and `PRIVILEGED`. Sensitive and mutating actions strictly require valid authentication.
- **DNS Rebinding Defense (`app/api/server.py`):** Host header validation enforces loopback identity (`127.0.0.1`, `localhost`). External or forged hostnames trigger HTTP 403 Forbidden.
- **Request Size & Rate Limiting:** Request payload size is hard-capped at 1 MB (HTTP 413). Sliding-window rate limiters reject request flooding (e.g. 5 requests/min for mutating actions).
- **Safe Error Envelopes:** Error responses return standardized error messages without leaking stack traces, internal paths, or environment variables.

### 7.3 Subprocess & System Security (`app/core/security.py`)
- **Executable Allowlist (`ALLOWED_EXECUTABLES`):** Probes and diagnostic actions can only invoke explicitly allowlisted system binaries (`ping.exe`, `tracert.exe`, etc.) with absolute paths where practical.
- **Shell Metacharacter Defense:** Subprocess runners reject shell metacharacters (`&`, `;`, `|`, `` ` ``, `$`) and enforce `shell=False` across all calls.
- **Output Capping:** Subprocess stdout/stderr streams are hard-capped at 64 KB (`MAX_SUBPROCESS_OUTPUT_BYTES`) with bounded timeouts.
- **Path Traversal Defense (`safe_resolve_path`):** Rejects directory traversal sequences (`../`, `..\`), null bytes, Alternate Data Streams (`:`), and UNC network paths (`\\`).
- **CSV Formula Injection Sanitization (`sanitize_csv_cell`):** Escapes spreadsheet trigger characters (`=`, `+`, `-`, `@`) with a leading apostrophe.
- **Log Injection Defense (`sanitize_log_string`):** Strips newline characters (`\r`, `\n`) to prevent log forging and splitting.
- **Centralized Credential Scanner (`SecretScanner`):** Recursively audits dictionaries and strings, redacting passwords, bearer tokens, API keys, and cryptographic certificates.

### 7.4 Optimization & Snapshot Integrity (`optimization/`)
- **HMAC-SHA256 Snapshot Integrity:** Snapshots are signed with a session-bound HMAC key (`calculate_snapshot_hmac`). Any state modification or file tampering raises `SnapshotTamperedError`.
- **Pre-Rollback State Verification:** `RollbackSafetyError` is raised if system state diverges from the snapshot prior to rollback, preventing blind application of stale configuration.
- **Concurrency Mutex:** Global threading lock serializes optimization runs, preventing race conditions between concurrent opportunities or simultaneous rollback/apply cycles.
- **Crash Recovery:** Interrupted runs discovered on startup are safely transitioned to `INCONCLUSIVE` without falsely recording success or corrupting system state.

### 7.5 Storage Reliability & Corruption Fallback (`storage/sqlite_engine.py`)
- **Startup Integrity Checks:** Engine executes `PRAGMA integrity_check` on connection initialization.
- **Graceful Degradation:** If SQLite corruption or disk-full conditions occur, storage transitions to `StorageHealthState.DEGRADED` without terminating real-time monitoring.

### 7.6 AI Security & Prompt Injection Boundary (`analyzer/ai/`)
- **Input Sanitization:** Strips control characters, newlines, and bounds queries to 500 characters.
- **Deterministic Action Barrier:** Natural language processing has zero tool execution authority, zero shell access, and zero configuration mutation privileges.

---

## 8. Stage 8 Production Packaging & Deployment Architecture

### 8.1 Standalone Windows Binary & Runtime Bundling (`installer/veyra.spec`)
- **Zero Host Python Dependency:** Packaged via PyInstaller into a self-contained 64-bit Windows executable (`dist/VEYRA/VEYRA.exe`), embedding the Python 3.14 runtime, standard library, and native hardware bindings (`psutil`).
- **Rule 9 Simulation Exclusion:** The PyInstaller build specification explicitly excludes `simulation` and `tests` modules from the production bundle, preventing testing or chaos fixtures from shipping to end-user machines.

### 8.2 Strict Directory & Permission Separation (`app/core/paths.py`)
- **Installation Directory (Read-Only Binaries):** `%LOCALAPPDATA%\Programs\VEYRA` or `C:\Program Files\VEYRA`. Holds immutable executables, libraries, and locked branding assets.
- **User Data Directory (Writable Storage):** `%LOCALAPPDATA%\VEYRA`. Completely segregated from application binaries:
  - Database: `%LOCALAPPDATA%\VEYRA\data\history.sqlite`
  - Logs: `%LOCALAPPDATA%\VEYRA\logs\veyra.log`
  - Config: `%LOCALAPPDATA%\VEYRA\config\config.json`
- **Least-Privilege Standard User Compatibility:** Runs under standard unprivileged user accounts without requiring UAC administrator elevation for normal execution or database persistence.

### 8.3 Deployment & Installer Ecosystem
- **One-Command PowerShell Installer (`install.ps1`):** Validates distribution binaries, copies application files, registers Windows Add/Remove Programs uninstall registry entry (`HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\VEYRA`), creates Start Menu shortcuts with official branding icons, and verifies SHA-256 manifest integrity.
- **Data-Safe Uninstaller (`uninstall.ps1`):** Terminates running instances, cleans application binaries, removes shortcuts, and **preserves user data and history by default**, requiring explicit `-PurgeData` switch for full data wiping.
- **One-Command Production Launcher (`run_veyra.bat`):** Locates installed application binaries safely and starts the standalone executable without requiring Python, Git, or developer tooling.
- **Inno Setup & MSIX Specifications (`installer/installer.iss`, `installer/AppxManifest.xml`):** Provides standard Windows desktop setup packaging and MSIX desktop bridge declarations with restricted capabilities (`runFullTrust`).
- **Minimal Process Supervisor (`app/core/supervisor.py`):** Provides user-space background monitoring with rate-limited bounded restart logic (max 5 restarts within a 60-second rolling window) to prevent restart thrashing or CPU exhaustion loops.
- **Release Manifest Integrity (`release_manifest.json`):** Tracks all distribution binaries, setup scripts, and specs with cryptographic SHA-256 digests and file sizes.



