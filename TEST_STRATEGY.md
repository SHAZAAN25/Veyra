# VEYRA — Testing Strategy & Quality Assurance Framework

> **Strategy Status:** ACTIVE  
> **Testing Level:** Continuous Automated Test Suite

---

## 1. Quality Assurance Philosophy

VEYRA monitors mission-critical system stability, network reliability, and gaming performance. A flaw in VEYRA's telemetry engine could misdiagnose a user's connection or burden their hardware.

The test strategy is grounded in three principles:

1. **Zero Fake Telemetry Verification:** Tests must continuously assert that metrics adhere to the data contract. Any attempt to populate a non-`AVAILABLE` metric with a value must fail the test suite.
2. **Deterministic Branding Integrity:** Automated tests hash all 22 official branding assets against `branding_manifest.json` on every test run. If any artwork is altered or replaced, the build fails immediately.
3. **Local-First Security Enforcements:** Tests strictly verify that all API configurations refuse non-localhost bindings (`0.0.0.0`, LAN IPs) and that subprocess runners reject unsafe invocations.

---

## 2. Test Pyramid & Directory Structure

```
tests/
├── __init__.py
├── test_branding.py     # Brand asset integrity & SHA-256 validation
├── test_config.py       # Configuration schema, port limits, localhost enforcement
├── test_security.py     # Subprocess isolation, path traversal, sensitive redaction
├── test_contracts.py    # MetricState lifecycle, non-fabrication invariant
└── test_errors.py       # Error hierarchy, safe logger resilience, sleep/gap detection
```

---

## 3. Test Categories

### A. Integrity & Contract Tests
- Assert that `Measurement` enforces `is_valid` exclusively when `state == MetricState.AVAILABLE`.
- Assert that assigning a numeric fallback to `UNAVAILABLE` raises `DataContractViolationError`.
- Assert that every measurement contains `provenance`, `source_collector`, and `timestamp_utc`.

### B. Security & Boundary Tests
- Assert that binding configuration to `0.0.0.0` or public IP ranges raises `SecurityViolationError`.
- Assert that path traversal attempts (`../`) are blocked by `validate_safe_path`.
- Assert that passwords, bearer tokens, and private keys are scrubbed by `redact_sensitive_data`.

### C. Branding Lock Tests
- Assert that all 22 assets listed in `assets/branding/branding_manifest.json` exist and match their SHA-256 hash byte-for-byte.
- Assert that `VEYRA_Normal_Logo_EXACT.png` and `VEYRA_Gaming_Logo_EXACT.png` are at least 1254x1254 and present in their respective directories.

### D. Stage 6 Security, Privacy & Reliability Hardening Tests (`tests/test_stage6_security.py`)
- **Authentication & Token Lifecycle:** 256-bit cryptographically secure token generation, constant-time verification, rotation, revocation, invalid token rejection.
- **Rate Limiting & Request Capping:** Sliding-window rate limiter enforcement and 1 MB payload limits.
- **DNS Rebinding Defense:** Host header validation rejecting non-loopback headers.
- **Path Traversal & Injection Defense:** Blocking `../`, null bytes, alternate data streams, and UNC paths; CSV formula injection defense (`sanitize_csv_cell`); log injection defense (`sanitize_log_string`).
- **Subprocess Security:** Blocking shell metacharacters and unallowlisted binaries.
- **Privilege Separation & Nonce Anti-Replay:** Single-use authorization nonces, expiration, and parameter hash validation.
- **Snapshot Integrity:** HMAC-SHA256 signature verification and tamper detection.
- **Optimization Mutex & Concurrency:** Process-wide lock preventing concurrent optimization execution.
- **Storage Degradation:** Graceful fallback to `StorageHealthState.DEGRADED` upon SQLite corruption without crashing the application.
- **AI Action Barrier & Prompt Injection:** Query sanitization and non-executable isolation.

### E. Stage 7 Chaos Simulation, Fault Injection & QA Harnesses (`tests/test_stage7_*.py`)
- **Chaos Engine & Orchestration (`tests/test_stage7_chaos_simulation.py`):** Dynamic experiment registration, failure handling, graceful degradation verification, and Rule 9 data segregation audit.
- **Fault Injection Matrix (`tests/test_stage7_fault_injection.py`):**
  - *Hardware & Subsystem:* GPU subprocess timeout and corrupted output handling without fake metrics.
  - *Storage:* Disk full I/O error and database corruption degradation and recovery.
  - *Process & Concurrency:* Interrupted optimization startup crash recovery and concurrency lock race prevention.
  - *Clock & Time:* Sleep/wake gap detection (>15s) and NTP wall-clock backwards jump invariance.
  - *Network:* Bufferbloat latency surge, packet loss burst, and DNS blackhole layer isolation.
- **Soak & Stress Bounds (`tests/test_stage7_stress_and_soak.py`):** Accelerated 500-cycle and 1,000-cycle telemetry streaming, memory leak delta boundary (<15MB), bounded ring buffer capacity, and 1,000-observation statistical aggregation throughput.
- **End-to-End User Journeys (`tests/test_stage7_e2e_scenarios.py`):**
  - *Gaming Session DNA:* Full session lifecycle under jitter with DNA calculation and zero fabricated FPS.
  - *Safe Optimization & Auto-Rollback:* User approval, HMAC pre-snapshot, regression detection, and guardian auto-rollback.
  - *Cross-Layer Diagnostics:* Multi-layer probe execution and topological DNS root cause isolation.
  - *Storage Degradation Resilience:* Real-time in-memory buffer operations during SQLite failure.
  - *Zero-Trust Security Barrage:* Path traversal, CSV formula neutralization, and log injection defense.

### F. Stage 8 Packaging, Deployment & Windows Release Engineering Tests (`tests/test_stage8_packaging.py`)
- **Production Path Resolution:** Clean separation between read-only installation directory (`%LOCALAPPDATA%\Programs\VEYRA`) and writable user data directory (`%LOCALAPPDATA%\VEYRA`).
- **Simulation Data Exclusion:** Verifying `installer/veyra.spec` excludes `simulation` and `tests` packages (Rule 9).
- **Zero Hardcoded Developer Paths:** Verifying production path resolvers and configurations contain zero developer environment paths or user names.
- **Production Database Initialization:** Isolated database creation and automatic schema migration execution.
- **Installer & Deployment Script Validation:** Verifying `install.ps1`, `uninstall.ps1`, `run_veyra.bat`, `installer/installer.iss`, and `installer/AppxManifest.xml` parameter validation and least-privilege security.
- **Uninstaller User Data Policy:** Enforcing that uninstallation preserves user history by default and only purges when explicitly commanded.
- **Process Supervisor Bounded Restarts:** Validating restart storm detection and thrashing prevention.
- **Release Manifest Cryptographic Verification:** Generating and asserting SHA-256 digests for all release artifacts.

---

## 4. Test Execution

Tests can be executed across the entire repository using standard Python tooling:

```bash
# Standard library test runner (Zero dependencies required)
python -m unittest discover -s tests -v

# Total Verified Discovery: 209 tests across 41 test modules (100% passing)
```

