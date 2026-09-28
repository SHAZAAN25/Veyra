"""
VEYRA Storage Engine Contracts & Historical Data Models.
Defines strongly-typed models for SQLite historical records, summaries,
baselines, timeline events, incident replays, and flight recorder snapshots.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import json

from app.core.time import now_utc_iso


class DataQuality(str, Enum):
    """Quality classification of a historical measurement summary."""
    VALID = "VALID"                      # >=95% samples valid and present
    PARTIAL = "PARTIAL"                  # Some valid readings, some unavailable
    DEGRADED = "DEGRADED"                # High volatility or collector reported degraded
    STALE = "STALE"                      # Timestamp gap or stale telemetry
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Too few samples to form a defensible statistic
    UNAVAILABLE = "UNAVAILABLE"          # 0 valid samples in the bucket


class SummaryResolution(int, Enum):
    """Bucket resolution tiers in seconds."""
    MINUTE_1 = 60        # 0–24 Hours
    MINUTE_5 = 300       # 1–7 Days
    MINUTE_30 = 1800     # 7–30 Days
    HOUR_1 = 3600        # 30 Days–1 Year
    DAY_1 = 86400        # >1 Year long-term preservation


class StorageHealthState(str, Enum):
    """Operational health of local SQLite storage."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    PRESSURE_WARNING = "PRESSURE_WARNING"
    CRITICAL = "CRITICAL"
    FAILED = "FAILED"


class TimeContext(str, Enum):
    """Time-of-day contextual partition for baselines."""
    ALL = "ALL"
    PEAK = "PEAK"          # Typically 18:00 - 23:00
    OFF_PEAK = "OFF_PEAK"  # 07:00 - 18:00
    NIGHT = "NIGHT"        # 23:00 - 07:00


@dataclass
class MeasurementSummaryRecord:
    """Historical rollup bucket stored permanently in SQLite."""
    metric_name: str
    bucket_start_utc: str
    bucket_end_utc: str
    resolution_seconds: int
    sample_count: int
    min_value: Optional[float]
    max_value: Optional[float]
    mean_value: Optional[float]
    median_value: Optional[float]
    p95_value: Optional[float]
    std_dev: Optional[float]
    unavailable_count: int = 0
    degraded_count: int = 0
    data_quality: DataQuality = DataQuality.VALID
    unit: str = ""
    summary_id: Optional[int] = None
    created_at_utc: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "metric_name": self.metric_name,
            "bucket_start_utc": self.bucket_start_utc,
            "bucket_end_utc": self.bucket_end_utc,
            "resolution_seconds": self.resolution_seconds,
            "sample_count": self.sample_count,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "mean_value": self.mean_value,
            "median_value": self.median_value,
            "p95_value": self.p95_value,
            "std_dev": self.std_dev,
            "unavailable_count": self.unavailable_count,
            "degraded_count": self.degraded_count,
            "data_quality": self.data_quality.value,
            "unit": self.unit,
            "created_at_utc": self.created_at_utc,
        }


@dataclass
class IncidentRecord:
    """Persisted record of an anomaly or incident."""
    incident_id: str
    incident_type: str
    severity: str
    status: str
    started_at_utc: str
    ended_at_utc: Optional[str]
    duration_seconds: float
    summary: str
    primary_cause: str
    cause_explanation: str
    confidence_score: float
    evidence_quality: str
    relationship: str
    affected_layers: List[str]
    correlation_id: str
    trigger_metric: str
    trigger_value: Optional[float]
    recovery_value: Optional[float]
    baseline_context_json: str = "{}"
    created_at_utc: str = field(default_factory=now_utc_iso)
    updated_at_utc: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "incident_type": self.incident_type,
            "severity": self.severity,
            "status": self.status,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": self.ended_at_utc,
            "duration_seconds": self.duration_seconds,
            "summary": self.summary,
            "primary_cause": self.primary_cause,
            "cause_explanation": self.cause_explanation,
            "confidence_score": self.confidence_score,
            "evidence_quality": self.evidence_quality,
            "relationship": self.relationship,
            "affected_layers": self.affected_layers,
            "correlation_id": self.correlation_id,
            "trigger_metric": self.trigger_metric,
            "trigger_value": self.trigger_value,
            "recovery_value": self.recovery_value,
            "baseline_context": json.loads(self.baseline_context_json or "{}"),
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }


@dataclass
class IncidentEvidenceRecord:
    """Persisted contextual telemetry observations around an incident."""
    evidence_id: str
    incident_id: str
    window_type: str  # "BEFORE", "DURING", "AFTER"
    timestamp_utc: str
    metrics_json: str  # Bounded JSON representation of observations


@dataclass
class BaselineRecord:
    """Persisted Personal PC Baseline statistics."""
    metric_name: str
    version: int
    sample_count: int
    mean: float
    median: float
    min_value: float
    max_value: float
    p95: float
    std_dev: float
    quality: str
    time_context: str = "ALL"
    established_at_utc: str = field(default_factory=now_utc_iso)
    updated_at_utc: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "time_context": self.time_context,
            "version": self.version,
            "sample_count": self.sample_count,
            "mean": self.mean,
            "median": self.median,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "p95": self.p95,
            "std_dev": self.std_dev,
            "quality": self.quality,
            "established_at_utc": self.established_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }


@dataclass
class TimelineEventRecord:
    """Persisted chronological event on the PC Timeline."""
    event_id: str
    timestamp_utc: str
    event_type: str
    severity: str
    source: str
    reference_id: str
    summary: str
    details_json: str = "{}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp_utc": self.timestamp_utc,
            "event_type": self.event_type,
            "severity": self.severity,
            "source": self.source,
            "reference_id": self.reference_id,
            "summary": self.summary,
            "details": json.loads(self.details_json or "{}"),
        }


@dataclass
class ConfigurationChangeRecord:
    """Persisted hardware/network configuration transition."""
    change_id: str
    category: str
    attribute_name: str
    old_value: str
    new_value: str
    detected_at_utc: str
    significance: str = "NORMAL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "category": self.category,
            "attribute_name": self.attribute_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "detected_at_utc": self.detected_at_utc,
            "significance": self.significance,
        }


@dataclass
class RegressionRecord:
    """Persisted performance regression analysis against baseline."""
    regression_id: str
    metric_name: str
    timestamp_utc: str
    baseline_mean: float
    observed_mean: float
    percentage_degradation: float
    is_significant: bool
    confidence: float
    sample_count: int
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regression_id": self.regression_id,
            "metric_name": self.metric_name,
            "timestamp_utc": self.timestamp_utc,
            "baseline_mean": self.baseline_mean,
            "observed_mean": self.observed_mean,
            "percentage_degradation": self.percentage_degradation,
            "is_significant": self.is_significant,
            "confidence": self.confidence,
            "sample_count": self.sample_count,
            "explanation": self.explanation,
        }


@dataclass
class FlightRecorderRecord:
    """Persisted privacy-safe system/network context snapshot."""
    snapshot_id: str
    timestamp_utc: str
    incident_id: str
    trigger_reason: str
    system_state_json: str
    network_state_json: str
    gpu_state_json: str
    collector_health_json: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp_utc": self.timestamp_utc,
            "incident_id": self.incident_id,
            "trigger_reason": self.trigger_reason,
            "system_state": json.loads(self.system_state_json or "{}"),
            "network_state": json.loads(self.network_state_json or "{}"),
            "gpu_state": json.loads(self.gpu_state_json or "{}"),
            "collector_health": json.loads(self.collector_health_json or "{}"),
        }


