# VEYRA — Persistent Engineering Memory (brain.md)

> **Document Purpose:** Ground-truth engineering memory across all development stages and agents.  
> **Rule:** Every agent or engineer MUST read this file before modifying any code.

---

## 1. Project Identity & Purpose
- **Product Name:** VEYRA (Strictly VEYRA; never "NetPulse").
- **Product Vision:** High-precision, local-first Windows PC observability, network diagnostics, system monitoring, incident intelligence, historical analysis, gaming-performance and future optimization application.
- **Authoritative Root:** `<project-root>`

---

## 2. Authoritative Project Roadmap

```
STAGE 0: Engineering Contract + Repository Foundation (COMPLETE)
   ↓
STAGE 1: Real Measurement + Collection (COMPLETE)
   ↓
STAGE 2: Intelligence + Incident Analysis Foundation (COMPLETE)
   ↓
STAGE 3: Historical Intelligence + Memory (COMPLETE)
   ↓
STAGE 4: Professional Veyra UI + Dashboard (COMPLETE)
   ↓
STAGE 5: Diagnostics + Gaming Intelligence + Optimization (COMPLETE)
   ↓
STAGE 6: Security + Privacy + Reliability Hardening (COMPLETE)
   ↓
STAGE 7: Automated Testing + Simulation + QA (COMPLETE)
   ↓
STAGE 8: Packaging + One-Command Deployment (COMPLETE)
   ↓
STAGE 9: GitHub + Documentation + Portfolio Polish (COMPLETE)
   ↓
STAGE 10: Full Production Audit + Release Certification (COMPLETE)
```

- **Production Status:** Stages 0 through 10 COMPLETE & CERTIFIED.
- **Test Baseline:** 209 tests passing (0 failures, 0 errors, 0 skips).
- **Release State:** Production Ready (v0.1.0-RC1).

---

## 3. Mandatory 16-Differentiator Traceability Matrix

Every single one of these 16 differentiators is mandatory final product scope by Stage 10.

