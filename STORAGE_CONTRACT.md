# VEYRA — Historical Storage & Compaction Contract

> **Contract Version:** 2.1.0 (Stage 5 Authoritative)  
> **Storage Engine Target:** SQLite (Local-First Compact Rollups) + In-Memory Circular Buffer  
> **Authoritative Root:** `<project-root>`

---

## 1. Storage Philosophy

VEYRA is designed to run 24/7 on end-user desktop machines.

**Continuous raw telemetry storage is strictly forbidden.** Storing raw high-frequency telemetry (e.g., 500ms or 2s intervals) would consume gigabytes of disk space and thrash user SSDs.

Instead, VEYRA enforces an **Ephemeral Buffer + Adaptive Compaction Pipeline**:

```
[ LIVE OBSERVATIONS ]
        │
        ▼ (Transient In-Memory Ring Buffer, max 1,800 entries)
[ RAW MEASUREMENTS ]
        │
        ▼ (Deterministic Statistical Aggregator)
[ 1-MINUTE MEASUREMENT SUMMARIES ]
        │
        ▼ (Atomic Transactional Write)
[ LOCAL SQLITE DATABASE (WAL Mode) ]
        │
        ▼ (Adaptive Compaction Engine)
[ 5-Min → 30-Min → 1-Hour → 1-Day Rollups ]
        │
        ▼ (Controlled Storage Pressure Management)
[ BOUNDED DISK FOOTPRINT: 25 MB – 50 MB / Year ]
```

---

## 2. Adaptive Resolution Hierarchy

The historical compaction engine organizes telemetry summaries into five descending tiers of resolution:

| Tier | Time Horizon | Bucket Resolution | Metrics & Statistics Recorded | Retention & Purpose |
|---|---|---|---|---|
| **Tier 1** | **0 – 24 Hours** | **1-minute** (`60s`) | min, max, mean, median, p95, std_dev, sample_count, unavailable_count, data_quality | High-fidelity recent diagnostics & daily trend review |
| **Tier 2** | **1 – 7 Days** | **5-minute** (`300s`) | min, max, mean, median, p95, std_dev, sample_count, unavailable_count, data_quality | Weekly stability & intermittent issue analysis |
| **Tier 3** | **7 – 30 Days** | **30-minute** (`1800s`) | min, max, mean, median, p95, std_dev, sample_count, unavailable_count, data_quality | Monthly performance baseline comparison |
| **Tier 4** | **30 Days – 1 Year**| **1-hour** (`3600s`) | min, max, mean, median, p95, std_dev, sample_count, unavailable_count, data_quality | Long-term ISP performance verification & seasonality |
| **Tier 5** | **> 1 Year** | **1-day** (`86400s`) | min, max, mean, median, p95, std_dev, sample_count, unavailable_count, data_quality | Multi-year system longevity & ISP SLA audit |

### Compaction Execution Invariant:
1. Aggregate eligible lower-tier records into the target resolution bucket.
2. Validate the statistical rollup.
3. Persist the rolled-up records atomically inside a transaction.
4. Verify persistence.
5. Only then delete superseded lower-tier records.

---

## 3. Storage Pressure Management & Configurable Limits

Storage capacity is strictly bounded. The engine supports configurable storage limits:
- **Presets:** 25 MB, 50 MB (default), 100 MB, 250 MB, 500 MB, 1 GB, or Custom.

When physical database size approaches the configured limit (`downsample_threshold_pct = 90%`):
1. **Recent Data Protected:** Data from the last 24 hours is never pruned.
2. **Critical/High Incidents Protected:** Incidents with `CRITICAL` or `HIGH` severity and their associated evidence windows are permanently shielded.
3. **Personal PC Baseline Integrity Protected:** Established baselines are never purged during compaction.
4. **Controlled Compaction:** Older 1-minute and 5-minute records are accelerated into 30-minute and 1-hour tiers.
5. **Low-Value Pruning:** If pressure remains critical (>95%), non-incident summaries older than 90 days are pruned while preserving daily summaries.
6. **Physical Space Reclamation:** `VACUUM` is executed to reclaim freed pages and defragment the SQLite file.

---

## 4. SQLite Schema & Tables (Version 2)

All operations are executed against a normalized SQLite database managed by `MigrationManager` (`storage/migrations/`). Current schema version: `2`.

