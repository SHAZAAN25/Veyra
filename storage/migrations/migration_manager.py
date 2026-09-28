"""
VEYRA Schema Migration Manager.
Handles deterministic database schema versioning, incremental migrations,
schema verification, and transaction rollback on migration failure.
"""
import sqlite3
from typing import List, Tuple, Callable
import logging

from app.core.exceptions import StorageError
from app.core.time import now_utc_iso

logger = logging.getLogger("veyra.storage.migrations")

# Target schema version
CURRENT_SCHEMA_VERSION = 2



def _migration_001(cursor: sqlite3.Cursor) -> None:
    """Migration 1: Initial VEYRA Historical Intelligence Schema."""
    # 1. Schema metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # 2. Measurement Summaries (Adaptive historical rollups: 1m, 5m, 30m, 1h, 1d)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS measurement_summaries (
        summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_name TEXT NOT NULL,
        bucket_start_utc TEXT NOT NULL,
        bucket_end_utc TEXT NOT NULL,
        resolution_seconds INTEGER NOT NULL,
        sample_count INTEGER NOT NULL,
        min_value REAL,
        max_value REAL,
        mean_value REAL,
        median_value REAL,
        p95_value REAL,
        std_dev REAL,
        unavailable_count INTEGER DEFAULT 0,
        degraded_count INTEGER DEFAULT 0,
        data_quality TEXT NOT NULL,
        unit TEXT NOT NULL,
        created_at_utc TEXT NOT NULL,
        CONSTRAINT uq_summary_metric_bucket UNIQUE (metric_name, bucket_start_utc, resolution_seconds)
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_metric_time ON measurement_summaries(metric_name, bucket_start_utc);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_time ON measurement_summaries(bucket_start_utc);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_resolution ON measurement_summaries(resolution_seconds, bucket_start_utc);")

    # 3. Incidents
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id TEXT PRIMARY KEY,
        incident_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at_utc TEXT NOT NULL,
        ended_at_utc TEXT,
        duration_seconds REAL NOT NULL,
        summary TEXT NOT NULL,
        primary_cause TEXT NOT NULL,
        cause_explanation TEXT NOT NULL,
        confidence_score REAL NOT NULL,
        evidence_quality TEXT NOT NULL,
        relationship TEXT NOT NULL,
        affected_layers_json TEXT NOT NULL,
        correlation_id TEXT NOT NULL,
        trigger_metric TEXT NOT NULL,
        trigger_value REAL,
        recovery_value REAL,
        baseline_context_json TEXT NOT NULL,
        created_at_utc TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_started ON incidents(started_at_utc);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_correlation ON incidents(correlation_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents(incident_type);")

    # 4. Incident Evidence (Contextual observation points before, during, after)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incident_evidence (
        evidence_id TEXT PRIMARY KEY,
        incident_id TEXT NOT NULL,
        window_type TEXT NOT NULL,
        timestamp_utc TEXT NOT NULL,
        metrics_json TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_incident ON incident_evidence(incident_id, window_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_time ON incident_evidence(timestamp_utc);")

    # 5. Personal PC Baselines
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS baselines (
        metric_name TEXT NOT NULL,
        time_context TEXT NOT NULL DEFAULT 'ALL',
        version INTEGER NOT NULL,
        sample_count INTEGER NOT NULL,
        mean REAL NOT NULL,
        median REAL NOT NULL,
        min_value REAL NOT NULL,
        max_value REAL NOT NULL,
        p95 REAL NOT NULL,
        std_dev REAL NOT NULL,
        quality TEXT NOT NULL,
        established_at_utc TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL,
        PRIMARY KEY (metric_name, time_context)
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_baselines_quality ON baselines(quality);")

    # 6. PC Timeline Events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS timeline_events (
        event_id TEXT PRIMARY KEY,
        timestamp_utc TEXT NOT NULL,
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        source TEXT NOT NULL,
        reference_id TEXT NOT NULL,
        summary TEXT NOT NULL,
        details_json TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeline_time ON timeline_events(timestamp_utc);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeline_type ON timeline_events(event_type);")

    # 7. Configuration Changes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS configuration_changes (
        change_id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        attribute_name TEXT NOT NULL,
        old_value TEXT NOT NULL,
        new_value TEXT NOT NULL,
        detected_at_utc TEXT NOT NULL,
        significance TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_time ON configuration_changes(detected_at_utc);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_cat ON configuration_changes(category);")

    # 8. Performance Regressions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS performance_regressions (
        regression_id TEXT PRIMARY KEY,
        metric_name TEXT NOT NULL,
        timestamp_utc TEXT NOT NULL,
        baseline_mean REAL NOT NULL,
        observed_mean REAL NOT NULL,
        percentage_degradation REAL NOT NULL,
        is_significant INTEGER NOT NULL,
        confidence REAL NOT NULL,
        sample_count INTEGER NOT NULL,
        explanation TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_regressions_time ON performance_regressions(timestamp_utc);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_regressions_metric ON performance_regressions(metric_name);")

    # 9. Flight Recorder Snapshots
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS flight_recorder_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        timestamp_utc TEXT NOT NULL,
        incident_id TEXT NOT NULL,
        trigger_reason TEXT NOT NULL,
        system_state_json TEXT NOT NULL,
        network_state_json TEXT NOT NULL,
        gpu_state_json TEXT NOT NULL,
        collector_health_json TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_flight_recorder_time ON flight_recorder_snapshots(timestamp_utc);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_flight_recorder_incident ON flight_recorder_snapshots(incident_id);")

    # 10. Optimization Experiment History (Contract foundation for future A/B tests)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS optimization_experiments (
        experiment_id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        before_state_json TEXT NOT NULL,
        action_name TEXT NOT NULL,
        after_state_json TEXT NOT NULL,
        verification_result TEXT NOT NULL,
        rollback_executed INTEGER NOT NULL,
        timestamp_utc TEXT NOT NULL
    );
    """)

    # Populate metadata
    cursor.execute(
        "INSERT OR REPLACE INTO schema_metadata (key, value) VALUES (?, ?);",
        ("schema_version", "1")
    )
    cursor.execute(
        "INSERT OR REPLACE INTO schema_metadata (key, value) VALUES (?, ?);",
        ("app_name", "VEYRA")
    )


def _migration_002(cursor: sqlite3.Cursor) -> None:
    """Migration 2: Stage 5 Diagnostics, Gaming Sessions, and Safe Optimization Schema."""
    # 1. Diagnostic Runs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_runs (
        run_id TEXT PRIMARY KEY,
        target TEXT NOT NULL,
        run_type TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at_utc TEXT NOT NULL,
        ended_at_utc TEXT,
        duration_seconds REAL NOT NULL,
        assessment TEXT NOT NULL,
        confidence REAL NOT NULL,
        evidence_json TEXT NOT NULL,
        affected_layers_json TEXT NOT NULL,
        recommendations_json TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diag_runs_time ON diagnostic_runs(started_at_utc);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diag_runs_status ON diagnostic_runs(status);")

    # 2. Diagnostic Results
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnostic_results (
        result_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        test_name TEXT NOT NULL,
        target TEXT NOT NULL,
        status TEXT NOT NULL,
        latency_ms REAL,
        packet_loss_pct REAL,
        details_json TEXT NOT NULL,
        created_at_utc TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES diagnostic_runs(run_id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diag_results_run ON diagnostic_results(run_id);")

    # 3. Gaming Sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gaming_sessions (
        session_id TEXT PRIMARY KEY,
        game_name TEXT NOT NULL,
        executable TEXT NOT NULL,
        process_id INTEGER,
        status TEXT NOT NULL,
        started_at_utc TEXT NOT NULL,
        ended_at_utc TEXT,
        duration_seconds REAL NOT NULL,
        fps_available INTEGER NOT NULL DEFAULT 0,
        avg_cpu_pct REAL,
        avg_gpu_pct REAL,
        avg_ram_pct REAL,
        avg_vram_pct REAL,
        avg_latency_ms REAL,
        packet_loss_pct REAL,
        incident_count INTEGER NOT NULL DEFAULT 0,
        bottleneck_candidates_json TEXT NOT NULL,
        session_dna_json TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gaming_sessions_time ON gaming_sessions(started_at_utc);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gaming_sessions_game ON gaming_sessions(game_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gaming_sessions_status ON gaming_sessions(status);")

    # 4. Gaming Profiles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gaming_profiles (
        profile_id TEXT PRIMARY KEY,
        game_name TEXT NOT NULL UNIQUE,
        executable TEXT NOT NULL,
        expected_process TEXT NOT NULL,
        preferred_metrics_json TEXT NOT NULL,
        baseline_references_json TEXT NOT NULL,
        known_config_json TEXT NOT NULL,
        created_at_utc TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gaming_profiles_game ON gaming_profiles(game_name);")

    # 5. Optimization Runs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS optimization_runs (
        run_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        state TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        requires_elevation INTEGER NOT NULL,
        user_approved INTEGER NOT NULL,
        applied_at_utc TEXT,
        verified_at_utc TEXT,
        rolled_back_at_utc TEXT,
        verification_status TEXT NOT NULL,
        details_json TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_opt_runs_opp ON optimization_runs(opportunity_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_opt_runs_state ON optimization_runs(state);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_opt_runs_applied ON optimization_runs(applied_at_utc);")

    # 6. Optimization Snapshots
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS optimization_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        optimization_id TEXT NOT NULL,
        timestamp_utc TEXT NOT NULL,
        subsystem TEXT NOT NULL,
        pre_state_json TEXT NOT NULL,
        context_json TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_opt_snapshots_run ON optimization_snapshots(run_id);")

    # 7. Optimization Results
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS optimization_results (
        result_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        baseline_value REAL,
        post_value REAL,
        difference REAL,
        confidence REAL NOT NULL,
        outcome TEXT NOT NULL,
        created_at_utc TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES optimization_runs(run_id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_opt_results_run ON optimization_results(run_id);")

    # 8. Evidence Packages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evidence_packages (
        package_id TEXT PRIMARY KEY,
        timestamp_utc TEXT NOT NULL,
        query TEXT NOT NULL,
        summary TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        confidence REAL NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_pkg_time ON evidence_packages(timestamp_utc);")

    # Update metadata to version 2
    cursor.execute(
        "INSERT OR REPLACE INTO schema_metadata (key, value) VALUES (?, ?);",
        ("schema_version", "2")
    )


# Ordered registry of migrations: (version, description, migration_func)
MIGRATIONS: List[Tuple[int, str, Callable[[sqlite3.Cursor], None]]] = [
    (1, "Initial VEYRA Historical Intelligence Schema", _migration_001),
    (2, "Stage 5 Diagnostics, Gaming Sessions, and Safe Optimization Schema", _migration_002),
]


class MigrationManager:
    """Manages SQLite schema version inspection and migrations."""

    @staticmethod
    def get_current_version(conn: sqlite3.Connection) -> int:
        """Determines the current migration version of the database."""
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_utc TEXT NOT NULL,
            description TEXT NOT NULL
        );
        """)
        cursor.execute("SELECT MAX(version) FROM schema_migrations;")
        row = cursor.fetchone()
        return row[0] if (row and row[0] is not None) else 0

    @classmethod
    def apply_migrations(cls, conn: sqlite3.Connection) -> int:
        """
        Executes pending migrations within transactions.
        Rolls back immediately if any migration step fails.
        """
        current_version = cls.get_current_version(conn)
        applied_count = 0

        for version, description, func in MIGRATIONS:
            if version > current_version:
                logger.info(f"Applying migration {version}: {description}")
                try:
                    with conn:
                        cursor = conn.cursor()
                        func(cursor)
                        cursor.execute(
                            "INSERT INTO schema_migrations (version, applied_at_utc, description) VALUES (?, ?, ?);",
                            (version, now_utc_iso(), description)
                        )
                    applied_count += 1
                except Exception as e:
                    logger.error(f"Migration {version} failed: {e}")
                    raise StorageError(f"Database migration {version} failed: {e}") from e

        return applied_count

    @classmethod
    def validate_schema(cls, conn: sqlite3.Connection) -> bool:
        """Verifies that all required tables and indices exist and database is sound."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        row = cursor.fetchone()
        if not row or row[0].lower() != "ok":
            raise StorageError(f"SQLite integrity check failed: {row[0] if row else 'Unknown error'}")

        required_tables = [
            "schema_migrations", "schema_metadata", "measurement_summaries",
            "incidents", "incident_evidence", "baselines", "timeline_events",
            "configuration_changes", "performance_regressions",
            "flight_recorder_snapshots", "optimization_experiments",
            "diagnostic_runs", "diagnostic_results", "gaming_sessions",
            "gaming_profiles", "optimization_runs", "optimization_snapshots",
            "optimization_results", "evidence_packages"
        ]
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = {r[0] for r in cursor.fetchall()}
        missing = [t for t in required_tables if t not in existing_tables]
        if missing:
            raise StorageError(f"Database schema validation failed. Missing tables: {missing}")

        return True

