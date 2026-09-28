"""
VEYRA Analyzer Contracts & Intelligence Foundation Models.
Defines deterministic types for Incidents, Evidence Windows, Root Cause Analysis,
Personal PC Baselining, "What Changed?", Regression Detection, Bottleneck Investigation,
and Future Optimization/AI Contracts.
"""
from dataclasses import dataclass, field
from enum import Enum
import time
import uuid
from typing import Any, Dict, List, Optional

from app.core.contracts import Observation, Measurement
from app.core.time import now_utc_iso


class IncidentStatus(str, Enum):
    """Lifecycle states of a detected incident."""
    DETECTED = "DETECTED"
    ACTIVE = "ACTIVE"
    RECOVERED = "RECOVERED"


class IncidentSeverity(str, Enum):
    """Deterministic severity levels."""
    INFO = "INFO"            # Informational, non-impacting configuration or state change
    WARNING = "WARNING"      # Meaningful performance or quality degradation
    HIGH = "HIGH"            # Significant sustained degradation or service disruption
    CRITICAL = "CRITICAL"    # Complete outage, packet failure, or hardware throttling


class IncidentType(str, Enum):
    """16 Core Deterministic Incident Categories."""
    PACKET_LOSS_SPIKE = "PACKET_LOSS_SPIKE"
    LATENCY_SPIKE = "LATENCY_SPIKE"
    JITTER_SPIKE = "JITTER_SPIKE"
    WIFI_DISCONNECT = "WIFI_DISCONNECT"
    WIFI_RECONNECT = "WIFI_RECONNECT"
    GATEWAY_UNREACHABLE = "GATEWAY_UNREACHABLE"
    DNS_FAILURE = "DNS_FAILURE"
    INTERNET_UNREACHABLE = "INTERNET_UNREACHABLE"
    WIFI_SIGNAL_DEGRADATION = "WIFI_SIGNAL_DEGRADATION"
    LINK_SPEED_CHANGE = "LINK_SPEED_CHANGE"
    NETWORK_ADAPTER_CHANGE = "NETWORK_ADAPTER_CHANGE"
    MULTI_LAYER_NETWORK_FAILURE = "MULTI_LAYER_NETWORK_FAILURE"
    SYSTEM_RESOURCE_PRESSURE = "SYSTEM_RESOURCE_PRESSURE"
    GPU_RESOURCE_PRESSURE = "GPU_RESOURCE_PRESSURE"
    HARDWARE_BOTTLENECK_CANDIDATE = "HARDWARE_BOTTLENECK_CANDIDATE"
    OBSERVATION_GAP_SLEEP_RESUME = "OBSERVATION_GAP_SLEEP_RESUME"


class EvidenceQuality(str, Enum):
    """Technical evaluation of evidence sufficiency."""
    STRONG = "STRONG"              # Multiple correlated observations across multiple probes
    MODERATE = "MODERATE"          # Clear observations from primary collector with good confidence
    LIMITED = "LIMITED"            # Few samples or transient threshold crossing
    INSUFFICIENT = "INSUFFICIENT"  # Inconclusive data or conflicting probes


class RootCauseCategory(str, Enum):
    """Deterministic root cause domains."""
    LOCAL_DEVICE_ADAPTER = "LOCAL_DEVICE_ADAPTER"
    WIFI_LINK = "WIFI_LINK"
    GATEWAY_LOCAL_NETWORK = "GATEWAY_LOCAL_NETWORK"
    DNS_SUBSYSTEM = "DNS_SUBSYSTEM"
    UPSTREAM_INTERNET = "UPSTREAM_INTERNET"
    SYSTEM_RESOURCE_PRESSURE = "SYSTEM_RESOURCE_PRESSURE"
    GPU_COMPUTE_PRESSURE = "GPU_COMPUTE_PRESSURE"
    OBSERVATION_GAP_SUSPENSION = "OBSERVATION_GAP_SUSPENSION"
    CAUSE_UNDETERMINED = "CAUSE_UNDETERMINED"


class BaselineQuality(str, Enum):
    """Quality status of a calculated personal baseline."""
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Fewer than required minimum samples
    LOW_CONFIDENCE = "LOW_CONFIDENCE"        # Small sample size or high volatility
    ESTABLISHED = "ESTABLISHED"              # Sufficient consistent historical samples
    STALE = "STALE"                          # Observations too old to reflect current environment
    DEGRADED = "DEGRADED"                    # Samples captured during degraded operating periods


