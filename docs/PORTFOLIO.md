# VEYRA — Senior Systems Engineering Portfolio Deep Dive

> **Project Name:** VEYRA  
> **Repository:** [github.com/SHAZAAN25/Veyra](https://github.com/SHAZAAN25/Veyra)  
> **Author:** Mohammed Shazaan ([SHAZAAN25](https://github.com/SHAZAAN25))  
> **Domain:** Local-First Windows PC Observability, Network Telemetry, Systems Reliability & Safe Optimization  
> **Technologies:** Python 3.12, Windows Kernel APIs (psutil, NDIS netsh, WMI, ctypes), SQLite (WAL), Tkinter, PyInstaller, Inno Setup, MSIX, Cryptography (HMAC)

---

## 1. Project Overview

**VEYRA** is an open-source, local-first Windows PC observability and performance optimization engine. It was built to address a fundamental architectural flaw in modern PC management software: **metric fragmentation without causal correlation**.

Most monitoring tools present isolated graphs (CPU usage in Task Manager, ping in Discord, GPU temps in Afterburner) or offer reckless "one-click PC cleaners" that edit registry keys without safety guarantees.

VEYRA bridges this gap with an evidence-driven systems architecture:
- Correlates physical hardware counters, network packet latency, Wi-Fi NDIS statistics, and background processes into a **unified causal graph**.
- Implements **Incident Replay**, allowing users to scrub backward through historical latency spikes and performance drops second-by-second.
- Enforces an **Atomic Rollback Guardian** and **PrivilegedHelper** separation, guaranteeing that every system optimization is verified against real telemetry and can be reversed with a single click.
- Adheres strictly to **Rule 1: Never Fabricate a Measurement** — zero guessing, zero synthetic interpolation, zero cloud telemetry.

---

## 2. The 16 Core Architectural Differentiators

| # | Differentiator | Architectural Implementation |
| :---: | :--- | :--- |
| **1** | **Incident Replay** | Second-by-second forensic scrubber across circular RAM buffer and SQLite snapshots. |
| **2** | **Personal PC Baseline** | Rolling 7-day percentile distributions (P50, P95, P99) of your specific hardware and network. |
| **3** | **What Changed?** | Differential state analyzer tracking background services, driver updates, and network routes. |
| **4** | **Performance Regression Detector** | Real-time statistical drift monitor alerting when system baseline deviates significantly. |
| **5** | **Optimization A/B Testing** | Empirical benchmark comparison testing system performance before and after any tweak. |
| **6** | **Automatic Rollback Guardian** | HMAC-signed state snapshots enabling instant, zero-risk restoration of modified configurations. |
| **7** | **PC Health Flight Recorder** | High-frequency ring-buffer maintaining pre-crash and pre-spike telemetry windows. |
| **8** | **Cross-Layer Root Cause Graph** | Causal graph linking Wi-Fi RSSI drops, gateway bufferbloat, DNS timeouts, and process I/O. |
| **9** | **Ask Veyra** | Natural language deterministic query engine operating 100% offline on verified metrics. |
| **10** | **Explain My PC** | Comprehensive, plain-English executive summary of hardware health and bottlenecks. |
| **11** | **Gaming Session DNA** | Match stability fingerprint graphing latency variance and thermal throttle events without anti-cheat hooks. |
| **12** | **Game-Specific Profiles** | Adaptive monitoring configurations customized for specific esports titles. |
| **13** | **Safe Optimization** | Strict least-privilege execution via authenticated loopback IPC (`PrivilegedHelper`). |
| **14** | **Hardware Bottleneck Investigator** | Evaluates CPU compute, memory bandwidth, and GPU fill-rate limits simultaneously. |
| **15** | **PC Timeline** | Unified chronological stream correlating system events, network disconnects, and incidents. |
| **16** | **Evidence-Grounded AI** | Explanations cite verifiable metric timestamps; zero cloud LLM hallucination. |

---

## 3. High-Impact Engineering Challenges & Solutions

### Challenge 1: High-Frequency Polling Without Storage Thrashing
- **The Problem:** Capturing sub-second network jitter and CPU spikes produces hundreds of thousands of data points per hour. Committing every point directly to disk exhausts SSD write endurance and causes I/O contention.
- **The Solution:** Implemented a two-tier storage hierarchy:
  1. An in-memory, pre-allocated circular ring buffer holding 300 high-resolution 1 Hz samples (5-minute rolling window).
  2. A background compaction worker that computes statistical aggregates (Min, Max, Mean, P95) every 5 minutes and commits them as a single atomic transaction to SQLite in WAL mode. Disk writes are reduced by 99.6% while preserving instant forensic replay.

### Challenge 2: Safe System Optimization Without Blanket Administrator Privileges
- **The Problem:** Standard optimization utilities demand full Administrator privileges, opening severe vulnerability vectors and exposing users to system corruption.
- **The Solution:** Designed a strict privilege-separation architecture:
  - The main GUI, telemetry collectors, and user API run under unprivileged user permissions (`asInvoker`).
  - Optimization requests are delegated to a dedicated `PrivilegedHelper` over loopback IPC.
  - The helper requires caller PID verification, single-use cryptographic nonces, and an immutable action allowlist with strict argument regex validation. Arbitrary command execution is impossible.

### Challenge 3: Esports Telemetry Without Anti-Cheat Flags
- **The Problem:** Most gaming overlay tools use DLL injection or global API hooks (`SetWindowsHookEx`), triggering false-positive bans in kernel anti-cheat systems (Riot Vanguard, BattlEye, Easy Anti-Cheat).
- **The Solution:** VEYRA uses strictly passive, non-intrusive OS observability:
  - Monitors foreground window focus via `GetForegroundWindow` and `GetWindowThreadProcessId`.
  - Queries physical network adapter packet counters and driver NDIS statistics asynchronously.
  - Renders a lightweight, borderless Tkinter HUD on a dedicated canvas layer without touching game memory spaces.

---

## 4. Verification, Testing & Reliability

The VEYRA repository is backed by an automated test suite guaranteeing deterministic stability across all subsystems:

- **Total Automated Tests:** **209 tests** across 41 test modules.
- **Pass Rate:** **100%** (0 failures, 0 errors, 0 skips).
- **Test Runtime:** ~22.5 seconds.
- **Chaos & Fault Injection (Stage 7):** Comprehensive simulation framework evaluating system resilience under simulated network bufferbloat, packet loss bursts, clock jumps, worker process crashes, and SQLite storage corruption.
- **Rule 9 Enforcement:** All chaos simulation contracts embed `is_simulation=True` and are strictly excluded from production installer packages.

---

## 5. Standalone Packaging & Distribution

VEYRA packages into an independent Windows desktop product:
- **Standalone Binary:** `dist/VEYRA/VEYRA.exe` (bundled Python 3.12 runtime, C-extensions, and Tkinter GUI).
- **Zero Prerequisites:** Operates cleanly on fresh Windows installations without Python, Git, or compiler toolchains.
- **Dual Installer Architecture:** Supports both graphical setup wizards (Inno Setup / MSIX) and one-command headless installations (`install.ps1`, `run_veyra.bat`).
- **User Data Policy:** Program binaries install to `%LOCALAPPDATA%\Programs\VEYRA`, while user history is preserved by default in `%LOCALAPPDATA%\VEYRA`.

---

## 6. Project Architecture Summary

```
Physical Hardware & OS Counters
            ↓
Immutable Measurement Contracts (1 Hz)
            ↓
In-Memory Ring Buffer (300 Samples) + Telemetry Analyzer
            ↓
Cross-Layer Root Cause Graph & Incident Detection
            ↓
Compacted 5-Minute SQLite Rollups (WAL Mode)
            ↓
Unprivileged Desktop Dashboard (Cyan Normal / Crimson Gaming)
            ↓ [User-Approved Optimization]
PrivilegedHelper IPC (Nonce + PID + HMAC Snapshot)
            ↓
Atomic System Change & Rollback Verification
```