### Core Telemetry & Incident Tables (Migration 001):
1. `schema_migrations`: `(version INTEGER PRIMARY KEY, applied_at_utc TEXT, description TEXT)`
2. `schema_metadata`: `(key TEXT PRIMARY KEY, value TEXT)`
3. `measurement_summaries`: Bounded time-series summary rollups across 5 resolution tiers.
4. `incidents`: Full incident lifecycle record with root cause, affected layers, and correlation IDs.
5. `incident_evidence`: Bounded contextual telemetry observations (`BEFORE`, `DURING`, `AFTER`).
6. `baselines`: Statistical personal baseline models per metric and time context (`ALL`, `PEAK`, `OFF_PEAK`, `NIGHT`).
7. `timeline_events`: Chronological PC Timeline entries with structured JSON details.
8. `configuration_changes`: Hardware, adapter, and network state transitions.
9. `performance_regressions`: Verified regression records with baseline comparisons.
10. `flight_recorder_snapshots`: Privacy-sanitized contextual snapshots.
11. `optimization_experiments`: Optimization A/B testing records and outcomes.

### Stage 5 Advanced Diagnostics, Gaming & Safe Optimization Tables (Migration 002):
12. `diagnostic_runs`: Detailed run records (`run_id`, `started_at_utc`, `completed_at_utc`, `status`, `target`, `overall_health`, `root_cause_node`, `assessment`, `confidence_pct`, `recommendations_json`).
13. `diagnostic_results`: Probe test items (`result_id`, `run_id`, `probe_name`, `layer`, `status`, `duration_ms`, `measurements_json`, `observations_json`, `error_message`).
14. `gaming_sessions`: Session records (`session_id`, `game_id`, `game_name`, `process_name`, `state`, `started_at_utc`, `ended_at_utc`, `duration_seconds`, `dna_json`, `metrics_summary_json`).
15. `gaming_profiles`: Configured game profiles (`profile_id`, `game_id`, `name`, `executable_names_json`, `target_fps`, `preferred_power_scheme`, `custom_settings_json`, `created_at_utc`, `updated_at_utc`).
16. `optimization_runs`: Optimization action executions (`run_id`, `opportunity_id`, `title`, `category`, `risk_level`, `affected_subsystem`, `state`, `requires_elevation`, `started_at_utc`, `completed_at_utc`, `error_message`).
17. `optimization_snapshots`: Pre-change configuration snapshots (`snapshot_id`, `run_id`, `subsystem`, `captured_at_utc`, `configuration_json`, `sanitized_metrics_json`, `hash_sha256`).
18. `optimization_results`: Verification and A/B test results (`result_id`, `run_id`, `outcome`, `baseline_window_seconds`, `test_window_seconds`, `pre_change_metrics_json`, `post_change_metrics_json`, `improvement_pct`, `confidence_pct`, `confounders_detected_json`, `rollback_triggered`, `rollback_reason`, `created_at_utc`).
19. `evidence_packages`: Evidence packages for Explain My PC & Ask Veyra (`package_id`, `correlation_id`, `title`, `created_at_utc`, `measurements_json`, `incidents_json`, `timeline_events_json`, `baseline_deviations_json`, `bottleneck_json`, `diagnostics_json`, `confidence_score`).


---

## 5. Non-Negotiable Invariants

1. **Missing != Zero:** If a metric is unavailable or timed out, its value is `None` with `DataQuality.UNAVAILABLE` or `PARTIAL`. It is strictly forbidden to store `0.0` for missing packets or unreachable gateways.
2. **Zero Fabrication:** Statistical metrics are computed strictly from real observations. If fewer samples exist than necessary, statistics are marked `INSUFFICIENT_DATA`.
3. **Anti-Contamination Baseline Policy:** Measurements captured during active incident periods are strictly excluded from baseline evolutionary updates.
4. **Crash Safety & Atomic Transactions:** Every SQLite mutation is executed inside a transaction. In the event of process interruption, the transaction is rolled back completely.
5. **Absolute Privacy:** Passwords, tokens, browser history, cookies, and raw packet payloads are never stored. Privacy verification guards reject any snapshot containing credential keywords.
6. **Local-First Isolation:** Database resides exclusively in the local application directory. Zero cloud synchronization or external transmission.

---

## 6. Stage 6 Reliability & Corruption Handling

1. **Startup Integrity Check:** Every connection initialization issues `PRAGMA integrity_check`. If the database returns errors or fails to pass the integrity check, VEYRA records an audit event and transitions to `StorageHealthState.DEGRADED`.
2. **Graceful Fallback:** When SQLite encounters corruption, disk-full conditions, or I/O errors, storage operations fail safely without crashing the real-time monitoring coordinator or GUI.
3. **Data Minimization & User Deletion:** Provides explicit interfaces for user-requested historical deletion (`delete_history_range`, incident reset, session reset) which securely remove rows without leaving dangling orphaned records.
4. **HMAC Signing for Snapshots:** Pre-change optimization snapshots verify HMAC-SHA256 signatures before being utilized for rollbacks.

