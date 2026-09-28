"""
VEYRA Master Storage Engine Facade.
Unifies SQLite persistence, statistical metric aggregation, adaptive retention compaction,
incident storage, replay reconstruction, baseline evolution, and timeline queries into
a single coherent, failure-isolated subsystem.
"""
from typing import Any, Dict, List, Optional
import logging

from app.core.config import StorageConfig
from app.core.contracts import HistoricalSummary, Incident, Observation
from storage import BaseStorageEngine
from storage.aggregation.aggregator import MetricAggregator
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
    StorageStats,
    SummaryResolution,
    TimelineEventRecord,
)
from storage.history.baseline_store import PersistentBaselineStore
from storage.history.comparison_engine import HistoricalComparisonEngine
from storage.history.flight_recorder_store import PersistentFlightRecorderStore
from storage.history.incident_store import HistoricalIncidentStore
from storage.history.replay_store import IncidentReplayStore
from storage.history.timeline_store import PersistentTimelineStore
from storage.retention.compactor import CompactionEngine
from storage.sqlite_engine import SqliteStorageEngine

logger = logging.getLogger("veyra.storage.master_engine")


class StorageEngine(BaseStorageEngine):
    """
    Master Storage Facade for VEYRA Historical Memory.
    Provides complete lifecycle management from RAM buffering to SQLite compaction.
    """

    def __init__(self, db_path: str = "history.sqlite", config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self.sqlite = SqliteStorageEngine(db_path=db_path, config=self.config)
        self.aggregator = MetricAggregator()
        self.compactor = CompactionEngine(engine=self.sqlite, config=self.config)
        self.incidents = HistoricalIncidentStore(engine=self.sqlite)
        self.replay = IncidentReplayStore(incident_store=self.incidents)
        self.flight_recorder = PersistentFlightRecorderStore(engine=self.sqlite)
        self.baselines = PersistentBaselineStore(engine=self.sqlite)
        self.timeline = PersistentTimelineStore(engine=self.sqlite)
        self.comparison = HistoricalComparisonEngine(engine=self.sqlite, baseline_store=self.baselines)

    # --------------------------------------------------------------------------
    # BaseStorageEngine Protocol Methods
    # --------------------------------------------------------------------------

    def append_raw_observation(self, observation: Observation) -> None:
        """Buffers raw observation into ephemeral RAM buffer."""
        self.sqlite.append_raw_observation(observation)

    def persist_summary(self, summary: HistoricalSummary) -> None:
        """Compatibility adapter for HistoricalSummary."""
        self.sqlite.persist_summary(summary)

    def query_summaries(
        self,
        metric_name: str,
        start_utc: str,
        end_utc: str,
        bucket_size_minutes: int
    ) -> List[HistoricalSummary]:
        """Compatibility query method for HistoricalSummary."""
        return self.sqlite.query_summaries(metric_name, start_utc, end_utc, bucket_size_minutes)

    def persist_incident(self, incident: Incident) -> None:
        """Compatibility adapter for Incident."""
        self.sqlite.persist_incident(incident)

    def query_incidents(self, limit: int = 50) -> List[Incident]:
        """Compatibility query method for Incident."""
        return self.sqlite.query_incidents(limit)

    # --------------------------------------------------------------------------
    # Enhanced Stage 3 Historical Intelligence Methods
    # --------------------------------------------------------------------------

    def flush_buffer_to_summaries(
        self,
        bucket_start_utc: str,
        bucket_end_utc: str,
        clear_buffer: bool = True
    ) -> List[MeasurementSummaryRecord]:
        """
        Aggregates currently buffered raw observations in RAM into 1-minute historical summaries,
        atomically writes them to SQLite, and clears the in-memory buffer.
        """
        observations = self.sqlite.get_buffered_observations()
        if not observations:
            return []

        summaries = self.aggregator.aggregate_observations(
            observations=observations,
            bucket_start_utc=bucket_start_utc,
            bucket_end_utc=bucket_end_utc,
            resolution_seconds=SummaryResolution.MINUTE_1.value
        )

        if summaries:
            self.sqlite.save_measurement_summary_records(summaries)

        if clear_buffer:
            self.sqlite.clear_buffered_observations()

        return summaries

    def run_compaction(self) -> Dict[str, int]:
        """Executes adaptive retention compaction rollups across all time horizons."""
        return self.compactor.run_compaction_cycle()

    def handle_pressure(self) -> Dict[str, Any]:
        """Enforces storage limits and controlled degradation."""
        return self.compactor.handle_storage_pressure()

    def get_stats(self) -> StorageStats:
        """Returns operational storage metrics and health state."""
        return self.sqlite.get_storage_stats()

    # --------------------------------------------------------------------------
    # Stage 5 Facade Methods
    # --------------------------------------------------------------------------

    def save_diagnostic_run(self, run: DiagnosticRunRecord) -> None:
        self.sqlite.save_diagnostic_run(run)

    def get_diagnostic_run(self, run_id: str) -> Optional[DiagnosticRunRecord]:
        return self.sqlite.get_diagnostic_run(run_id)

    def list_diagnostic_runs(self, limit: int = 50) -> List[DiagnosticRunRecord]:
        return self.sqlite.list_diagnostic_runs(limit)

    def save_diagnostic_result(self, result: DiagnosticResultRecord) -> None:
        self.sqlite.save_diagnostic_result(result)

    def get_diagnostic_results_for_run(self, run_id: str) -> List[DiagnosticResultRecord]:
        return self.sqlite.get_diagnostic_results_for_run(run_id)

    def save_gaming_session(self, session: GamingSessionRecord) -> None:
        self.sqlite.save_gaming_session(session)

    def get_gaming_session(self, session_id: str) -> Optional[GamingSessionRecord]:
        return self.sqlite.get_gaming_session(session_id)

    def list_gaming_sessions(self, limit: int = 50, game_name: Optional[str] = None) -> List[GamingSessionRecord]:
        return self.sqlite.list_gaming_sessions(limit, game_name)

    def save_gaming_profile(self, profile: GamingProfileRecord) -> None:
        self.sqlite.save_gaming_profile(profile)

    def get_gaming_profile(self, profile_id_or_name: str) -> Optional[GamingProfileRecord]:
        return self.sqlite.get_gaming_profile(profile_id_or_name)

    def list_gaming_profiles(self) -> List[GamingProfileRecord]:
        return self.sqlite.list_gaming_profiles()

    def delete_gaming_profile(self, profile_id: str) -> bool:
        return self.sqlite.delete_gaming_profile(profile_id)

    def save_optimization_run(self, run: OptimizationRunRecord) -> None:
        self.sqlite.save_optimization_run(run)

    def get_optimization_run(self, run_id: str) -> Optional[OptimizationRunRecord]:
        return self.sqlite.get_optimization_run(run_id)

    def list_optimization_runs(self, limit: int = 50) -> List[OptimizationRunRecord]:
        return self.sqlite.list_optimization_runs(limit)

    def save_optimization_snapshot(self, snapshot: OptimizationSnapshotRecord) -> None:
        self.sqlite.save_optimization_snapshot(snapshot)

    def get_optimization_snapshot(self, snapshot_id: str) -> Optional[OptimizationSnapshotRecord]:
        return self.sqlite.get_optimization_snapshot(snapshot_id)

    def get_optimization_snapshot_for_run(self, run_id: str) -> Optional[OptimizationSnapshotRecord]:
        return self.sqlite.get_optimization_snapshot_for_run(run_id)

    def save_optimization_result(self, result: OptimizationResultRecord) -> None:
        self.sqlite.save_optimization_result(result)

    def get_optimization_results_for_run(self, run_id: str) -> List[OptimizationResultRecord]:
        return self.sqlite.get_optimization_results_for_run(run_id)

    def save_evidence_package(self, pkg: EvidencePackageRecord) -> None:
        self.sqlite.save_evidence_package(pkg)

    def get_evidence_package(self, package_id: str) -> Optional[EvidencePackageRecord]:
        return self.sqlite.get_evidence_package(package_id)

    def list_evidence_packages(self, limit: int = 20) -> List[EvidencePackageRecord]:
        return self.sqlite.list_evidence_packages(limit)

