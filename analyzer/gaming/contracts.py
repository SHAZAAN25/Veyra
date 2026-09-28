"""
VEYRA Gaming Intelligence & Session DNA Contracts.
Defines strongly-typed models for reliable game identification, gaming session states,
Gaming Session DNA, and session-to-session comparisons.
Strictly prohibits fabricated FPS or unverified game detection.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from app.core.time import now_utc_iso


class GameDetectionSource(str, Enum):
    """Authoritative source of game identity."""
    PROCESS_MATCH = "PROCESS_MATCH"
    USER_PROFILE = "USER_PROFILE"
    UNKNOWN = "UNKNOWN"


class GamingSessionState(str, Enum):
    """Lifecycle states of a gaming session."""
    DETECTED = "DETECTED"
    ACTIVE = "ACTIVE"
    ENDING = "ENDING"
    COMPLETED = "COMPLETED"
    INTERRUPTED = "INTERRUPTED"


class SessionPerformanceCharacteristic(str, Enum):
    """Dominant workload characteristic of the session."""
    BALANCED = "BALANCED"
    CPU_BOUND = "CPU_BOUND"
    GPU_BOUND = "GPU_BOUND"
    NETWORK_VOLATILE = "NETWORK_VOLATILE"
    MEMORY_CONSTRAINED = "MEMORY_CONSTRAINED"
    STABLE = "STABLE"


class NetworkStabilityRating(str, Enum):
    """Network stability classification during gaming session."""
    EXCELLENT = "EXCELLENT"  # 0% loss, jitter < 3ms
    GOOD = "GOOD"            # 0% loss, jitter < 10ms
    VOLATILE = "VOLATILE"    # Occasional packet loss or high jitter
    DEGRADED = "DEGRADED"    # Sustained packet loss > 2% or high latency spikes


class SystemPressureRating(str, Enum):
    """System resource pressure classification during gaming session."""
    NOMINAL = "NOMINAL"      # CPU < 75%, RAM < 80%
    ELEVATED = "ELEVATED"    # CPU 75-90%, RAM 80-90%
    SATURATED = "SATURATED"  # CPU > 90% or RAM > 92%


@dataclass
class GameIdentity:
    """Reliably identified game executable metadata."""
    name: str
    executable: Optional[str] = None
    process_id: Optional[int] = None
    detection_source: GameDetectionSource = GameDetectionSource.UNKNOWN
    is_validated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "executable": self.executable,
            "process_id": self.process_id,
            "detection_source": self.detection_source.value,
            "is_validated": self.is_validated,
        }


@dataclass
class GamingSessionDNA:
    """
    Session-level analytical profile.
    Deterministic representation of what the gaming session was actually like.
    """
    stability_score: float  # 0.0 to 100.0 deterministic score
    performance_characteristic: SessionPerformanceCharacteristic
    network_stability: NetworkStabilityRating
    system_pressure: SystemPressureRating
    bottlenecks_detected: List[str] = field(default_factory=list)
    incident_types: List[str] = field(default_factory=list)
    sample_count: int = 0
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stability_score": self.stability_score,
            "performance_characteristic": self.performance_characteristic.value,
            "network_stability": self.network_stability.value,
            "system_pressure": self.system_pressure.value,
            "bottlenecks_detected": self.bottlenecks_detected,
            "incident_types": self.incident_types,
            "sample_count": self.sample_count,
            "summary": self.summary,
        }


@dataclass
class GamingSession:
    """Complete gaming session record."""
    session_id: str
    game: GameIdentity
    state: GamingSessionState
    started_at_utc: str
    ended_at_utc: Optional[str] = None
    duration_seconds: float = 0.0
    fps_telemetry: Optional[float] = None  # None if unavailable; never fabricated
    avg_cpu_pct: Optional[float] = None
    avg_gpu_pct: Optional[float] = None
    avg_ram_pct: Optional[float] = None
    avg_vram_pct: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    incident_count: int = 0
    bottleneck_candidates: List[str] = field(default_factory=list)
    session_dna: Optional[GamingSessionDNA] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "game": self.game.to_dict(),
            "state": self.state.value,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": self.ended_at_utc,
            "duration_seconds": self.duration_seconds,
            "fps_telemetry": self.fps_telemetry,
            "avg_cpu_pct": self.avg_cpu_pct,
            "avg_gpu_pct": self.avg_gpu_pct,
            "avg_ram_pct": self.avg_ram_pct,
            "avg_vram_pct": self.avg_vram_pct,
            "avg_latency_ms": self.avg_latency_ms,
            "packet_loss_pct": self.packet_loss_pct,
            "incident_count": self.incident_count,
            "bottleneck_candidates": self.bottleneck_candidates,
            "session_dna": self.session_dna.to_dict() if self.session_dna else None,
        }


@dataclass
class GamingComparisonResult:
    """Compatible comparison between two gaming sessions or against a gaming baseline."""
    session_a_id: str
    session_b_id: str
    metric_comparisons: Dict[str, Dict[str, Any]]
    stability_change: float
    summary: str
    compatible: bool = True
    incompatibility_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_a_id": self.session_a_id,
            "session_b_id": self.session_b_id,
            "metric_comparisons": self.metric_comparisons,
            "stability_change": self.stability_change,
            "summary": self.summary,
            "compatible": self.compatible,
            "incompatibility_reason": self.incompatibility_reason,
        }
