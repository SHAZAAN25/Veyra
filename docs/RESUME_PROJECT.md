# VEYRA — Resume Project Summary & Impact Statements

> **Quick Navigation:** [GitHub Repository](https://github.com/SHAZAAN25/Veyra) | [Architecture Showcase](ARCHITECTURE_SHOWCASE.md) | [Portfolio Deep Dive](PORTFOLIO.md)

---

## 1. One-Line Project Description

> **VEYRA:** An open-source, local-first Windows PC observability and evidence-driven optimization engine correlating hardware performance, network latency, and system incidents into a unified forensic timeline with atomic rollbacks.

---

## 2. Two-Line Project Description

> **VEYRA** is a standalone Windows desktop observability platform built in Python and C-extensions, delivering sub-second network jitter telemetry, cross-layer root cause incident detection, and game session profiling. Designed with strict least-privilege security, it guarantees zero cloud dependencies, non-intrusive anti-cheat compatibility, and single-click optimization rollbacks backed by an automated 209-test verification suite.

---

## 3. High-Impact Resume Bullet Points

### Systems & Performance Engineering
- Architected a **local-first Windows observability platform** in Python 3.12 and native C-extensions, capturing sub-second CPU, GPU, memory, disk, and network NDIS counters with zero cloud dependencies.
- Designed a **two-tier telemetry storage hierarchy** combining a 300-sample in-memory circular ring buffer with 5-minute statistical SQLite rollups (WAL mode), **reducing disk write overhead by 99.6%** while maintaining instant second-by-second forensic incident replay.
- Engineered a **Cross-Layer Root Cause Analysis graph** that automatically correlates physical Wi-Fi signal degradation, local gateway bufferbloat, upstream DNS timeouts, and per-process network I/O into deterministic incident records.

### Security & Systems Architecture
- Implemented a **least-privilege security model** isolating elevated system modifications behind an unprivileged-to-elevated IPC helper (`PrivilegedHelper`) with single-use cryptographic nonces, PID binding, and strict command allowlisting.
- Built an **Atomic Rollback Guardian** utilizing HMAC-SHA256 state snapshots, enabling safe A/B benchmarking and one-click reversal of system optimizations without administrator elevation risks.
- Formulated strict architectural invariants enforcing **Rule 1: Never Fabricate a Measurement**, eliminating synthetic interpolation, fake metrics, and cloud LLM hallucination across all analytical pipelines.

### Release Engineering, QA & Reliability
- Developed a comprehensive **automated testing harness comprising 209 unit, integration, and chaos simulation tests** across 41 modules, achieving a **100% pass rate** in ~22 seconds.
- Built a **fault-injection and chaos simulation engine** (Stage 7) modeling hardware timeouts, packet loss bursts, wall-clock skew, worker crashes, and storage corruption, with strict isolation preventing synthetic data contamination of production stores.
- Packaged the platform into a **standalone Windows executable distribution** via PyInstaller, Inno Setup, and MSIX, delivering automated one-command deployment (`install.ps1`, `run_veyra.bat`) requiring zero host Python or developer dependencies.

---

## 4. Technical Stack Breakdown

| Layer | Technologies / Modules |
| :--- | :--- |
| **Core Language & Runtime** | Python 3.12 (Embedded CPython 64-bit), Windows C-APIs (`ctypes`, `kernel32`, `advapi32`) |
| **System & Hardware Telemetry** | `psutil`, Windows NDIS (`netsh wlan`), WMI, DXGI / GPU counters, Raw Socket ICMP |
| **Storage & Persistence** | SQLite 3 (WAL Journal Mode), In-Memory Circular Buffers, HMAC-SHA256 Snapshots |
| **User Interface** | Native Tkinter Canvas UI, High-Contrast Cyan (Normal) & Crimson (Gaming HUD) themes |
| **Security & IPC** | Localhost Socket (`127.0.0.1`), Ephemeral Token Authentication, Single-Use Monotonic Nonces |
| **Reliability & Testing** | `pytest`, Chaos Simulation Harness, Fault Injectors, Soak Testing, Memory Leak Auditing |
| **Packaging & Deployment** | PyInstaller (Spec-driven `onedir`), Inno Setup, MSIX (`AppxManifest.xml`), PowerShell 5.1/7+ |

---

## 5. Architectural Metrics & Benchmarks

- **Test Suite Discovery:** 209 automated tests across 41 modules (0 failures, 0 errors, 0 skips).
- **Execution Overhead:** Idle memory footprint < 120 MB; background collector CPU utilization < 1.2% on standard quad-core systems.
- **Polling Cadence:** 1000ms hardware & network sampling; 5-minute persistent rollup aggregation.
- **Packaging Binary:** 2.87 MB standalone launcher binary (`dist/VEYRA/VEYRA.exe`).
- **Network Exposure:** 0 external ports listening; 100% loopback binding (`127.0.0.1`).