| # | Mandatory Differentiator | Stage 5 Status | Architectural Traceability Path to Stage 10 |
|---|---|---|---|
| 1 | **Incident Replay** | COMPLETE | Stage 2 replay contracts → Stage 3 persistent Before/During/After SQLite replay (`IncidentReplayStore`) → Stage 4 visual replay viewer (`ReplayViewer` answering all 5 questions) → Stage 5 advanced diagnostics integration → Stage 6 privacy audit (zero sensitive payload persistence) |
| 2 | **Personal PC Baseline** | COMPLETE | Stage 2 baseline engine → Stage 3 persistent SQLite baseline (`PersistentBaselineStore`) → Stage 4 UI overview & drift comparison panels → Stage 5 game-specific & historical baseline integration → Stage 6 monotonic clock tracking & tamper resistance |
| 3 | **"What Changed?" Engine** | COMPLETE | Stage 2 change detector → Stage 3 historical comparisons (`HistoricalComparisonEngine`) → Stage 4 dedicated `WhatChangedScreen` with configuration & metric shift log → Stage 6 credential & secret redaction on change records |
| 4 | **Performance Regression Detector** | COMPLETE | Stage 2 regression detector → Stage 3 historical regression detection against baselines → Stage 4 historical UI and baseline deviation indicators → Stage 5 optimization verification regression detector → Stage 6 automatic rollback trigger validation |
| 5 | **Optimization A/B Testing** | COMPLETE | Stage 2 contracts → Stage 3 `optimization_experiments` table → Stage 4 settings awareness → Stage 5 `OptimizationABTestingEngine` with baseline vs test window & confounder detection → Stage 6 anti-tamper & concurrency protection |
| 6 | **Automatic Rollback Guardian** | COMPLETE | Stage 2 safety contracts → Stage 3 rollback persistence schema → Stage 5 `AutomaticRollbackGuardian` with deterministic regression trigger → Stage 6 pre-rollback state verification & replay defense |
| 7 | **PC Health Flight Recorder** | COMPLETE | Stage 2 flight recorder → Stage 3 persistent snapshots (`PersistentFlightRecorderStore`) → Stage 4 incident investigation view with evidence context → Stage 5 diagnostic integration → Stage 6 privacy-safe recursive credential scrubbing |
| 8 | **Cross-Layer Root Cause Graph** | COMPLETE | Stage 2 topology/evaluator → Stage 3 persistent incident root causes → Stage 4 cross-layer network topology banner → Stage 5 `CrossLayerInvestigator` with 6-node graph & deterministic confidence → Stage 6 bounded probe execution & cancellation |
| 9 | **"Ask Veyra" AI** | COMPLETE | Stage 2 evidence package builder → Stage 3 durable evidence storage → Stage 4 API & UI presentation → Stage 5 `AskVeyraEngine` deterministic offline Q&A with structured citations → Stage 6 prompt injection boundary & action barrier |
| 10 | **"Explain My PC"** | COMPLETE | Stage 2 explainable assessments → Stage 3 persistent frequencies → Stage 4 deterministic bottleneck and incident explanations → Stage 5 `ExplainMyPCEngine` structured synthesis → Stage 6 ground truth verification without external keys |
| 11 | **Gaming Session DNA** | COMPLETE | Stage 2 telemetry tracking → Stage 3 rollups → Stage 4 Crimson Gaming mode shell infrastructure → Stage 5 `GamingSessionEngine` & `GamingSessionDNA` (zero fake FPS) → Stage 6 sanitized metadata & profile path traversal defense |
| 12 | **Game-Specific Performance Profiles** | COMPLETE | Stage 2 workload contracts → Stage 3 baseline context → Stage 4 mode selection shell → Stage 5 `GameProfileManager` with process detection & profile persistence → Stage 6 strict path and process validation |
| 13 | **Safe Optimization Opportunities** | COMPLETE | Stage 2 opportunity contracts → Stage 3 baseline comparisons → Stage 4 visual baseline comparisons → Stage 5 `OptimizationOpportunityEngine` & `OptimizationExecutor` with mandatory user approval → Stage 6 HMAC snapshot integrity & single-action mutex |
| 14 | **Hardware Bottleneck Investigator** | COMPLETE | Stage 2 bottleneck investigator → Stage 3 timeline/regression → Stage 4 `SystemScreen` hardware bottleneck panel → Stage 5 `BottleneckInvestigator` with genuine thermal sensors & workload correlation → Stage 6 strict sensor validation & non-fabrication |
| 15 | **PC Timeline** | COMPLETE | Stage 2 chronological events → Stage 3 durable SQLite PC Timeline → Stage 4 `TimelineView` widget on Dashboard and configuration history → Stage 5 gaming session & optimization event integration → Stage 6 privacy-safe sanitized event stream |
| 16 | **Evidence-Grounded AI** | COMPLETE | Stage 2 evidence contracts → Stage 3 verifiable historical records → Stage 4 grounded incident replay presentation → Stage 5 `AIEvidencePackage` & local offline ground truth → Stage 6 tamper-proof evidence signing & strict offline isolation |

---

## 4. Non-Negotiable Core Principles

1. **NEVER FABRICATE A MEASUREMENT:** Zero synthetic telemetry, guessed values, or placeholder data. Missing metrics explicitly use `Unavailable`, `Not supported`, `Stale`, `Permission required`, `Collector unavailable`, or `Measurement failed`.
2. **Deterministic Intelligence & Memory Loop:**
   `MEASUREMENT → EVIDENCE → INCIDENT → MEMORY (SQLITE) → BASELINES → COMPARISONS → UI → ACTION (APPROVAL) → VERIFICATION → ROLLBACK`
   - Collectors collect real measurements.
   - Analyzers evaluate verified observations.
   - Storage persists compacted historical summaries; ephemeral raw buffer in RAM.
   - UI presents real evidence; contains ZERO collection logic and ZERO raw SQL.
3. **Decoupling Invariant:**
   - Collectors do NOT know about storage or UI.
   - Analyzers consume standardized `Observation` contracts from collectors.
   - Storage stores verified observations, incident records, baselines, and summaries.
   - UI consumes `UiStateManager` and `StorageEngine` service APIs.
