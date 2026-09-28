"""
VEYRA Collector Common Infrastructure.
Provides shared helper classes, network layer definitions, and resilient execution wrappers.
"""
from enum import Enum
import time
import uuid
from typing import Dict, Optional, Callable

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from app.core.logging import get_logger
from app.core.time import now_utc_iso, monotonic_time
from collectors import BaseCollector, CollectorHealth, CollectorHealthStatus


class NetworkLayer(str, Enum):
    """Network architecture separation layers."""
    LAYER_1_ADAPTER = "LAYER_1_LOCAL_ADAPTER"
    LAYER_2_GATEWAY = "LAYER_2_GATEWAY"
    LAYER_3_DNS = "LAYER_3_DNS"
    LAYER_4_INTERNET = "LAYER_4_INTERNET_UPSTREAM"


class StatefulCollector(BaseCollector):
    """
    Base implementation providing failure counting, execution timing,
    and automatic status reporting.
    """
    def __init__(self, name: str):
        self._name = name
        self._status = CollectorHealthStatus.RUNNING
        self._last_collection_utc = "NEVER"
        self._consecutive_failures = 0
        self._last_duration_ms = 0.0
        self._last_error = ""
        self.logger = get_logger(f"collector.{name}")

    @property
    def name(self) -> str:
        return self._name

    def check_health(self) -> CollectorHealth:
        is_operational = self._status in {CollectorHealthStatus.RUNNING, CollectorHealthStatus.DEGRADED}
        return CollectorHealth(
            collector_name=self._name,
            status=self._status,
            is_operational=is_operational,
            last_collection_time_utc=self._last_collection_utc,
            consecutive_failures=self._consecutive_failures,
            last_execution_duration_ms=self._last_duration_ms,
            error_message=self._last_error
        )

    def _mark_success(self, duration_ms: float):
        self._status = CollectorHealthStatus.RUNNING
        self._consecutive_failures = 0
        self._last_error = ""
        self._last_duration_ms = duration_ms
        self._last_collection_utc = now_utc_iso()

    def _mark_degraded(self, error: str, duration_ms: float):
        self._status = CollectorHealthStatus.DEGRADED
        self._consecutive_failures += 1
        self._last_error = error
        self._last_duration_ms = duration_ms
        self._last_collection_utc = now_utc_iso()

    def _mark_failed(self, error: str, duration_ms: float):
        self._status = CollectorHealthStatus.FAILED
        self._consecutive_failures += 1
        self._last_error = error
        self._last_duration_ms = duration_ms
        self._last_collection_utc = now_utc_iso()

    def _mark_unsupported(self, reason: str):
        self._status = CollectorHealthStatus.UNSUPPORTED
        self._last_error = reason
        self._last_collection_utc = now_utc_iso()

    def _mark_permission_denied(self, reason: str):
        self._status = CollectorHealthStatus.PERMISSION_DENIED
        self._consecutive_failures += 1
        self._last_error = reason
        self._last_collection_utc = now_utc_iso()

    def _mark_timeout(self, reason: str, duration_ms: float):
        self._status = CollectorHealthStatus.TIMEOUT
        self._consecutive_failures += 1
        self._last_error = reason
        self._last_duration_ms = duration_ms
        self._last_collection_utc = now_utc_iso()

    def create_observation(
        self,
        measurements: Dict[str, Measurement],
        healthy: bool = True,
        status_summary: str = "OK"
    ) -> Observation:
        return Observation(
            observation_id=f"obs_{self.name}_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}",
            timestamp_utc=now_utc_iso(),
            collector_name=self.name,
            measurements=measurements,
            collector_healthy=healthy,
            status_summary=status_summary
        )
