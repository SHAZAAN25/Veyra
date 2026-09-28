"""
VEYRA SQLite Storage Engine.
Implements crash-safe, local-first transactional persistence for historical summaries,
incidents, baselines, timeline events, and flight recorder snapshots.
"""
from collections import deque
import json
import logging
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.config import StorageConfig
from app.core.contracts import HistoricalSummary, Incident, Observation, MetricState, MetricUnit
from app.core.exceptions import StorageError
from app.core.time import now_utc_iso
from storage import BaseStorageEngine
from storage.contracts import (
    BaselineRecord,
    ConfigurationChangeRecord,
    DataQuality,
    DiagnosticResultRecord,
    DiagnosticRunRecord,
    EvidencePackageRecord,
    FlightRecorderRecord,
    GamingProfileRecord,
    GamingSessionRecord,
    IncidentEvidenceRecord,
    IncidentRecord,
    MeasurementSummaryRecord,
    OptimizationResultRecord,
    OptimizationRunRecord,
    OptimizationSnapshotRecord,
    RegressionRecord,
    StorageHealthState,
    StorageStats,
    SummaryResolution,
    TimelineEventRecord,
)
from storage.migrations.migration_manager import MigrationManager


logger = logging.getLogger("veyra.storage.sqlite")


class SqliteStorageEngine(BaseStorageEngine):
    """Authoritative local-first SQLite persistence engine."""

    def __init__(self, db_path: str = "history.sqlite", config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self.db_path = str(Path(db_path).resolve())
        
        # Ensure parent directory exists safely
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        # Ephemeral in-memory ring buffer for raw observations
        self._ram_buffer: deque[Observation] = deque(maxlen=self.config.ram_buffer_max_entries)
        
        # Operational metrics
        self._write_failures = 0
        self._last_write_latency_ms = 0.0
        self._compaction_runs = 0
        self._dropped_summaries = 0
        self._is_degraded = False

        # Initialize schema and verify connection
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Creates a configured connection with strict WAL mode and busy timeout."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.config.busy_timeout_ms / 1000.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if self.config.wal_mode:
            cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute(f"PRAGMA busy_timeout = {self.config.busy_timeout_ms};")
        return conn

    def _init_db(self) -> None:
        """Applies migrations and validates schema integrity with corruption detection."""
        self._is_degraded = False
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            row = cursor.fetchone()
            if row and str(row[0]).lower() != "ok":
                logger.critical(f"SQLite integrity check failed on {self.db_path}: {row[0]}")
                self._is_degraded = True
                return

            MigrationManager.apply_migrations(conn)
            MigrationManager.validate_schema(conn)
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            logger.critical(f"SQLite initialization or corruption error on {self.db_path}: {e}")
            self._is_degraded = True
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def close(self) -> None:
        """Flushes buffers and releases resources."""
        self._ram_buffer.clear()

    # --------------------------------------------------------------------------
    # BaseStorageEngine Implementation
    # --------------------------------------------------------------------------

    def append_raw_observation(self, observation: Observation) -> None:
        """Buffers raw observation into ephemeral RAM buffer."""
        if getattr(observation, "is_simulation", False) is True:
            raise ValueError("Rule 9 Violation: Simulation observation cannot be persisted to production storage.")
        self._ram_buffer.append(observation)

    def get_buffered_observations(self) -> List[Observation]:
        """Returns all currently buffered in-memory raw observations."""
        return list(self._ram_buffer)

    def clear_buffered_observations(self) -> None:
        """Clears the ephemeral in-memory buffer."""
        self._ram_buffer.clear()

    def persist_summary(self, summary: HistoricalSummary) -> None:
        """Compatibility adapter for app.core.contracts.HistoricalSummary."""
        record = MeasurementSummaryRecord(
            metric_name=summary.metric_name,
            bucket_start_utc=summary.bucket_start_utc,
            bucket_end_utc=summary.bucket_end_utc,
            resolution_seconds=SummaryResolution.MINUTE_1.value,
            sample_count=summary.count,
            min_value=summary.min_value,
            max_value=summary.max_value,
            mean_value=summary.avg_value,
            median_value=summary.avg_value,
            p95_value=summary.p95_value,
            std_dev=0.0,
            unavailable_count=summary.unavailable_count,
            degraded_count=0,
            data_quality=DataQuality.VALID if summary.count > 0 else DataQuality.UNAVAILABLE,
            unit="",
        )
        self.save_measurement_summary_record(record)

    def query_summaries(
        self,
        metric_name: str,
        start_utc: str,
        end_utc: str,
        bucket_size_minutes: int
    ) -> List[HistoricalSummary]:
        """Compatibility query method returning HistoricalSummary list."""
        resolution_sec = bucket_size_minutes * 60
        records = self.query_measurement_summaries(
            metric_name=metric_name,
            start_utc=start_utc,
            end_utc=end_utc,
            resolution_seconds=resolution_sec
        )
        return [
            HistoricalSummary(
                bucket_start_utc=r.bucket_start_utc,
                bucket_end_utc=r.bucket_end_utc,
                metric_name=r.metric_name,
                count=r.sample_count,
                min_value=r.min_value,
                max_value=r.max_value,
                avg_value=r.mean_value,
                p95_value=r.p95_value,
                unavailable_count=r.unavailable_count,
            )
            for r in records
        ]

    def persist_incident(self, incident: Incident) -> None:
        """Compatibility adapter for app.core.contracts.Incident."""
        record = IncidentRecord(
            incident_id=incident.incident_id,
            incident_type=incident.domain,
            severity=incident.severity,
            status="RECOVERED" if incident.end_time_utc else "ACTIVE",
            started_at_utc=incident.start_time_utc,
            ended_at_utc=incident.end_time_utc,
            duration_seconds=0.0,
            summary=incident.summary,
            primary_cause=incident.root_cause_analysis or "UNKNOWN",
            cause_explanation=incident.root_cause_analysis or "",
            confidence_score=1.0,
            evidence_quality="STRONG",
            relationship="OBSERVED",
            affected_layers=[incident.domain],
            correlation_id="",
            trigger_metric="",
            trigger_value=None,
            recovery_value=None,
        )
        self.save_incident_record(record)

    def query_incidents(self, limit: int = 50) -> List[Incident]:
        """Compatibility query method returning Incident list."""
        records = self.query_incident_records(limit=limit)
        return [
            Incident(
                incident_id=r.incident_id,
                domain=r.incident_type,
                severity=r.severity,
                summary=r.summary,
                start_time_utc=r.started_at_utc,
                end_time_utc=r.ended_at_utc,
                root_cause_analysis=r.cause_explanation,
            )
            for r in records
        ]

    # --------------------------------------------------------------------------
    # Measurement Summary Operations
    # --------------------------------------------------------------------------

    def save_measurement_summary_record(self, record: MeasurementSummaryRecord) -> None:
        """Saves a single MeasurementSummaryRecord atomically."""
        self.save_measurement_summary_records([record])

    def save_measurement_summary_records(self, records: List[MeasurementSummaryRecord]) -> None:
        """Saves a batch of MeasurementSummaryRecords in a single atomic transaction."""
        if not records:
            return

        t0 = time.perf_counter()
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.executemany("""
                INSERT OR REPLACE INTO measurement_summaries (
                    metric_name, bucket_start_utc, bucket_end_utc, resolution_seconds,
                    sample_count, min_value, max_value, mean_value, median_value,
                    p95_value, std_dev, unavailable_count, degraded_count, data_quality,
                    unit, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, [
                    (
                        r.metric_name, r.bucket_start_utc, r.bucket_end_utc, r.resolution_seconds,
                        r.sample_count, r.min_value, r.max_value, r.mean_value, r.median_value,
                        r.p95_value, r.std_dev, r.unavailable_count, r.degraded_count,
                        r.data_quality.value if isinstance(r.data_quality, DataQuality) else str(r.data_quality),
                        r.unit, r.created_at_utc or now_utc_iso()
                    )
                    for r in records
                ])
            self._last_write_latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        except Exception as e:
            self._write_failures += 1
            logger.error(f"Failed to persist measurement summaries: {e}")
            raise StorageError(f"Database write failure: {e}") from e
        finally:
            conn.close()

    def query_measurement_summaries(
        self,
        metric_name: Optional[str] = None,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        resolution_seconds: Optional[int] = None,
        limit: int = 1000
    ) -> List[MeasurementSummaryRecord]:
        """Queries measurement summaries matching provided criteria."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM measurement_summaries WHERE 1=1"
            params: List[Any] = []

            if metric_name:
                query += " AND metric_name = ?"
                params.append(metric_name)
            if start_utc:
                query += " AND bucket_start_utc >= ?"
                params.append(start_utc)
            if end_utc:
                query += " AND bucket_end_utc <= ?"
                params.append(end_utc)
            if resolution_seconds is not None:
                query += " AND resolution_seconds = ?"
                params.append(resolution_seconds)

            query += " ORDER BY bucket_start_utc ASC LIMIT ?"
            params.append(limit)

            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                MeasurementSummaryRecord(
                    summary_id=row["summary_id"],
                    metric_name=row["metric_name"],
                    bucket_start_utc=row["bucket_start_utc"],
                    bucket_end_utc=row["bucket_end_utc"],
                    resolution_seconds=row["resolution_seconds"],
                    sample_count=row["sample_count"],
                    min_value=row["min_value"],
                    max_value=row["max_value"],
                    mean_value=row["mean_value"],
                    median_value=row["median_value"],
                    p95_value=row["p95_value"],
                    std_dev=row["std_dev"],
                    unavailable_count=row["unavailable_count"],
                    degraded_count=row["degraded_count"],
                    data_quality=DataQuality(row["data_quality"]),
                    unit=row["unit"],
                    created_at_utc=row["created_at_utc"]
                )
                for row in rows
            ]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Incident & Evidence Operations
    # --------------------------------------------------------------------------

    def save_incident_record(
        self,
        record: IncidentRecord,
        evidence_records: Optional[List[IncidentEvidenceRecord]] = None
    ) -> None:
        """Persists an incident and its associated evidence records atomically."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO incidents (
                    incident_id, incident_type, severity, status, started_at_utc,
                    ended_at_utc, duration_seconds, summary, primary_cause,
                    cause_explanation, confidence_score, evidence_quality,
                    relationship, affected_layers_json, correlation_id,
                    trigger_metric, trigger_value, recovery_value,
                    baseline_context_json, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    record.incident_id, record.incident_type, record.severity, record.status,
                    record.started_at_utc, record.ended_at_utc, record.duration_seconds,
                    record.summary, record.primary_cause, record.cause_explanation,
                    record.confidence_score, record.evidence_quality, record.relationship,
                    json.dumps(record.affected_layers), record.correlation_id,
                    record.trigger_metric, record.trigger_value, record.recovery_value,
                    record.baseline_context_json or "{}",
                    record.created_at_utc or now_utc_iso(),
                    record.updated_at_utc or now_utc_iso()
                ))

                if evidence_records:
                    cursor.executemany("""
                    INSERT OR REPLACE INTO incident_evidence (
                        evidence_id, incident_id, window_type, timestamp_utc, metrics_json
                    ) VALUES (?, ?, ?, ?, ?);
                    """, [
                        (e.evidence_id, e.incident_id, e.window_type, e.timestamp_utc, e.metrics_json)
                        for e in evidence_records
                    ])
        except Exception as e:
            self._write_failures += 1
            logger.error(f"Failed to persist incident {record.incident_id}: {e}")
            raise StorageError(f"Incident write failure: {e}") from e
        finally:
            conn.close()

    def get_incident_record(self, incident_id: str) -> Optional[IncidentRecord]:
        """Retrieves an incident record by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incidents WHERE incident_id = ?;", (incident_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_incident_record(row)
        finally:
            conn.close()

    def query_incident_records(
        self,
        incident_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        limit: int = 100
    ) -> List[IncidentRecord]:
        """Queries incidents matching filters."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM incidents WHERE 1=1"
            params: List[Any] = []

            if incident_type:
                query += " AND incident_type = ?"
                params.append(incident_type)
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            if status:
                query += " AND status = ?"
                params.append(status)
            if start_utc:
                query += " AND started_at_utc >= ?"
                params.append(start_utc)
            if end_utc:
                query += " AND started_at_utc <= ?"
                params.append(end_utc)

            query += " ORDER BY started_at_utc DESC LIMIT ?"
            params.append(limit)

            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_incident_record(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_incident_evidence(self, incident_id: str) -> List[IncidentEvidenceRecord]:
        """Retrieves all evidence records linked to an incident."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM incident_evidence WHERE incident_id = ? ORDER BY timestamp_utc ASC;",
                (incident_id,)
            )
            return [
                IncidentEvidenceRecord(
                    evidence_id=row["evidence_id"],
                    incident_id=row["incident_id"],
                    window_type=row["window_type"],
                    timestamp_utc=row["timestamp_utc"],
                    metrics_json=row["metrics_json"]
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def _row_to_incident_record(self, row: sqlite3.Row) -> IncidentRecord:
        return IncidentRecord(
            incident_id=row["incident_id"],
            incident_type=row["incident_type"],
            severity=row["severity"],
            status=row["status"],
            started_at_utc=row["started_at_utc"],
            ended_at_utc=row["ended_at_utc"],
            duration_seconds=row["duration_seconds"],
            summary=row["summary"],
            primary_cause=row["primary_cause"],
            cause_explanation=row["cause_explanation"],
            confidence_score=row["confidence_score"],
            evidence_quality=row["evidence_quality"],
            relationship=row["relationship"],
            affected_layers=json.loads(row["affected_layers_json"] or "[]"),
            correlation_id=row["correlation_id"],
            trigger_metric=row["trigger_metric"],
            trigger_value=row["trigger_value"],
            recovery_value=row["recovery_value"],
            baseline_context_json=row["baseline_context_json"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"]
        )

    # --------------------------------------------------------------------------
    # Personal PC Baseline Operations
    # --------------------------------------------------------------------------

    def save_baseline_record(self, baseline: BaselineRecord) -> None:
        """Persists a personal baseline for a metric and time context."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO baselines (
                    metric_name, time_context, version, sample_count, mean, median,
                    min_value, max_value, p95, std_dev, quality, established_at_utc,
                    updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    baseline.metric_name, baseline.time_context, baseline.version,
                    baseline.sample_count, baseline.mean, baseline.median,
                    baseline.min_value, baseline.max_value, baseline.p95,
                    baseline.std_dev, baseline.quality, baseline.established_at_utc,
                    baseline.updated_at_utc
                ))
        finally:
            conn.close()

    def get_baseline_record(self, metric_name: str, time_context: str = "ALL") -> Optional[BaselineRecord]:
        """Retrieves a baseline record by metric and context."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM baselines WHERE metric_name = ? AND time_context = ?;",
                (metric_name, time_context)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return BaselineRecord(
                metric_name=row["metric_name"],
                time_context=row["time_context"],
                version=row["version"],
                sample_count=row["sample_count"],
                mean=row["mean"],
                median=row["median"],
                min_value=row["min_value"],
                max_value=row["max_value"],
                p95=row["p95"],
                std_dev=row["std_dev"],
                quality=row["quality"],
                established_at_utc=row["established_at_utc"],
                updated_at_utc=row["updated_at_utc"]
            )
        finally:
            conn.close()

    def list_all_baselines(self) -> List[BaselineRecord]:
        """Lists all established or running baselines."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM baselines ORDER BY metric_name ASC;")
            return [
                BaselineRecord(
                    metric_name=row["metric_name"],
                    time_context=row["time_context"],
                    version=row["version"],
                    sample_count=row["sample_count"],
                    mean=row["mean"],
                    median=row["median"],
                    min_value=row["min_value"],
                    max_value=row["max_value"],
                    p95=row["p95"],
                    std_dev=row["std_dev"],
                    quality=row["quality"],
                    established_at_utc=row["established_at_utc"],
                    updated_at_utc=row["updated_at_utc"]
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def reset_baselines(self, metric_name: Optional[str] = None) -> int:
        """Resets baselines for a specific metric or all metrics."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                if metric_name:
                    cursor.execute("DELETE FROM baselines WHERE metric_name = ?;", (metric_name,))
                else:
                    cursor.execute("DELETE FROM baselines;")
                return cursor.rowcount
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # PC Timeline Operations
    # --------------------------------------------------------------------------

    def save_timeline_event(self, event: TimelineEventRecord) -> None:
        """Persists a timeline event."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO timeline_events (
                    event_id, timestamp_utc, event_type, severity, source,
                    reference_id, summary, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    event.event_id, event.timestamp_utc, event.event_type,
                    event.severity, event.source, event.reference_id,
                    event.summary, event.details_json or "{}"
                ))
        finally:
            conn.close()

    def query_timeline_events(
        self,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[TimelineEventRecord]:
        """Queries chronological timeline events."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM timeline_events WHERE 1=1"
            params: List[Any] = []

            if start_utc:
                query += " AND timestamp_utc >= ?"
                params.append(start_utc)
            if end_utc:
                query += " AND timestamp_utc <= ?"
                params.append(end_utc)
            if event_types:
                placeholders = ",".join("?" for _ in event_types)
                query += f" AND event_type IN ({placeholders})"
                params.extend(event_types)

            query += " ORDER BY timestamp_utc DESC LIMIT ?"
            params.append(limit)

            cursor = conn.cursor()
            cursor.execute(query, params)
            return [
                TimelineEventRecord(
                    event_id=row["event_id"],
                    timestamp_utc=row["timestamp_utc"],
                    event_type=row["event_type"],
                    severity=row["severity"],
                    source=row["source"],
                    reference_id=row["reference_id"],
                    summary=row["summary"],
                    details_json=row["details_json"]
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Configuration Change Operations
    # --------------------------------------------------------------------------

    def save_configuration_change(self, change: ConfigurationChangeRecord) -> None:
        """Persists a detected configuration change."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO configuration_changes (
                    change_id, category, attribute_name, old_value, new_value,
                    detected_at_utc, significance
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    change.change_id, change.category, change.attribute_name,
                    change.old_value, change.new_value, change.detected_at_utc,
                    change.significance
                ))
        finally:
            conn.close()

    def query_configuration_changes(
        self,
        category: Optional[str] = None,
        start_utc: Optional[str] = None,
        limit: int = 50
    ) -> List[ConfigurationChangeRecord]:
        """Queries configuration change records."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM configuration_changes WHERE 1=1"
            params: List[Any] = []
            if category:
                query += " AND category = ?"
                params.append(category)
            if start_utc:
                query += " AND detected_at_utc >= ?"
                params.append(start_utc)

            query += " ORDER BY detected_at_utc DESC LIMIT ?"
            params.append(limit)

            cursor = conn.cursor()
            cursor.execute(query, params)
            return [
                ConfigurationChangeRecord(
                    change_id=row["change_id"],
                    category=row["category"],
                    attribute_name=row["attribute_name"],
                    old_value=row["old_value"],
                    new_value=row["new_value"],
                    detected_at_utc=row["detected_at_utc"],
                    significance=row["significance"]
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Performance Regression Operations
    # --------------------------------------------------------------------------

    def save_regression_record(self, reg: RegressionRecord) -> None:
        """Persists a detected performance regression."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO performance_regressions (
                    regression_id, metric_name, timestamp_utc, baseline_mean,
                    observed_mean, percentage_degradation, is_significant,
                    confidence, sample_count, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    reg.regression_id, reg.metric_name, reg.timestamp_utc,
                    reg.baseline_mean, reg.observed_mean, reg.percentage_degradation,
                    1 if reg.is_significant else 0, reg.confidence,
                    reg.sample_count, reg.explanation
                ))
        finally:
            conn.close()

    def query_regression_records(
        self,
        metric_name: Optional[str] = None,
        limit: int = 50
    ) -> List[RegressionRecord]:
        """Queries historical regression records."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM performance_regressions WHERE 1=1"
            params: List[Any] = []
            if metric_name:
                query += " AND metric_name = ?"
                params.append(metric_name)

            query += " ORDER BY timestamp_utc DESC LIMIT ?"
            params.append(limit)

            cursor = conn.cursor()
            cursor.execute(query, params)
            return [
                RegressionRecord(
                    regression_id=row["regression_id"],
                    metric_name=row["metric_name"],
                    timestamp_utc=row["timestamp_utc"],
                    baseline_mean=row["baseline_mean"],
                    observed_mean=row["observed_mean"],
                    percentage_degradation=row["percentage_degradation"],
                    is_significant=bool(row["is_significant"]),
                    confidence=row["confidence"],
                    sample_count=row["sample_count"],
                    explanation=row["explanation"]
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Flight Recorder Snapshots
    # --------------------------------------------------------------------------

    def save_flight_recorder_snapshot(self, snapshot: FlightRecorderRecord) -> None:
        """Persists a privacy-safe flight recorder snapshot."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO flight_recorder_snapshots (
                    snapshot_id, timestamp_utc, incident_id, trigger_reason,
                    system_state_json, network_state_json, gpu_state_json,
                    collector_health_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    snapshot.snapshot_id, snapshot.timestamp_utc, snapshot.incident_id,
                    snapshot.trigger_reason, snapshot.system_state_json or "{}",
                    snapshot.network_state_json or "{}", snapshot.gpu_state_json or "{}",
                    snapshot.collector_health_json or "{}"
                ))
        finally:
            conn.close()

    def get_flight_recorder_snapshot(self, snapshot_id: str) -> Optional[FlightRecorderRecord]:
        """Retrieves a flight recorder snapshot by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flight_recorder_snapshots WHERE snapshot_id = ?;", (snapshot_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return FlightRecorderRecord(
                snapshot_id=row["snapshot_id"],
                timestamp_utc=row["timestamp_utc"],
                incident_id=row["incident_id"],
                trigger_reason=row["trigger_reason"],
                system_state_json=row["system_state_json"],
                network_state_json=row["network_state_json"],
                gpu_state_json=row["gpu_state_json"],
                collector_health_json=row["collector_health_json"]
            )
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Stage 5 Diagnostics Persistence
    # --------------------------------------------------------------------------

    def save_diagnostic_run(self, run: DiagnosticRunRecord) -> None:
        """Persists or updates an on-demand diagnostic investigation."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO diagnostic_runs (
                    run_id, target, run_type, status, started_at_utc, ended_at_utc,
                    duration_seconds, assessment, confidence, evidence_json,
                    affected_layers_json, recommendations_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    run.run_id, run.target, run.run_type, run.status,
                    run.started_at_utc, run.ended_at_utc, run.duration_seconds,
                    run.assessment, run.confidence, run.evidence_json or "{}",
                    run.affected_layers_json or "[]", run.recommendations_json or "[]"
                ))
        finally:
            conn.close()

    def get_diagnostic_run(self, run_id: str) -> Optional[DiagnosticRunRecord]:
        """Retrieves a diagnostic run record by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM diagnostic_runs WHERE run_id = ?;", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return DiagnosticRunRecord(
                run_id=row["run_id"],
                target=row["target"],
                run_type=row["run_type"],
                status=row["status"],
                started_at_utc=row["started_at_utc"],
                ended_at_utc=row["ended_at_utc"],
                duration_seconds=float(row["duration_seconds"]),
                assessment=row["assessment"],
                confidence=float(row["confidence"]),
                evidence_json=row["evidence_json"],
                affected_layers_json=row["affected_layers_json"],
                recommendations_json=row["recommendations_json"]
            )
        finally:
            conn.close()

    def list_diagnostic_runs(self, limit: int = 50) -> List[DiagnosticRunRecord]:
        """Lists recent diagnostic runs."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM diagnostic_runs ORDER BY started_at_utc DESC LIMIT ?;",
                (limit,)
            )
            runs = []
            for row in cursor.fetchall():
                runs.append(DiagnosticRunRecord(
                    run_id=row["run_id"],
                    target=row["target"],
                    run_type=row["run_type"],
                    status=row["status"],
                    started_at_utc=row["started_at_utc"],
                    ended_at_utc=row["ended_at_utc"],
                    duration_seconds=float(row["duration_seconds"]),
                    assessment=row["assessment"],
                    confidence=float(row["confidence"]),
                    evidence_json=row["evidence_json"],
                    affected_layers_json=row["affected_layers_json"],
                    recommendations_json=row["recommendations_json"]
                ))
            return runs
        finally:
            conn.close()

    def save_diagnostic_result(self, result: DiagnosticResultRecord) -> None:
        """Persists an individual diagnostic test item result."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO diagnostic_results (
                    result_id, run_id, test_name, target, status,
                    latency_ms, packet_loss_pct, details_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    result.result_id, result.run_id, result.test_name,
                    result.target, result.status, result.latency_ms,
                    result.packet_loss_pct, result.details_json or "{}",
                    result.created_at_utc
                ))
        finally:
            conn.close()

    def get_diagnostic_results_for_run(self, run_id: str) -> List[DiagnosticResultRecord]:
        """Retrieves all diagnostic test results for a specific run."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM diagnostic_results WHERE run_id = ? ORDER BY created_at_utc ASC;",
                (run_id,)
            )
            results = []
            for row in cursor.fetchall():
                results.append(DiagnosticResultRecord(
                    result_id=row["result_id"],
                    run_id=row["run_id"],
                    test_name=row["test_name"],
                    target=row["target"],
                    status=row["status"],
                    latency_ms=row["latency_ms"],
                    packet_loss_pct=row["packet_loss_pct"],
                    details_json=row["details_json"],
                    created_at_utc=row["created_at_utc"]
                ))
            return results
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Stage 5 Gaming Sessions & Profiles Persistence
    # --------------------------------------------------------------------------

    def save_gaming_session(self, session: GamingSessionRecord) -> None:
        """Persists or updates a gaming session record with Session DNA."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO gaming_sessions (
                    session_id, game_name, executable, process_id, status,
                    started_at_utc, ended_at_utc, duration_seconds, fps_available,
                    avg_cpu_pct, avg_gpu_pct, avg_ram_pct, avg_vram_pct,
                    avg_latency_ms, packet_loss_pct, incident_count,
                    bottleneck_candidates_json, session_dna_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    session.session_id, session.game_name, session.executable,
                    session.process_id, session.status, session.started_at_utc,
                    session.ended_at_utc, session.duration_seconds,
                    1 if session.fps_available else 0, session.avg_cpu_pct,
                    session.avg_gpu_pct, session.avg_ram_pct, session.avg_vram_pct,
                    session.avg_latency_ms, session.packet_loss_pct,
                    session.incident_count, session.bottleneck_candidates_json or "[]",
                    session.session_dna_json or "{}"
                ))
        finally:
            conn.close()

    def get_gaming_session(self, session_id: str) -> Optional[GamingSessionRecord]:
        """Retrieves a gaming session by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM gaming_sessions WHERE session_id = ?;", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return GamingSessionRecord(
                session_id=row["session_id"],
                game_name=row["game_name"],
                executable=row["executable"],
                process_id=row["process_id"],
                status=row["status"],
                started_at_utc=row["started_at_utc"],
                ended_at_utc=row["ended_at_utc"],
                duration_seconds=float(row["duration_seconds"]),
                fps_available=bool(row["fps_available"]),
                avg_cpu_pct=row["avg_cpu_pct"],
                avg_gpu_pct=row["avg_gpu_pct"],
                avg_ram_pct=row["avg_ram_pct"],
                avg_vram_pct=row["avg_vram_pct"],
                avg_latency_ms=row["avg_latency_ms"],
                packet_loss_pct=row["packet_loss_pct"],
                incident_count=int(row["incident_count"]),
                bottleneck_candidates_json=row["bottleneck_candidates_json"],
                session_dna_json=row["session_dna_json"]
            )
        finally:
            conn.close()

    def list_gaming_sessions(
        self,
        limit: int = 50,
        game_name: Optional[str] = None
    ) -> List[GamingSessionRecord]:
        """Lists recorded gaming sessions, optionally filtered by game name."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if game_name:
                cursor.execute(
                    "SELECT * FROM gaming_sessions WHERE game_name = ? ORDER BY started_at_utc DESC LIMIT ?;",
                    (game_name, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM gaming_sessions ORDER BY started_at_utc DESC LIMIT ?;",
                    (limit,)
                )
            sessions = []
            for row in cursor.fetchall():
                sessions.append(GamingSessionRecord(
                    session_id=row["session_id"],
                    game_name=row["game_name"],
                    executable=row["executable"],
                    process_id=row["process_id"],
                    status=row["status"],
                    started_at_utc=row["started_at_utc"],
                    ended_at_utc=row["ended_at_utc"],
                    duration_seconds=float(row["duration_seconds"]),
                    fps_available=bool(row["fps_available"]),
                    avg_cpu_pct=row["avg_cpu_pct"],
                    avg_gpu_pct=row["avg_gpu_pct"],
                    avg_ram_pct=row["avg_ram_pct"],
                    avg_vram_pct=row["avg_vram_pct"],
                    avg_latency_ms=row["avg_latency_ms"],
                    packet_loss_pct=row["packet_loss_pct"],
                    incident_count=int(row["incident_count"]),
                    bottleneck_candidates_json=row["bottleneck_candidates_json"],
                    session_dna_json=row["session_dna_json"]
                ))
            return sessions
        finally:
            conn.close()

    def save_gaming_profile(self, profile: GamingProfileRecord) -> None:
        """Saves or updates a game-specific performance profile."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO gaming_profiles (
                    profile_id, game_name, executable, expected_process,
                    preferred_metrics_json, baseline_references_json,
                    known_config_json, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    profile.profile_id, profile.game_name, profile.executable,
                    profile.expected_process, profile.preferred_metrics_json or "[]",
                    profile.baseline_references_json or "{}",
                    profile.known_config_json or "{}", profile.created_at_utc,
                    profile.updated_at_utc
                ))
        finally:
            conn.close()

    def get_gaming_profile(self, profile_id_or_name: str) -> Optional[GamingProfileRecord]:
        """Retrieves a gaming profile by profile_id or game_name."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM gaming_profiles WHERE profile_id = ? OR game_name = ?;",
                (profile_id_or_name, profile_id_or_name)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return GamingProfileRecord(
                profile_id=row["profile_id"],
                game_name=row["game_name"],
                executable=row["executable"],
                expected_process=row["expected_process"],
                preferred_metrics_json=row["preferred_metrics_json"],
                baseline_references_json=row["baseline_references_json"],
                known_config_json=row["known_config_json"],
                created_at_utc=row["created_at_utc"],
                updated_at_utc=row["updated_at_utc"]
            )
        finally:
            conn.close()

    def list_gaming_profiles(self) -> List[GamingProfileRecord]:
        """Lists all registered gaming profiles."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM gaming_profiles ORDER BY game_name ASC;")
            profiles = []
            for row in cursor.fetchall():
                profiles.append(GamingProfileRecord(
                    profile_id=row["profile_id"],
                    game_name=row["game_name"],
                    executable=row["executable"],
                    expected_process=row["expected_process"],
                    preferred_metrics_json=row["preferred_metrics_json"],
                    baseline_references_json=row["baseline_references_json"],
                    known_config_json=row["known_config_json"],
                    created_at_utc=row["created_at_utc"],
                    updated_at_utc=row["updated_at_utc"]
                ))
            return profiles
        finally:
            conn.close()

    def delete_gaming_profile(self, profile_id: str) -> bool:
        """Deletes a gaming profile by ID without removing session history."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM gaming_profiles WHERE profile_id = ?;", (profile_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Stage 5 Optimization Runs, Snapshots & Verification Results
    # --------------------------------------------------------------------------

    def save_optimization_run(self, run: OptimizationRunRecord) -> None:
        """Persists or updates an optimization run record."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO optimization_runs (
                    run_id, opportunity_id, category, title, state, risk_level,
                    requires_elevation, user_approved, applied_at_utc,
                    verified_at_utc, rolled_back_at_utc, verification_status,
                    details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    run.run_id, run.opportunity_id, run.category, run.title,
                    run.state, run.risk_level, 1 if run.requires_elevation else 0,
                    1 if run.user_approved else 0, run.applied_at_utc,
                    run.verified_at_utc, run.rolled_back_at_utc,
                    run.verification_status, run.details_json or "{}"
                ))
        finally:
            conn.close()

    def get_optimization_run(self, run_id: str) -> Optional[OptimizationRunRecord]:
        """Retrieves an optimization run by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM optimization_runs WHERE run_id = ?;", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return OptimizationRunRecord(
                run_id=row["run_id"],
                opportunity_id=row["opportunity_id"],
                category=row["category"],
                title=row["title"],
                state=row["state"],
                risk_level=row["risk_level"],
                requires_elevation=bool(row["requires_elevation"]),
                user_approved=bool(row["user_approved"]),
                applied_at_utc=row["applied_at_utc"],
                verified_at_utc=row["verified_at_utc"],
                rolled_back_at_utc=row["rolled_back_at_utc"],
                verification_status=row["verification_status"],
                details_json=row["details_json"]
            )
        finally:
            conn.close()

    def list_optimization_runs(self, limit: int = 50) -> List[OptimizationRunRecord]:
        """Lists recent optimization runs."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM optimization_runs ORDER BY rowid DESC LIMIT ?;", (limit,))
            runs = []
            for row in cursor.fetchall():
                runs.append(OptimizationRunRecord(
                    run_id=row["run_id"],
                    opportunity_id=row["opportunity_id"],
                    category=row["category"],
                    title=row["title"],
                    state=row["state"],
                    risk_level=row["risk_level"],
                    requires_elevation=bool(row["requires_elevation"]),
                    user_approved=bool(row["user_approved"]),
                    applied_at_utc=row["applied_at_utc"],
                    verified_at_utc=row["verified_at_utc"],
                    rolled_back_at_utc=row["rolled_back_at_utc"],
                    verification_status=row["verification_status"],
                    details_json=row["details_json"]
                ))
            return runs
        finally:
            conn.close()

    def save_optimization_snapshot(self, snapshot: OptimizationSnapshotRecord) -> None:
        """Persists a pre-change snapshot for deterministic rollback."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO optimization_snapshots (
                    snapshot_id, run_id, optimization_id, timestamp_utc,
                    subsystem, pre_state_json, context_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    snapshot.snapshot_id, snapshot.run_id, snapshot.optimization_id,
                    snapshot.timestamp_utc, snapshot.subsystem,
                    snapshot.pre_state_json or "{}", snapshot.context_json or "{}"
                ))
        finally:
            conn.close()

    def get_optimization_snapshot(self, snapshot_id: str) -> Optional[OptimizationSnapshotRecord]:
        """Retrieves an optimization snapshot by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM optimization_snapshots WHERE snapshot_id = ?;", (snapshot_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return OptimizationSnapshotRecord(
                snapshot_id=row["snapshot_id"],
                run_id=row["run_id"],
                optimization_id=row["optimization_id"],
                timestamp_utc=row["timestamp_utc"],
                subsystem=row["subsystem"],
                pre_state_json=row["pre_state_json"],
                context_json=row["context_json"]
            )
        finally:
            conn.close()

    def get_optimization_snapshot_for_run(self, run_id: str) -> Optional[OptimizationSnapshotRecord]:
        """Retrieves the pre-optimization snapshot associated with a specific run."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM optimization_snapshots WHERE run_id = ?;", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return OptimizationSnapshotRecord(
                snapshot_id=row["snapshot_id"],
                run_id=row["run_id"],
                optimization_id=row["optimization_id"],
                timestamp_utc=row["timestamp_utc"],
                subsystem=row["subsystem"],
                pre_state_json=row["pre_state_json"],
                context_json=row["context_json"]
            )
        finally:
            conn.close()

    def save_optimization_result(self, result: OptimizationResultRecord) -> None:
        """Persists a detailed verification result for an optimization run."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO optimization_results (
                    result_id, run_id, metric_name, baseline_value,
                    post_value, difference, confidence, outcome, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    result.result_id, result.run_id, result.metric_name,
                    result.baseline_value, result.post_value, result.difference,
                    result.confidence, result.outcome, result.created_at_utc
                ))
        finally:
            conn.close()

    def get_optimization_results_for_run(self, run_id: str) -> List[OptimizationResultRecord]:
        """Retrieves all verification metric results for an optimization run."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM optimization_results WHERE run_id = ? ORDER BY created_at_utc ASC;",
                (run_id,)
            )
            results = []
            for row in cursor.fetchall():
                results.append(OptimizationResultRecord(
                    result_id=row["result_id"],
                    run_id=row["run_id"],
                    metric_name=row["metric_name"],
                    baseline_value=row["baseline_value"],
                    post_value=row["post_value"],
                    difference=row["difference"],
                    confidence=float(row["confidence"]),
                    outcome=row["outcome"],
                    created_at_utc=row["created_at_utc"]
                ))
            return results
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Stage 5 Evidence Packages Persistence
    # --------------------------------------------------------------------------

    def save_evidence_package(self, pkg: EvidencePackageRecord) -> None:
        """Persists a deterministic evidence package supporting Ask Veyra / Explain My PC."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO evidence_packages (
                    package_id, timestamp_utc, query, summary, evidence_json, confidence
                ) VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    pkg.package_id, pkg.timestamp_utc, pkg.query,
                    pkg.summary, pkg.evidence_json or "{}", pkg.confidence
                ))
        finally:
            conn.close()

    def get_evidence_package(self, package_id: str) -> Optional[EvidencePackageRecord]:
        """Retrieves an evidence package by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM evidence_packages WHERE package_id = ?;", (package_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return EvidencePackageRecord(
                package_id=row["package_id"],
                timestamp_utc=row["timestamp_utc"],
                query=row["query"],
                summary=row["summary"],
                evidence_json=row["evidence_json"],
                confidence=float(row["confidence"])
            )
        finally:
            conn.close()

    def list_evidence_packages(self, limit: int = 20) -> List[EvidencePackageRecord]:
        """Lists recent evidence packages."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM evidence_packages ORDER BY timestamp_utc DESC LIMIT ?;",
                (limit,)
            )
            pkgs = []
            for row in cursor.fetchall():
                pkgs.append(EvidencePackageRecord(
                    package_id=row["package_id"],
                    timestamp_utc=row["timestamp_utc"],
                    query=row["query"],
                    summary=row["summary"],
                    evidence_json=row["evidence_json"],
                    confidence=float(row["confidence"])
                ))
            return pkgs
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Storage Stats, Health & Pressure Management
    # --------------------------------------------------------------------------


    def get_storage_stats(self) -> StorageStats:
        """Gathers runtime storage size, row counts, and health status."""
        try:
            db_size_bytes = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        except OSError:
            db_size_bytes = 0

        max_size_bytes = self.config.max_storage_size_mb * 1024 * 1024
        utilization_pct = round((db_size_bytes / max_size_bytes) * 100.0, 2) if max_size_bytes > 0 else 0.0

        if getattr(self, "_is_degraded", False):
            return StorageStats(
                db_size_bytes=db_size_bytes,
                max_size_bytes=max_size_bytes,
                utilization_pct=utilization_pct,
                oldest_record_utc=None,
                newest_record_utc=None,
                summary_count=0,
                incident_count=0,
                evidence_count=0,
                timeline_count=0,
                baseline_count=0,
                write_latency_ms=self._last_write_latency_ms,
                write_failures=self._write_failures,
                compaction_runs=self._compaction_runs,
                storage_health=StorageHealthState.DEGRADED
            )

        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM measurement_summaries;")
                summary_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM incidents;")
                incident_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM incident_evidence;")
                evidence_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM timeline_events;")
                timeline_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM baselines;")
                baseline_count = cursor.fetchone()[0]

                cursor.execute("SELECT MIN(bucket_start_utc), MAX(bucket_end_utc) FROM measurement_summaries;")
                row = cursor.fetchone()
                oldest_utc = row[0] if row else None
                newest_utc = row[1] if row else None

                # Health classification
                if self._write_failures > 5:
                    health = StorageHealthState.DEGRADED
                elif utilization_pct >= 95.0:
                    health = StorageHealthState.CRITICAL
                elif utilization_pct >= self.config.downsample_threshold_pct:
                    health = StorageHealthState.PRESSURE_WARNING
                else:
                    health = StorageHealthState.HEALTHY

                return StorageStats(
                    db_size_bytes=db_size_bytes,
                    max_size_bytes=max_size_bytes,
                    utilization_pct=utilization_pct,
                    oldest_record_utc=oldest_utc,
                    newest_record_utc=newest_utc,
                    summary_count=summary_count,
                    incident_count=incident_count,
                    evidence_count=evidence_count,
                    timeline_count=timeline_count,
                    baseline_count=baseline_count,
                    write_latency_ms=self._last_write_latency_ms,
                    write_failures=self._write_failures,
                    compaction_runs=self._compaction_runs,
                    storage_health=health
                )
            finally:
                conn.close()
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            logger.error(f"Error querying storage stats from {self.db_path}: {e}")
            self._is_degraded = True
            return StorageStats(
                db_size_bytes=db_size_bytes,
                max_size_bytes=max_size_bytes,
                utilization_pct=utilization_pct,
                oldest_record_utc=None,
                newest_record_utc=None,
                summary_count=0,
                incident_count=0,
                evidence_count=0,
                timeline_count=0,
                baseline_count=0,
                write_latency_ms=self._last_write_latency_ms,
                write_failures=self._write_failures,
                compaction_runs=self._compaction_runs,
                storage_health=StorageHealthState.DEGRADED
            )

    def delete_history_range(
        self,
        start_utc: str,
        end_utc: str,
        metric_name: Optional[str] = None
    ) -> int:
        """Explicitly deletes historical summaries within a given UTC range."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                query = "DELETE FROM measurement_summaries WHERE bucket_start_utc >= ? AND bucket_end_utc <= ?"
                params: List[Any] = [start_utc, end_utc]
                if metric_name:
                    query += " AND metric_name = ?"
                    params.append(metric_name)

                cursor.execute(query, params)
                deleted = cursor.rowcount
                cursor.execute("PRAGMA incremental_vacuum;")
                return deleted
        finally:
            conn.close()

    def reset_database(self) -> None:
        """Resets the entire database by clearing tables and re-applying schema."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA writable_schema = 1;")
                cursor.execute("DELETE FROM sqlite_master WHERE type IN ('table', 'index', 'trigger');")
                cursor.execute("PRAGMA writable_schema = 0;")
                cursor.execute("VACUUM;")
            MigrationManager.apply_migrations(conn)
        finally:
            conn.close()