4. **Local-First & Privacy:**
   - Default binding: `127.0.0.1`. Binding to `0.0.0.0` or public interfaces is strictly rejected.
   - Zero telemetry exfiltration, zero cloud upload, zero external API keys, zero raw packet capture, zero secrets recorded.
5. **Deterministic AI Boundary:**
   - LLMs DO NOT control core detection, incident severity, root-cause attribution, or actions.
   - Natural language explanations are strictly grounded in structured deterministic evidence.
6. **Final Stage Cleanup Directive (User Mandate):**
   - After completing the final stage (Stage 10: Full Production Audit + Release Gate), all stage completion report files (e.g. `STAGE_*_COMPLETION_REPORT.md`) MUST be deleted from the repository to leave a clean, professional, production-ready codebase.

---

## 5. Locked Branding Integrity

- **Normal Mode:** Cyan theme (`#27D3E6`), locked master artwork `VEYRA_Normal_Logo_EXACT.png` (1254x1254).
- **Gaming Mode:** Crimson theme (`#FF3045`), locked master artwork `VEYRA_Gaming_Logo_EXACT.png` (1254x1254).
- **Immutability Rule:** No recoloring, redrawing, tracing, distortion, or regeneration.
- **SHA-256 Manifest:** Located at `assets/branding/branding_manifest.json` (22 assets).
- **Verification Engine:** `app/core/branding.py` verifies all 22 assets against recorded SHA-256 digests. 100% verified.

---

## 6. Stage 4 — Professional UI & Localhost API Architecture

### 6.1 Localhost HTTP API (`app/api/`)
- `app/api/routes.py`: `ApiRouteDispatcher` implementing exact endpoints and standard envelopes defined in `API_CONTRACT.md`.
- `app/api/server.py`: `LocalApiServer` using `ThreadingHTTPServer` strictly bound to `127.0.0.1` with IP verification rejecting non-local connections.

### 6.2 Desktop GUI Shell & Components (`app/ui/`)
- `app/ui/theme.py`: `ThemeManager` with dynamic mode/theme listener callbacks, official locked branding logo/icon paths.
- `app/ui/state.py`: `UiStateManager` with reactive state caching, deterministic monotonic freshness calculation, and health scoring.
- `app/ui/screens/`: 11 full desktop screens covering all core domains and Stage 5 capabilities.

---

## 7. Stage 5 Architecture & Higher-Level Intelligence

### 7.1 Advanced Diagnostics Subsystem (`diagnostics/`)
- Diagnostic layers, 6 isolated probes with hard timeouts, `CrossLayerInvestigator`, and `DiagnosticRunner`.

### 7.2 Hardware Bottleneck Investigator (`analyzer/bottleneck/`)
- Deep bottleneck analysis across CPU, GPU, RAM, VRAM, storage, and genuine thermal sensors.

### 7.3 Gaming Intelligence & Session DNA (`analyzer/gaming/`)
- Session engine with circular telemetry buffer, deterministic DNA generation, and zero fake FPS.

### 7.4 Safe Optimization Engine & Automatic Rollback Guardian (`optimization/`)
- Evidence-based opportunities, mandatory user approval, snapshotting, verification, and automatic rollback on regression.

### 7.5 Explain My PC & Ask Veyra AI Architecture (`analyzer/ai/`)
- Structured, deterministic explanation synthesis and offline question answering without cloud dependencies.

---

## 8. Stage 6 — Security, Privacy & Reliability Hardening Architecture

### 8.1 Least-Privilege Separation & Helper Architecture (`app/core/privilege.py`)
- Main application runs non-elevated. Operations requiring administrator privilege are mediated by a narrow helper (`PrivilegedHelper`).
- Strict operation allowlist (`PrivilegedOperationAllowlist`): only explicitly registered operations can execute.
- Single-use authorization tokens (`PrivilegeAuthorizationToken`) with 60-second TTL, caller PID binding, and unique UUID nonces to eliminate replay attacks.

