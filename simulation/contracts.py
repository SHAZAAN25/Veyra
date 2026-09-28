"""
VEYRA Simulation & Chaos Contracts
Stage 7 Automated Testing, Fault Injection & QA Harnesses

Defines data models and contracts for chaos experiments, fault injection scenarios,
and resilience verification results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class SimulationTarget(str, Enum):
    """Subsystems subject to chaos and fault injection."""
    GPU_COLLECTOR = "GPU_COLLECTOR"
    NETWORK_COLLECTOR = "NETWORK_COLLECTOR"
    STORAGE_ENGINE = "STORAGE_ENGINE"
    PROCESS_COORDINATOR = "PROCESS_COORDINATOR"
    OPTIMIZATION_EXECUTOR = "OPTIMIZATION_EXECUTOR"
    API_SERVER = "API_SERVER"
    SYSTEM_CLOCK = "SYSTEM_CLOCK"
    DIAGNOSTICS_RUNNER = "DIAGNOSTICS_RUNNER"


class FaultType(str, Enum):
    """Categorization of simulated hardware, OS, and network faults."""
    SUBPROCESS_CRASH = "SUBPROCESS_CRASH"
    SUBPROCESS_TIMEOUT = "SUBPROCESS_TIMEOUT"
    DISK_IO_ERROR = "DISK_IO_ERROR"
    DATABASE_CORRUPTED = "DATABASE_CORRUPTED"
    BUFFERBLOAT_SPIKE = "BUFFERBLOAT_SPIKE"
    PACKET_LOSS_BURST = "PACKET_LOSS_BURST"
    DNS_BLACKHOLE = "DNS_BLACKHOLE"
    TIME_GAP_SLEEP = "TIME_GAP_SLEEP"
    CLOCK_SKEW = "CLOCK_SKEW"
    CONCURRENCY_RACE = "CONCURRENCY_RACE"
    CORRUPTED_PAYLOAD = "CORRUPTED_PAYLOAD"
    RATE_LIMIT_FLOOD = "RATE_LIMIT_FLOOD"


class ChaosStatus(str, Enum):
    """Lifecycle state of a chaos experiment."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    INJECTING = "INJECTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    ABORTED = "ABORTED"
    ERROR = "ERROR"


@dataclass
class SimulatedMeasurement:
    """
    Explicitly typed simulated metric reading.
    Guarantees Rule 9 compliance by permanently embedding is_simulation=True.
    """
    metric_name: str
    value: Any
    unit: str
    is_simulation: bool = True
    provenance: str = "synthetic:chaos"
    timestamp_utc: float = field(default_factory=time.time)


@dataclass
class SimulatedObservation:
    """
    Explicitly typed simulated observation bundle.
    Guarantees Rule 9 compliance by permanently embedding is_simulation=True.
    """
    observation_id: str
    collector_name: str
    measurements: Dict[str, SimulatedMeasurement] = field(default_factory=dict)
    is_simulation: bool = True
    timestamp_utc: float = field(default_factory=time.time)


def is_simulation_payload(payload: Any) -> bool:
    """Rule 9 runtime verification: Detects if data originated from simulation."""
    if getattr(payload, "is_simulation", False) is True:
        return True
    if hasattr(payload, "provenance") and ("synthetic" in str(payload.provenance) or "chaos" in str(payload.provenance)):
        return True
    return False


@dataclass
class FaultScenario:
    """Specification of an individual fault injection."""
    target: SimulationTarget
    fault_type: FaultType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0


@dataclass
class ChaosReport:
    """Execution outcome of a chaos experiment."""
    experiment_id: str
    target: SimulationTarget
    fault_type: FaultType
    status: ChaosStatus
    system_degraded_gracefully: bool
    recovered_cleanly: bool
    duration_ms: float
    assertions_evaluated: int
    assertions_passed: int
    telemetry_isolated: bool
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status in (ChaosStatus.PASSED, ChaosStatus.COMPLETED) and self.system_degraded_gracefully and self.telemetry_isolated


@dataclass
class ChaosExperiment:
    """Orchestrated chaos test experiment definition."""
    experiment_id: str
    name: str
    description: str
    scenario: FaultScenario
    created_at_utc: float = field(default_factory=time.time)
    status: ChaosStatus = ChaosStatus.PENDING
