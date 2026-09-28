"""
VEYRA Collector Interfaces & Health Contracts.
Establishes the contract that all metric collectors must implement.
Collectors collect real measurements; they never fabricate telemetry and never present UI.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional

from app.core.contracts import Observation


class CollectorHealthStatus(str, Enum):
    """Possible operational health states for VEYRA collectors."""
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"
    DISABLED = "DISABLED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TIMEOUT = "TIMEOUT"


@dataclass
class CollectorHealth:
    collector_name: str
    status: CollectorHealthStatus
    is_operational: bool
    last_collection_time_utc: str
    consecutive_failures: int
    last_execution_duration_ms: float = 0.0
    error_message: str = ""


class BaseCollector(ABC):
    """Abstract base class for all VEYRA collectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this collector."""
        pass

    @abstractmethod
    def collect(self) -> Observation:
        """
        Executes a real measurement cycle.
        Returns an Observation containing valid measurements or explicit error states.
        MUST NEVER fabricate fallback or synthetic values.
        """
        pass

    @abstractmethod
    def check_health(self) -> CollectorHealth:
        """Returns the current operational health of the collector."""
        pass
