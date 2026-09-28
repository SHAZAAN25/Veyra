# VEYRA — Architectural Deep Dive & Systems Showcase

> **Document Class:** Technical Architecture Specification & Systems Showcase  
> **Audience:** Senior Systems Architects, Observability Engineers, Security Reviewers  
> **Target Platform:** Microsoft Windows 10/11 (x64)  
> **Canonical Repository:** [github.com/SHAZAAN25/Veyra](https://github.com/SHAZAAN25/Veyra)

---

## 1. Executive Architecture Overview

VEYRA is a **local-first Windows desktop PC observability, network diagnostics, incident intelligence, and evidence-driven optimization engine**. It is engineered to solve a systemic problem in contemporary PC management tools: metric fragmentation, synthetic guesswork, ungrounded recommendations, and unconstrained privilege escalation.

Rather than presenting disjointed real-time meters, VEYRA correlates physical hardware performance, network protocol latency, network adapter states, background processes, historical baselines, and system changes into a single deterministic evidence graph.

```mermaid
graph TD
    subgraph Hardware_OS [Windows OS & Physical Hardware]
        HW_CPU[CPU Performance Counters]
        HW_MEM[RAM & Virtual Memory]
        HW_DISK[Disk IOPS & Volume Queues]
        HW_GPU[GPU Load & Video Memory]
        HW_NET[Network Adapters & Wi-Fi NDIS]
    end

    subgraph Collection_Layer [Collection Layer: collectors/]
        C_SYS[SystemCollector: psutil]
        C_NET[NetworkCollector: ping, socket]
        C_WIFI[WifiCollector: netsh wlan]
        C_GPU[GpuCollector: DXGI / WMI]
    end

    subgraph Processing_Layer [Core Engine & Analysis]
        COORD[MeasurementCoordinator]
        ANALYZER[TelemetryAnalyzer]
        CORR[RootCauseGraph / CorrelationEngine]
        DNA[GamingSessionDNA]
    end

    subgraph Storage_Layer [Storage Layer: storage/]
        RAM_BUF[Volatile Ring Buffer: 1s Samples]
        SQLITE[(history.sqlite: Compact Rollups & Incidents)]
    end

    subgraph Security_Boundary [Least-Privilege Security Boundary]
        API[Localhost HTTP/WS Server: 127.0.0.1]
        HELPER[PrivilegedHelper IPC Daemon]
    end

    subgraph Presentation_Layer [Presentation Layer: app/ui/]
        UI_NORM[Normal Desktop Dashboard: Cyan Theme]
        UI_GAME[Gaming HUD & DNA Mode: Crimson Theme]
    end

    Hardware_OS --> Collection_Layer
    Collection_Layer -->|Validated MeasurementContract| COORD
    COORD --> ANALYZER
    COORD --> RAM_BUF
    ANALYZER -->|IncidentDetected| CORR
    CORR --> SQLITE
    RAM_BUF -->|Compaction Worker: 5m rollups| SQLITE
    SQLITE --> API
    API --> Presentation_Layer
    Presentation_Layer -->|Authorized Action Token| HELPER
```

---

## 2. Unidirectional Measurement Pipeline

At the foundation of VEYRA is a strict engineering invariant: **Rule 1 — Never Fabricate a Measurement**. If telemetry is missing, hardware is unsupported, or an adapter is disconnected, the system explicitly reports `Unavailable` or `Not Supported`. Guesses, synthetic smoothing, and placeholder interpolation are categorically rejected.

```mermaid
sequenceDiagram
    autonumber
    participant OS as Windows Kernel / Drivers
    participant Coll as Hardware Collectors
    participant Coord as MeasurementCoordinator
    participant Anal as TelemetryAnalyzer
    participant Store as SQLite & RAM Ring
    participant UI as Desktop UI

    loop Every 1000ms Polling Interval
        Coll->>OS: Query OS APIs (psutil, netsh, ICMP)
        OS-->>Coll: Raw Hardware Counter Data
        Coll->>Coord: Emit Immutable MeasurementSnapshot
        Note over Coord: Verify Schema & Monotonic Timestamp
        Coord->>Store: Append to Volatile Circular Ring
        Coord->>Anal: Dispatch Snapshot for Evaluation
        Anal->>Anal: Check Baselines, Jitter & Thresholds
        Coord->>UI: Broadcast Live Telemetry via Localhost Socket
        UI->>UI: Refresh Native Canvas (Zero Polling Overhead)
    end
```

### Telemetry Pipeline Invariants:
1. **Immutable Snapshots:** All readings are frozen into `MeasurementSnapshot` dataclasses immediately upon collection.
2. **Zero In-Memory Drift:** Monotonic clocks (`time.monotonic()`) are used exclusively for interval coordination; wall clocks (`datetime.now(timezone.utc)`) are used strictly for human-readable audit timestamps.
3. **Graceful Degeneration:** A failure in an optional sensor (such as discrete GPU video memory query) never halts core CPU or network throughput telemetry.

---

## 3. Incident Intelligence Pipeline

Traditional monitoring tools inform users *that* a metric spiked; VEYRA determines *why* it spiked and traces the causal path across physical and logical boundaries.

```mermaid
graph LR
    M[Raw Measurement] --> D[Threshold / Baseline Anomaly]
    D --> E[Capture Evidence Window: ±30s]
    E --> C{Cross-Layer Graph Correlation}
    
    C -->|Layer: Wi-Fi NDIS| L1[Wi-Fi Roaming / RSSI Drop]
    C -->|Layer: Gateway| L2[Router Bufferbloat / Packet Loss]
    C -->|Layer: Process| L3[Background Disk / Bandwidth Hog]
    C -->|Layer: DNS| L4[Upstream Resolver Timeout]
    
    L1 --> R[Unified Incident Record]
    L2 --> R
    L3 --> R
    L4 --> R
    
    R --> S[(Persistent Storage: incidents table)]
    R --> UI[Incident Replay & Root Cause UI]
```

### Cross-Layer Root Cause Architecture
When network latency elevates or system throughput degrades, VEYRA correlates:
- **Physical Wi-Fi Signal:** RSSI, BSSID transition, channel contention.
- **Local Network Gateway:** Default route ping latency, ARP table churn.
- **DNS Subsystem:** UDP query duration, fallback nameserver latency.
- **Process Activity:** Top process CPU, working set memory, disk I/O delta, active sockets.

An incident is recorded with its full context (the pre-incident baseline, the trigger sample, and the post-incident recovery), allowing **Incident Replay** to reproduce exact conditions second-by-second.

---

## 4. Historical Storage & Compaction Lifecycle

VEYRA operates without external database servers or cloud telemetry aggregators. Persistent storage is managed via a zero-maintenance local SQLite engine configured for deterministic retention.

```mermaid
stateDiagram-v2
    [*] --> HighResolutionRAM: 1 Hz Raw Telemetry
    HighResolutionRAM --> RingBuffer: Store 300 Samples (5 Min Window)
    RingBuffer --> CompactionWorker: Every 5 Minutes
    
    state CompactionWorker {
        [*] --> ComputeAggregates
        ComputeAggregates --> MinMaxAvgP95: Compute 5-Min Summary
        MinMaxAvgP95 --> WriteRollup: Write to history_rollups
    }
    
    CompactionWorker --> SQLiteWAL: Atomic Transaction
    
    state SQLiteWAL {
        history_rollups --> 7DayRetention: Retain 2016 Rollups
        incidents --> PermanentAudit: Retain All Incident Context
        optimizations --> VerificationRecords: Retain Rollback Snapshots
    }
    
    7DayRetention --> PruneWorker: Daily Purge of Stale Rollups
    PruneWorker --> [*]
```

### Storage Characteristics:
- **Zero Thrashing:** High-frequency 1-second telemetry is maintained exclusively in a pre-allocated RAM circular buffer. Only compacted 5-minute statistical summaries (Min, Max, Avg, P95) are committed to disk.
- **Write-Ahead Logging (WAL):** SQLite operates with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`, preventing database locks during simultaneous UI reads and collector writes.
- **Tamper-Evident Signatures:** Incident and optimization records incorporate HMAC cryptographic signatures to verify state consistency across application restarts.

---

## 5. Safe Optimization & Least-Privilege Security Boundary

VEYRA adheres strictly to the **Principle of Least Privilege**. The main user application, native desktop dashboard, local API, and telemetry analyzers execute as standard, unprivileged user-mode processes.

```mermaid
sequenceDiagram
    autonumber
    participant UI as User Dashboard (Standard User)
    participant Core as Optimization Engine (Standard User)
    participant Storage as State Snapshot Store (Standard User)
    participant Helper as PrivilegedHelper Daemon (Elevated)
    participant OS as Windows Registry / Services

    UI->>Core: Request Optimization (e.g., Network Throttling Disable)
    Core->>Core: Evaluate Baseline & Incident History
    Core->>Storage: Create Cryptographic Pre-State Snapshot
    Core->>Helper: Submit Action Request + Cryptographic Nonce + PID
    Note over Helper: Verify Caller PID, Nonce & Action Allowlist
    Helper->>OS: Apply Narrow Registry / Service Configuration
    OS-->>Helper: Execution Status
    Helper-->>Core: Result + Execution Proof
    Core->>UI: Notify Success & Begin Verification Window
    
    alt Post-Verification Fails (Performance Regressed)
        UI->>Core: Trigger Automatic Rollback
        Core->>Helper: Submit Rollback Request using Snapshot
        Helper->>OS: Restore Original Baseline Configuration
        OS-->>Helper: State Restored
        Core->>UI: Rollback Confirmed
    end
```

### Security Boundary Guarantees:
1. **No Blanket Administrator Shell:** The application executable `VEYRA.exe` never requests administrator rights in its manifest (`requestedExecutionLevel="asInvoker"`).
2. **Authenticated Loopback IPC:** Privileged actions are delegated exclusively to a narrowly scoped `PrivilegedHelper` over loopback socket (`127.0.0.1`), requiring single-use cryptographic tokens.
3. **Strict Action Allowlisting:** The helper only executes explicitly enumerated system configuration commands with strict argument allowlists; arbitrary shell execution (`cmd.exe`, PowerShell arbitrary string execution) is impossible.
4. **Mandatory Rollback Guardian:** Every optimization automatically captures the existing system state in an atomic snapshot before modification, allowing instantaneous, one-click restoration.

---

## 6. Gaming Intelligence & Session DNA Architecture

Gaming mode provides telemetry for esports and high-performance gaming without injecting hook DLLs into game processes.

```mermaid
graph TD
    subgraph Detection [Game Session Detection]
        PROC[Foreground Process Scanner]
        LIB[Game Executable Allowlist / Steam / Epic Scan]
        PROC --> LIB
    end

    subgraph HUD [Gaming HUD: Crimson Theme]
        MIN_OVERLAY[High-Contrast Micro Canvas]
        LATENCY_RADAR[Real-time Jitter & Latency Radar]
        BOTTLENECK_LED[Hardware Bottleneck Indicator]
    end

    subgraph DNA_Engine [Gaming Session DNA Engine]
        SAMPLER[High-Rate Session Sampling: Latency, Frame Drops, Temps]
        CLUSTER[DNA Profiler: Stability Score & Jitter Variance]
        FINGERPRINT[Generate Session DNA Fingerprint]
    end

    LIB -->|Game Launch Detected| HUD
    HUD --> SAMPLER
    SAMPLER --> CLUSTER
    CLUSTER --> FINGERPRINT
    FINGERPRINT -->|Store| DNA_HISTORY[(gaming_sessions Table)]
```

### Gaming Invariants:
- **Zero Anti-Cheat Interference:** VEYRA never uses Windows API hooking (`SetWindowsHookEx`), DLL injection, or kernel memory inspection. Anti-cheat engines (Riot Vanguard, Easy Anti-Cheat, BattlEye) remain unaffected.
- **Session DNA Fingerprint:** Captures stability variance, packet jitter distributions, and GPU/CPU thermal throttling events over the duration of the match to produce an objective session health rating.

---

## 7. Evidence-Grounded AI Boundary

VEYRA contains zero external cloud LLM dependencies, requires zero third-party API keys, and transmits zero user telemetry off the machine.

```mermaid
graph LR
    subgraph Telemetry [Deterministic Data]
        OBS[Physical Measurements]
        INC[Incident Records]
        BASE[Personal Baseline]
    end

    subgraph Engine [Deterministic Analysis Engine]
        RULES[Rule-Based Correlation Graph]
        DIFF[What Changed? Differential Engine]
        EVID[Evidence Packet Formulation]
    end

    subgraph Explanation [Evidence-Grounded Explanation]
        EXPLAIN[Explain My PC / Ask Veyra Engine]
        OUT[Human-Readable Insights with Metric Citations]
    end

    OBS --> RULES
    INC --> RULES
    BASE --> DIFF
    RULES --> EVID
    DIFF --> EVID
    EVID --> EXPLAIN
    EXPLAIN --> OUT
```

- **Rule 10 Adherence:** The reasoning engine operates on verified facts. It answers questions like *"Why was my ping spiking at 8:15 PM?"* by querying actual stored packet loss, BSSID transitions, and process network I/O from that exact timestamp.
- **Zero Hallucination:** Explanations cite verified telemetry timestamps and metric values. If no evidence exists for a causal link, the engine explicitly reports inconclusive data rather than inventing a narrative.

---

## 8. Standalone Production Packaging Architecture

VEYRA packages into an independent Windows desktop application distribution requiring zero host development prerequisites.

```mermaid
graph TD
    subgraph Source_Repo [Development Repository]
        SRC[Python Code, Core Modules]
        ASSETS[assets/branding Locked Assets]
        SPEC[installer/veyra.spec]
    end

    subgraph Build_Pipeline [PyInstaller Build Engine]
        BUILD[installer/build_executable.py]
        ISOLATION[Rule 9 Filter: Exclude simulation/ and tests/]
        BUNDLE[Bundle Python 3.12 DLL + Native C-Extensions + Tkinter]
    end

    subgraph Dist_Artifacts [Release Distribution: dist/VEYRA/]
        EXE[VEYRA.exe: Windows GUI Binary]
        INTERNAL[_internal/: Runtime DLLs, Packages, Branding]
    end

    subgraph Deployment [Deployment Mechanisms]
        INNO[Inno Setup Installer: installer.iss]
        PS1[install.ps1: Automated User-Space Installer]
        BAT[run_veyra.bat: Portable Launcher]
        MSIX[AppxManifest.xml: MSIX Package Spec]
    end

    SRC --> BUILD
    ASSETS --> BUILD
    SPEC --> BUILD
    BUILD --> ISOLATION
    ISOLATION --> BUNDLE
    BUNDLE --> Dist_Artifacts
    Dist_Artifacts --> Deployment
```

### Packaging Highlights:
- **Clean User Separation:** Application binaries install to `%LOCALAPPDATA%\Programs\VEYRA`, while dynamic SQLite records and logs reside in `%LOCALAPPDATA%\VEYRA`.
- **Zero Cloud or Developer Dependencies:** The built executable operates entirely offline on fresh Windows installations without Python, Git, or VS Code.
- **Rule 9 Enforcement:** All chaos engines, simulation fixtures, and synthetic injectors are excluded at packaging time, guaranteeing production distributions ship with zero synthetic data.