@dataclass
class StorageStats:
    """Operational monitoring statistics for the storage subsystem."""
    db_size_bytes: int
    max_size_bytes: int
    utilization_pct: float
    oldest_record_utc: Optional[str]
    newest_record_utc: Optional[str]
    summary_count: int
    incident_count: int
    evidence_count: int
    timeline_count: int
    baseline_count: int
    write_latency_ms: float
    write_failures: int
    compaction_runs: int
    storage_health: StorageHealthState

    def to_dict(self) -> Dict[str, Any]:
        return {
            "db_size_bytes": self.db_size_bytes,
            "max_size_bytes": self.max_size_bytes,
            "utilization_pct": self.utilization_pct,
            "oldest_record_utc": self.oldest_record_utc,
            "newest_record_utc": self.newest_record_utc,
            "summary_count": self.summary_count,
            "incident_count": self.incident_count,
            "evidence_count": self.evidence_count,
            "timeline_count": self.timeline_count,
            "baseline_count": self.baseline_count,
            "write_latency_ms": self.write_latency_ms,
            "write_failures": self.write_failures,
            "compaction_runs": self.compaction_runs,
            "storage_health": self.storage_health.value,
        }


@dataclass
class OptimizationHistoryRecord:
    """
    Contract for recording future optimization experiments and A/B verification.
    """
    experiment_id: str
    candidate_id: str
    category: str
    description: str
    before_state_json: str
    action_name: str
    after_state_json: str
    verification_result: str
    rollback_executed: bool
    timestamp_utc: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "candidate_id": self.candidate_id,
            "category": self.category,
            "description": self.description,
            "before_state": json.loads(self.before_state_json or "{}"),
            "action_name": self.action_name,
            "after_state": json.loads(self.after_state_json or "{}"),
            "verification_result": self.verification_result,
            "rollback_executed": bool(self.rollback_executed),
            "timestamp_utc": self.timestamp_utc,
        }


# ==============================================================================
# STAGE 5 EXTENSIONS: DIAGNOSTICS, GAMING SESSIONS & SAFE OPTIMIZATION
# ==============================================================================

@dataclass
class DiagnosticRunRecord:
    """Persisted record of an on-demand diagnostic investigation."""
    run_id: str
    target: str
    run_type: str
    status: str  # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    started_at_utc: str
    ended_at_utc: Optional[str] = None
    duration_seconds: float = 0.0
    assessment: str = ""
    confidence: float = 0.0
    evidence_json: str = "{}"
    affected_layers_json: str = "[]"
    recommendations_json: str = "[]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "target": self.target,
            "run_type": self.run_type,
            "status": self.status,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": self.ended_at_utc,
            "duration_seconds": self.duration_seconds,
            "assessment": self.assessment,
            "confidence": self.confidence,
            "evidence": json.loads(self.evidence_json or "{}"),
            "affected_layers": json.loads(self.affected_layers_json or "[]"),
            "recommendations": json.loads(self.recommendations_json or "[]"),
        }


@dataclass
class DiagnosticResultRecord:
    """Individual test item result within a diagnostic run."""
    result_id: str
    run_id: str
    test_name: str
    target: str
    status: str  # HEALTHY, DEGRADED, FAILED, TIMED_OUT, UNKNOWN
    latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    details_json: str = "{}"
    created_at_utc: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "run_id": self.run_id,
            "test_name": self.test_name,
            "target": self.target,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "packet_loss_pct": self.packet_loss_pct,
            "details": json.loads(self.details_json or "{}"),
            "created_at_utc": self.created_at_utc,
        }


@dataclass
class GamingSessionRecord:
    """Persisted record of an identified gaming session with Session DNA."""
    session_id: str
    game_name: str
    executable: str
    process_id: Optional[int]
    status: str  # DETECTED, ACTIVE, ENDING, COMPLETED, INTERRUPTED
    started_at_utc: str
    ended_at_utc: Optional[str] = None
    duration_seconds: float = 0.0
    fps_available: bool = False
    avg_cpu_pct: Optional[float] = None
    avg_gpu_pct: Optional[float] = None
    avg_ram_pct: Optional[float] = None
    avg_vram_pct: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    incident_count: int = 0
    bottleneck_candidates_json: str = "[]"
    session_dna_json: str = "{}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "game_name": self.game_name,
            "executable": self.executable,
            "process_id": self.process_id,
            "status": self.status,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": self.ended_at_utc,
            "duration_seconds": self.duration_seconds,
            "fps_available": self.fps_available,
            "avg_cpu_pct": self.avg_cpu_pct,
            "avg_gpu_pct": self.avg_gpu_pct,
            "avg_ram_pct": self.avg_ram_pct,
            "avg_vram_pct": self.avg_vram_pct,
            "avg_latency_ms": self.avg_latency_ms,
            "packet_loss_pct": self.packet_loss_pct,
            "incident_count": self.incident_count,
            "bottleneck_candidates": json.loads(self.bottleneck_candidates_json or "[]"),
            "session_dna": json.loads(self.session_dna_json or "{}"),
        }


