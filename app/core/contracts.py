"""
VEYRA Core Data Contracts & Integrity Foundation.
Defines the strictly typed lifecycle:
MEASUREMENT -> OBSERVATION -> ASSESSMENT -> INCIDENT -> HISTORICAL RECORD -> UI

Enforces the non-negotiable rule: NEVER FABRICATE A MEASUREMENT.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time

from app.core.exceptions import DataContractViolationError
from app.core.time import now_utc_iso, monotonic_time


class MetricState(str, Enum):
    """Explicit lifecycle states for all VEYRA telemetry metrics."""
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    STALE = "STALE"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    COLLECTOR_UNAVAILABLE = "COLLECTOR_UNAVAILABLE"
    MEASUREMENT_FAILED = "MEASUREMENT_FAILED"


class MetricUnit(str, Enum):
    MILLISECONDS = "ms"
    PERCENTAGE = "%"
    MEGABITS_PER_SECOND = "Mbps"
    BYTES = "bytes"
    MEGABYTES = "MB"
    GIGABYTES = "GB"
    CELSIUS = "C"
    DBM = "dBm"
    COUNT = "count"
    HERTZ = "Hz"
    STRING = "string"
    BOOLEAN = "bool"


@dataclass
class Measurement:
    """
    Atomic raw reading produced by a collector.
    Enforces absolute provenance, explicit error states, and prohibits fake data.
    """
    metric_name: str
    state: MetricState
    value: Optional[float | int | str | bool]
    unit: MetricUnit
    source_collector: str
    provenance: str  # e.g., "ping:1.1.1.1", "wlan:netsh", "sys:psutil"
    timestamp_utc: str = field(default_factory=now_utc_iso)
    monotonic_timestamp: float = field(default_factory=monotonic_time)
    error_message: Optional[str] = None
    confidence: float = 1.0

    def __post_init__(self):
        # Strict validation of non-fabrication rule
        if self.state == MetricState.AVAILABLE and self.value is None:
            raise DataContractViolationError(
                f"Metric '{self.metric_name}' marked AVAILABLE but contains None value."
            )
        if self.state != MetricState.AVAILABLE and self.value is not None:
            raise DataContractViolationError(
                f"Metric '{self.metric_name}' has non-AVAILABLE state '{self.state.value}' "
                f"but contains value '{self.value}'. Fabricating fallback measurements is strictly forbidden."
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise DataContractViolationError("Confidence must be a float between 0.0 and 1.0.")

    @property
    def is_valid(self) -> bool:
        return self.state == MetricState.AVAILABLE and self.value is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "state": self.state.value,
            "value": self.value,
            "unit": self.unit.value,
            "source_collector": self.source_collector,
            "provenance": self.provenance,
            "timestamp_utc": self.timestamp_utc,
            "monotonic_timestamp": self.monotonic_timestamp,
            "error_message": self.error_message,
            "confidence": self.confidence,
        }


@dataclass
class Observation:
    """
    Aggregated and verified set of measurements for a single sampling interval.
    Produced by the collector coordinator after validation.
    """
    observation_id: str
    timestamp_utc: str
    collector_name: str
    measurements: Dict[str, Measurement]
    collector_healthy: bool
    status_summary: str = "OK"

    def get_metric(self, name: str) -> Optional[Measurement]:
        return self.measurements.get(name)


@dataclass
class Assessment:
    """
    Evaluation produced by an analyzer operating on verified observations.
    Evaluates health, stability, score, and operational thresholds.
    """
    assessment_id: str
    timestamp_utc: str
    target_domain: str  # e.g., "network", "system", "gaming"
    overall_health: str  # "HEALTHY", "WARNING", "CRITICAL", "UNKNOWN"
    score: Optional[float]  # 0 to 100
    observations_evaluated: int
    findings: List[str] = field(default_factory=list)


@dataclass
class Incident:
    """
    Structured record of an active or resolved anomaly.
    Generated when assessments cross threshold boundaries.
    """
    incident_id: str
    domain: str
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    summary: str
    start_time_utc: str
    end_time_utc: Optional[str] = None
    root_cause_analysis: Optional[str] = None
    snapshots: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class HistoricalSummary:
    """
    Compact historical record aggregated over a fixed time bucket.
    Stored permanently in SQLite; raw measurements are purged after aggregation.
    """
    bucket_start_utc: str
    bucket_end_utc: str
    metric_name: str
    count: int
    min_value: Optional[float]
    max_value: Optional[float]
    avg_value: Optional[float]
    p95_value: Optional[float]
    unavailable_count: int = 0
