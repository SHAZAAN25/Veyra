# VEYRA — Privacy Data Inventory
## Stage 6 Data Minimization & Privacy Protection Specification

**Authoritative Root:** `<project-root>`  
**Document Status:** FROZEN & MANDATORY  
**Target Operating Environment:** Windows 10/11 Desktop (Local-First Engine)

---

## 1. Privacy Principles & Boundaries

1. **Local-First Exclusivity:** All collected data is persisted solely on the local host in SQLite (`storage/sqlite_engine.py`) and memory ring buffers. Zero data is transmitted to cloud servers, remote analytics endpoints, or external APIs.
2. **Data Minimization:** VEYRA only collects measurements strictly required for system observability, network diagnostics, bottleneck detection, and safe optimization.
3. **Strict Credential Proscription:** Passwords, authentication tokens, cookies, browser history, emails, personal files, and packet payloads are NEVER collected, logged, or persisted.
4. **Transparent User Control:** Users can inspect all stored telemetry, purge historical ranges, or perform a total verified reset at any time.

---

## 2. Telemetry & Observation Data Inventory

| Field Name | Category / Purpose | Source | Sensitivity | Retention Schedule | Storage Location | User Visible? | Exportable? | Deletion Behavior |
|---|---|---|---|---|---|---|---|---|
| `cpu_usage_pct` | System load observation | Windows OS / `psutil` | Low | 1-min (24h) → 5-min (7d) → 30-min (30d) → 1h (1yr) → 1d (multi-year) | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `memory_usage_pct` | RAM consumption tracking | Windows OS / `psutil` | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `memory_available_mb` | Memory starvation check | Windows OS / `psutil` | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `disk_utilization_pct` | Disk I/O saturation check | Windows OS / `psutil` | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `gpu_usage_pct` | GPU workload evaluation | `nvidia-smi` CLI (if present) | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `vram_usage_pct` | GPU memory saturation | `nvidia-smi` CLI (if present) | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `gpu_temp_c` | Genuine thermal check | `nvidia-smi` CLI (if present) | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `network_rtt_ms` | Network latency & ping | ICMP ping to Gateway/DNS | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `network_jitter_ms` | RFC 3550 packet jitter | Statistical delta of RTT | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `network_packet_loss_pct`| Network packet drop rate | ICMP probe loss ratio | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `wifi_link_quality_pct` | Wi-Fi connection quality | Windows WLAN API / `netsh` | Low | Same as CPU | SQLite `measurement_summaries` | Yes | Yes (CSV/JSON) | Pruned by compaction; wiped on reset |
| `wifi_ssid` | Wi-Fi network identity | `netsh wlan show interfaces`| Medium | Active session only; sanitized | Ephemeral RAM buffer | Yes | No | Volatile (never stored long-term in rollups) |
| `gateway_ip` | LAN router address | Local IP routing table | Medium | Active session only | Ephemeral RAM buffer | Yes | No | Volatile (not persisted in summary rollups) |

---

## 3. Incident & Diagnostic Intelligence Data Inventory

| Field Name | Category / Purpose | Source | Sensitivity | Retention Schedule | Storage Location | User Visible? | Exportable? | Deletion Behavior |
|---|---|---|---|---|---|---|---|---|
| `incident_id` | Unique incident identifier | VEYRA Incident Engine | Low | Retained with incident (up to 90 days or storage limit) | SQLite `incidents` | Yes | Yes | Explicit incident delete or full reset |
| `severity` | Incident impact triage | VEYRA Incident Engine | Low | Same as incident | SQLite `incidents` | Yes | Yes | Explicit incident delete or full reset |
| `root_cause_node` | Attribution layer | Cross-layer evaluator | Low | Same as incident | SQLite `incidents` | Yes | Yes | Explicit incident delete or full reset |
| `evidence_window` | Before/During/After metrics | Pre-filtered telemetry | Medium | Same as incident (privacy sanitized) | SQLite `incident_evidence` | Yes | Yes | Explicit incident delete or full reset |
| `flight_recorder_snapshot`| Detailed diagnostic context| Subsystem telemetry | High | Sanitized; max 100 snapshots | SQLite `flight_recorder_snapshots` | Yes | Yes | Wiped on purge / full reset |
| `diagnostic_runs` | Active test run record | Diagnostics runner | Low | Bounded history (last 50 runs) | SQLite `diagnostic_runs` | Yes | Yes | Explicit delete or full reset |
| `probe_results` | Probe test breakdown | Diagnostics probes | Low | Linked to diagnostic run | SQLite `diagnostic_results` | Yes | Yes | Cascades with diagnostic run |

---

## 4. Optimization & Gaming Data Inventory

| Field Name | Category / Purpose | Source | Sensitivity | Retention Schedule | Storage Location | User Visible? | Exportable? | Deletion Behavior |
|---|---|---|---|---|---|---|---|---|
| `optimization_run_id` | Optimization run ID | Optimization Engine | Low | Permanent audit log (or full reset)| SQLite `optimization_runs` | Yes | Yes | Wiped on full reset |
| `pre_state_json` | Pre-change configuration | Subsystem query | High | Signed with HMAC; sanitized | SQLite `optimization_snapshots` | Yes | No | Wiped on full reset |
| `improvement_pct` | Verified tuning result | Verification Engine | Low | Permanent audit log | SQLite `optimization_results` | Yes | Yes | Wiped on full reset |
| `game_process_name` | Executable identifier | Process discovery | Low | Session duration | SQLite `gaming_sessions` | Yes | Yes | Deleted with session |
| `session_dna` | Session performance DNA | Session Engine formula | Low | Bounded gaming history | SQLite `gaming_sessions` | Yes | Yes | Deleted with session |
| `gaming_profile` | User game profile rules | User configuration | Low | User-defined lifetime | SQLite `gaming_profiles` | Yes | Yes | User deletion via UI/API |

---

## 5. Security & Authentication Data Inventory

| Field Name | Category / Purpose | Source | Sensitivity | Retention Schedule | Storage Location | User Visible? | Exportable? | Deletion Behavior |
|---|---|---|---|---|---|---|---|---|
| `api_token` | Localhost API Bearer token | `secrets.token_urlsafe(32)` | Critical | Rotatable; regenerated on demand | Local file `.veyra_api_token` (0600) | Yes (In Settings) | No | Revoked / rotated on user demand |
| `authorization_nonce` | Replay protection token | `uuid.uuid4().hex` | High | Single-use; expires in 60 seconds | Ephemeral RAM cache | No | No | Auto-expirations (RAM only) |
| `snapshot_hmac` | Integrity verification hash | HMAC-SHA256 | High | Linked to snapshot lifetime | SQLite `optimization_snapshots` | No | No | Deleted with snapshot |

---

## 6. Prohibited Data (Strict Non-Collection Rule)

The following categories of data are **strictly prohibited** from ever being collected, logged, processed, or persisted by VEYRA under any circumstances:
1. **User Credentials:** Passwords, passphrases, PINs, biometric data, private keys, certificates, SSH keys.
2. **Authentication Artifacts:** Web cookies, session tokens, JWTs, Bearer headers from external applications, OAuth tokens.
3. **Private User Communications:** Emails, messages, chat logs, browser search queries, browser URLs/history, clipboard contents.
4. **Packet Content:** Full network packet payloads (VEYRA performs strictly metric-level probes: RTT, jitter, and loss percentages; zero DPI / packet inspection).
5. **Personal Files:** Documents, source code, media files, or arbitrary user directories.