@dataclass
class GamingProfileRecord:
    """User or system-managed game-specific performance profile."""
    profile_id: str
    game_name: str
    executable: str
    expected_process: str
    preferred_metrics_json: str = "[]"
    baseline_references_json: str = "{}"
    known_config_json: str = "{}"
    created_at_utc: str = field(default_factory=now_utc_iso)
    updated_at_utc: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "game_name": self.game_name,
            "executable": self.executable,
            "expected_process": self.expected_process,
            "preferred_metrics": json.loads(self.preferred_metrics_json or "[]"),
            "baseline_references": json.loads(self.baseline_references_json or "{}"),
            "known_config": json.loads(self.known_config_json or "{}"),
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }


@dataclass
class OptimizationRunRecord:
    """Persisted record of an applied optimization with verification and rollback tracking."""
    run_id: str
    opportunity_id: str
    category: str
    title: str
    state: str  # PROPOSED, AWAITING_APPROVAL, SNAPSHOTTING, APPLYING, VERIFYING, VERIFIED, NO_CHANGE, REGRESSION, ROLLING_BACK, ROLLED_BACK, FAILED, INCONCLUSIVE
    risk_level: str
    requires_elevation: bool
    user_approved: bool
    applied_at_utc: Optional[str] = None
    verified_at_utc: Optional[str] = None
    rolled_back_at_utc: Optional[str] = None
    verification_status: str = "PENDING"
    details_json: str = "{}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "opportunity_id": self.opportunity_id,
            "category": self.category,
            "title": self.title,
            "state": self.state,
            "risk_level": self.risk_level,
            "requires_elevation": self.requires_elevation,
            "user_approved": self.user_approved,
            "applied_at_utc": self.applied_at_utc,
            "verified_at_utc": self.verified_at_utc,
            "rolled_back_at_utc": self.rolled_back_at_utc,
            "verification_status": self.verification_status,
            "details": json.loads(self.details_json or "{}"),
        }


@dataclass
class OptimizationSnapshotRecord:
    """Pre-optimization system snapshot for deterministic rollback."""
    snapshot_id: str
    run_id: str
    optimization_id: str
    timestamp_utc: str
    subsystem: str
    pre_state_json: str
    context_json: str = "{}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "run_id": self.run_id,
            "optimization_id": self.optimization_id,
            "timestamp_utc": self.timestamp_utc,
            "subsystem": self.subsystem,
            "pre_state": json.loads(self.pre_state_json or "{}"),
            "context": json.loads(self.context_json or "{}"),
        }


@dataclass
class OptimizationResultRecord:
    """Detailed verification metrics comparing pre- and post-optimization."""
    result_id: str
    run_id: str
    metric_name: str
    baseline_value: Optional[float]
    post_value: Optional[float]
    difference: Optional[float]
    confidence: float
    outcome: str  # VERIFIED_IMPROVEMENT, NO_MEANINGFUL_CHANGE, REGRESSION, INCONCLUSIVE, APPLICATION_FAILED
    created_at_utc: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "run_id": self.run_id,
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "post_value": self.post_value,
            "difference": self.difference,
            "confidence": self.confidence,
            "outcome": self.outcome,
            "created_at_utc": self.created_at_utc,
        }


@dataclass
class EvidencePackageRecord:
    """Persisted container of deterministic evidence supporting Ask Veyra / Explain My PC answers."""
    package_id: str
    timestamp_utc: str
    query: str
    summary: str
    evidence_json: str
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "timestamp_utc": self.timestamp_utc,
            "query": self.query,
            "summary": self.summary,
            "evidence": json.loads(self.evidence_json or "{}"),
            "confidence": self.confidence,
        }