### 8.2 Localhost API Hardening (`app/api/auth.py`, `app/api/server.py`, `app/api/routes.py`)
- **Authentication:** 256-bit cryptographically secure token lifecycle (`ApiTokenManager`) using constant-time `hmac.compare_digest`. Token rotation, revocation, and secure file storage (`0600` permissions).
- **Authorization:** Tiered access control (`READ_ONLY`, `SENSITIVE_READ`, `MUTATING`, `PRIVILEGED`). Mutating and privileged actions require explicit token auth.
- **DNS Rebinding Defense:** Host header validation (`ALLOWED_HOST_HEADERS`) rejecting requests with non-loopback host names.
- **Request Limiting:** Request body size bounded to 1 MB (`413 Payload Too Large`); sliding-window rate limiter (`ApiRateLimiter`) rejecting bursts.
- **Security Headers:** Enforced `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`.
- **Safe Error Envelopes:** Minimal error responses without stack traces, internal paths, or environment data.

### 8.3 Subprocess & Path Traversal Security (`app/core/security.py`)
- Hard allowlist of executable binaries (`ALLOWED_EXECUTABLES`).
- Shell metacharacter injection pattern blocking. `shell=False` strictly enforced.
- Subprocess output bounded to 64 KB (`MAX_SUBPROCESS_OUTPUT_BYTES`).
- Path validation (`safe_resolve_path`): Blocks `../`, `..\`, null bytes, alternate data streams (`:`), and UNC paths (`\\`).
- CSV formula sanitization (`sanitize_csv_cell`): Escapes `=`, `+`, `-`, `@` with a leading apostrophe.
- Log injection defense (`sanitize_log_string`): Strips `\r` and `\n` to prevent log forging.
- Centralized credential scanner (`SecretScanner`): Recursively inspects dictionaries and text to redact passwords, tokens, API keys, and private certificates.

### 8.4 Optimization & Snapshot Integrity (`optimization/snapshots.py`, `optimization/executor.py`)
- **HMAC-SHA256 Signing:** All pre-change snapshots are cryptographically signed using an ephemeral session key (`calculate_snapshot_hmac`). Tampered snapshots raise `SnapshotTamperedError` and are rejected.
- **Pre-Rollback State Verification:** Current system state is verified against snapshot expectations before rollback (`RollbackSafetyError`) to prevent mismatch replay.
- **Process Mutex:** Global threading lock prevents concurrent optimization runs or apply/rollback races.
- **Crash Recovery:** Transient interrupted states are marked `INCONCLUSIVE` upon startup without falsely asserting success.

### 8.5 Storage Reliability & Corruption Fallback (`storage/sqlite_engine.py`)
- SQLite database initializes with `PRAGMA integrity_check`.
- In the event of disk-full or database corruption, storage degrades gracefully to `StorageHealthState.DEGRADED` without crashing real-time monitoring.

### 8.6 AI Security & Prompt Injection Boundary (`analyzer/ai/ask_veyra.py`)
- Ask Veyra sanitizes inputs (stripping newlines/null bytes, 500-char max length).
- Strict Action Barrier: The engine has zero executable capabilities, zero shell access, and zero modification authority.

### 8.7 Chaos Simulation & QA Fault Injection Architecture (`simulation/`)
- **Rule 9 Isolation Guarantee:** All simulation data is strictly segregated from production telemetry with `is_simulation: True` tagging and zero production SQLite persistence.
- **Chaos Engine (`simulation/chaos_engine.py`):** Structured experiment orchestration, error containment, execution timeouts, and comprehensive `ChaosReport` generation.
- **Hardware & Storage Fault Injectors (`simulation/fault_injectors.py`):**
  - `GpuFaultInjector`: Simulates vendor driver hangs (timeout), NaN/out-of-range sensor spikes, and thermal throttling edge-cases.
  - `StorageFaultInjector`: Simulates `sqlite3.OperationalError` (disk full, I/O errors) and database file header corruption to verify graceful fallback.
  - `ProcessFaultInjector`: Injects concurrency collisions (`OptimizationConflictError`) and simulated worker crashes with inconclusive recovery states.
  - `TimeChaosInjector`: Simulates NTP backward steps, epoch jumps, and suspension/resume sleep gaps to verify monotonic clock invariance.
- **Network Anomaly Simulators (`simulation/network_chaos.py`):**
  - Simulates bufferbloat latency spikes (e.g. 5ms -> 350ms), burst packet drops (e.g. 25% drop rate), and DNS blackhole resolution failures (`socket.gaierror`).
- **Telemetry Soak & Memory Leak Harness (`simulation/soak_harness.py`):**
  - Generates high-throughput telemetry cycles (1,000+ observations) through a bounded ring buffer (`deque(maxlen=1000)`).
### 8.8 Production Packaging & Deployment Architecture (`installer/`, `app/core/paths.py`, `app/core/supervisor.py`)
- **Standalone Windows Executable (`dist/VEYRA/VEYRA.exe`):** Bundled via PyInstaller, embedding Python 3.14 runtime and native dependencies into a self-contained desktop binary. Zero requirement for host Python, pip, or virtualenv on client machines.
- **Rule 9 Simulation Exclusion:** PyInstaller spec explicitly excludes `simulation` and `tests` packages from production distribution artifacts.
- **Strict Directory Separation:**
  - Read-Only Program Files: `%LOCALAPPDATA%\Programs\VEYRA`
  - Writable User Data: `%LOCALAPPDATA%\VEYRA` (`data/history.sqlite`, `logs/veyra.log`, `config/config.json`)
- **Least-Privilege Security:** Operates completely under standard user rights without requiring UAC elevation.
- **Deployment Scripts:**
  - `install.ps1`: One-command PowerShell installer with Start Menu integration and Add/Remove Programs registration.
  - `uninstall.ps1`: Clean uninstaller that preserves user data by default, requiring explicit `-PurgeData` for full wipe.
  - `run_veyra.bat`: One-command launcher resolving production paths.
  - `installer/installer.iss`: Inno Setup installer specification with modern wizard and silent install options.
  - `installer/AppxManifest.xml`: MSIX Windows App Package manifest declaring `runFullTrust`.
  - `app/core/supervisor.py`: Bounded user-space supervisor enforcing restart rate limits (max 5 in 60s) to prevent crash storms.
  - `release_manifest.json`: Cryptographic SHA-256 digests for all tracked distribution artifacts.

---

## 9. Test Suite & Verification Results

- **Total Automated Tests:** 209 tests (`python -m unittest discover -s tests -v`)
- **Status:** 209 passed, 0 failures, 0 errors, 0 skipped (100% passing across 41 test modules in ~22s).
- **Test Modules:**
  - Pre-existing Stage 0–4 modules (29 modules, 108 tests)
  - Stage 5 modules (6 modules, 43 tests):
    - `tests/test_bottleneck_investigator.py` (10 tests)
    - `tests/test_gaming_intelligence.py` (8 tests)
    - `tests/test_optimization_engine.py` (7 tests)
    - `tests/test_diagnostics.py` (7 tests)
    - `tests/test_explain_my_pc_and_ai.py` (6 tests)
    - `tests/test_stage5_storage.py` (5 tests)
  - Stage 6 security module (1 module, 20 tests):
    - `tests/test_stage6_security.py` (20 tests) — Token auth, rotation, rate limiting, path traversal, CSV formula sanitization, subprocess injection defense, privileged helper single-use nonces, snapshot HMAC tampering defense, concurrency mutex, secret scanner, log sanitization, database corruption degradation, and AI prompt injection boundary.
  - Stage 7 chaos simulation, fault injection & QA modules (4 modules, 26 tests):
    - `tests/test_stage7_chaos_simulation.py` (6 tests) — ChaosEngine experiment execution, reporting, error containment, timeout enforcement, on-demand abort, and Phase 19 simulation data isolation contracts.
    - `tests/test_stage7_fault_injection.py` (12 tests) — GPU driver timeout/corrupted data, SQLite disk-full/corruption graceful degradation, optimization process concurrency/crash recovery, monotonic time skew invariance, network bufferbloat, packet loss bursts, DNS blackhole isolation, and Phase 19 storage contamination rejection.
    - `tests/test_stage7_stress_and_soak.py` (3 tests) — 500-cycle telemetry soak test, 1,000-cycle memory leak bounds (<15MB), and 1,000-observation statistical aggregation performance (<50ms).
    - `tests/test_stage7_e2e_scenarios.py` (5 tests) — End-to-end integration scenarios covering gaming session DNA under network jitter, safe optimization snapshot/rollback lifecycle, cross-layer diagnostic root cause isolation, SQLite storage degradation resilience, and zero-trust security input barrage.
  - Stage 8 packaging & deployment module (1 module, 12 tests):
    - `tests/test_stage8_packaging.py` (12 tests) — Production path resolution, user data vs binary separation, simulation exclusion in spec, zero hardcoded developer paths, database initialization/migrations in production paths, install.ps1/uninstall.ps1 syntax and policies, run_veyra.bat launcher integrity, Inno Setup script validity, MSIX manifest XML validation, release manifest SHA-256 generation, process supervisor bounded restart logic, and branding asset accessibility.

---

### 8.9 GitHub Integration, Documentation & Portfolio Architecture (`docs/`, `.github/`, `README.md`)
- **Comprehensive Systems Architecture Showcase (`docs/ARCHITECTURE_SHOWCASE.md`):** Complete top-to-bottom systems breakdown with GitHub-rendered Mermaid diagrams for unidirectional measurement, incident correlation, historical compaction, least-privilege IPC, and gaming session DNA.
- **Security Model & Vulnerability Disclosure (`docs/SECURITY.md`):** Threat boundary analysis, loopback IPC authentication, subprocess safety, privacy audit, and responsible disclosure SLA.
- **Engineering Portfolio Showcase (`docs/PORTFOLIO.md`):** Deep dive into the 16 core differentiators, systems engineering challenges, storage compaction trade-offs, and reliability metrics.
- **Resume Project Description (`docs/RESUME_PROJECT.md`):** Quantifiable systems engineering bullet points, technical stack matrix, and elevator pitches.
- **Technical Case Study (`docs/CASE_STUDY.md`):** "Building an Evidence-Driven Observability & Optimization Engine for Windows" analyzing design principles, empirical findings, and lessons learned.
- **Release Engineering Guide (`docs/RELEASE.md`):** SemVer 2.0.0 rules, build pipeline, cryptographic manifest verification, and pre-release QA checklist.
- **Open-Source Governance & CI:**
  - `CONTRIBUTING.md`: Development environment setup, coding standards, and invariant enforcement.
  - `CODE_OF_CONDUCT.md`: Contributor Covenant v2.1.
  - `.github/workflows/ci.yml`: Automated GitHub Actions workflow on Windows running Pytest across 209 tests.
  - Issue & PR Templates: Standardized bug report, feature request, security report, and PR verification checklists.

---

## 9. Test Suite & Verification Results

- **Total Automated Tests:** 209 tests (`python -m unittest discover -s tests -v` / `pytest tests/ -q`)
- **Status:** 209 passed, 0 failures, 0 errors, 0 skipped (100% passing across 41 test modules in ~22s).
- **Test Modules:**
  - Pre-existing Stage 0–4 modules (29 modules, 108 tests)
  - Stage 5 modules (6 modules, 43 tests)
  - Stage 6 security module (1 module, 20 tests)
  - Stage 7 chaos simulation, fault injection & QA modules (4 modules, 26 tests)
  - Stage 8 packaging & deployment module (1 module, 12 tests)

---

## 10. Known Limitations & Architectural Boundaries

- **Windows x64 Exclusivity:** Engineered specifically for Windows 10/11 (64-bit); ARM64 and non-Windows OSes are out of scope.
- **Ad-Hoc Signing:** Current open-source release packages use self-signed / ad-hoc Authenticode certificates; production enterprise rollout requires an EV certificate.
- **Hardware Counter Dependency:** Detailed GPU 3D engine and video memory telemetry requires compatible DXGI/WMI driver support.
- **No Remote / Cloud Telemetry:** Zero external API keys or cloud analytics dependencies exist.

---

## 11. Final Stage Status: STAGE 10 — PRODUCTION CERTIFIED
- **Audit Verdict:** FINAL PRODUCTION GATE: PASS.
- **Repository State:** Production-certified, clean, fully documented, and ready for deployment.
- **Development Lifecycle:** COMPLETE. All 10 stages successfully executed and verified.