@dataclass
class EvidenceWindow:
    """In-memory bounded observations capturing context before, during, and after an event."""
    before_observations: List[Observation] = field(default_factory=list)
    incident_observations: List[Observation] = field(default_factory=list)
    after_observations: List[Observation] = field(default_factory=list)


@dataclass
class RootCauseAssessment:
    """Deterministic root-cause conclusion grounded strictly in evidence."""
    primary_cause: RootCauseCategory
    explanation: str
    confidence_score: float  # 0.0 to 1.0 derived from evidence factors
    evidence_quality: EvidenceQuality
    relationship: str  # "OBSERVED", "PROBABLE", "UNDETERMINED"
    supporting_evidence: List[str] = field(default_factory=list)
    affected_layers: List[str] = field(default_factory=list)


@dataclass
class DetailedIncident:
    """Full incident record with lifecycle tracking, evidence window, and root-cause intelligence."""
    incident_id: str
    incident_type: IncidentType
    severity: IncidentSeverity
    status: IncidentStatus
    started_at_utc: str
    ended_at_utc: Optional[str] = None
    duration_seconds: float = 0.0
    summary: str = ""
    root_cause: Optional[RootCauseAssessment] = None
    affected_layers: List[str] = field(default_factory=list)
    correlation_id: str = ""
    evidence_window: EvidenceWindow = field(default_factory=EvidenceWindow)
    trigger_metric: str = ""
    trigger_value: Optional[float] = None
    recovery_value: Optional[float] = None
    baseline_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BaselineMetricSummary:
    """Statistical summary for a single metric within the Personal PC Baseline."""
    metric_name: str
    sample_count: int
    mean: float
    median: float
    p95: float
    min_value: float
    max_value: float
    std_dev: float
    quality: BaselineQuality
    updated_at_utc: str = field(default_factory=now_utc_iso)


@dataclass
class ChangeEvent:
    """Record of a genuine configuration or environment change."""
    change_id: str
    category: str  # "WIFI", "ADAPTER", "GATEWAY", "HARDWARE", "SYSTEM"
    attribute_name: str
    old_value: Any
    new_value: Any
    detected_at_utc: str = field(default_factory=now_utc_iso)
    significance: str = "NORMAL"  # "NORMAL", "SUSPICIOUS", "CRITICAL"


@dataclass
class RegressionAssessment:
    """Performance regression compared against established personal baseline."""
    metric_name: str
    baseline_mean: float
    observed_mean: float
    percentage_degradation: float
    is_significant: bool
    confidence: float
    sample_count: int
    explanation: str


@dataclass
class BottleneckCandidate:
    """Correlated candidate hardware/network bottleneck."""
    component: str  # "CPU", "RAM", "GPU", "VRAM", "DISK", "NETWORK"
    classification: str  # "OBSERVED", "INFERRED", "UNDETERMINED"
    confidence: float
    rationale: str
    metrics_snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationCandidate:
    """
    Contract for a potential optimization opportunity.
    Strictly unexecuted in Stage 2.
    """
    candidate_id: str
    category: str  # "NETWORK", "GPU", "SYSTEM", "BACKGROUND_TASKS"
    description: str
    evidence: List[str]
    expected_effect: str
    risk_level: str  # "SAFE", "RECOMMENDED", "ADVANCED"
    required_privilege: str  # "USER", "ELEVATED"
    is_reversible: bool
    requires_snapshot: bool
    verification_plan: str
    rollback_plan: str
    confidence: float
    user_approved: bool = False


@dataclass
class AIEvidencePackage:
    """
    Deterministic evidence container for future 'Ask Veyra' and 'Explain My PC' integration.
    Guarantees that AI answers are grounded strictly in verified evidence.
    """
    package_id: str
    timestamp_utc: str
    summary: str
    root_cause: Optional[RootCauseAssessment]
    active_incidents: List[DetailedIncident]
    recent_changes: List[ChangeEvent]
    bottlenecks: List[BottleneckCandidate]
    regressions: List[RegressionAssessment]
    evidence_quality: EvidenceQuality
    raw_evidence_summary: Dict[str, Any]
