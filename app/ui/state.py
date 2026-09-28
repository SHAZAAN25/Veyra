"""
VEYRA UI State Manager.
Manages live telemetry state, freshness calculation, active incident caches,
and deterministic overall health states without executing collection logic in the UI.
"""
from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional

from analyzer.contracts import DetailedIncident, ChangeEvent
from app.core.contracts import Observation, Assessment, MetricState
from app.core.time import now_utc_iso


class UiStateManager:
    """Central reactive state repository feeding all UI views."""

    def __init__(self):
        self.latest_observation: Optional[Observation] = None
        self.latest_assessment: Optional[Assessment] = None
        self.active_incidents: List[DetailedIncident] = []
        self.recent_changes: List[ChangeEvent] = []
        
        self.overall_health: str = "UNKNOWN"
        self.freshness_state: str = "UNAVAILABLE"
        self.last_update_monotonic: float = 0.0
        self.last_update_utc: str = ""

        self._listeners: List[Callable[[], None]] = []

    @property
    def current_telemetry(self) -> Optional[Observation]:
        return self.latest_observation

    @property
    def current_incidents(self) -> List[DetailedIncident]:
        return self.active_incidents

    def add_listener(self, listener: Callable[[], None]) -> None:

        """Registers a callback when telemetry state updates."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                pass

    def update_telemetry(
        self,
        observation: Optional[Observation],
        assessment: Optional[Assessment] = None,
        active_incidents: Optional[List[DetailedIncident]] = None,
        recent_changes: Optional[List[ChangeEvent]] = None
    ) -> None:
        """Updates internal telemetry state and computes deterministic freshness and health."""
        now = time.monotonic()
        self.latest_observation = observation
        if assessment:
            self.latest_assessment = assessment
        if active_incidents is not None:
            self.active_incidents = active_incidents
        if recent_changes is not None:
            self.recent_changes = recent_changes

        if observation:
            self.last_update_monotonic = now
            self.last_update_utc = observation.timestamp_utc

        # 1. Deterministic Freshness Calculation
        self.freshness_state = self.calculate_freshness(now)

        # 2. Deterministic Overall Health State
        self.overall_health = self.calculate_overall_health()

        self._notify()

    def calculate_freshness(self, current_monotonic: Optional[float] = None) -> str:
        """Computes freshness state based on monotonic elapsed time."""
        if not self.latest_observation or self.last_update_monotonic == 0.0:
            return "UNAVAILABLE"
        now = current_monotonic or time.monotonic()
        age = now - self.last_update_monotonic
        if age <= 3.0:
            return "LIVE"
        elif age <= 10.0:
            return "RECENT"
        elif age <= 30.0:
            return "STALE"
        return "UNAVAILABLE"

    def calculate_overall_health(self) -> str:
        """
        Derives overall health strictly from backend evidence.
        Precedence: CRITICAL -> HIGH -> WARNING -> DEGRADED -> HEALTHY -> UNKNOWN.
        """
        if not self.latest_observation:
            return "UNKNOWN"

        if not self.latest_observation.collector_healthy:
            return "DEGRADED"

        # Check active incidents
        if self.active_incidents:
            highest_sev = None
            order = {"CRITICAL": 4, "HIGH": 3, "WARNING": 2}
            for inc in self.active_incidents:
                sev = inc.severity.value if hasattr(inc.severity, "value") else str(inc.severity)
                if sev in order:
                    if highest_sev is None or order[sev] > order[highest_sev]:
                        highest_sev = sev
            if highest_sev:
                return highest_sev

        # Check assessment overall health
        if self.latest_assessment:
            ass_health = self.latest_assessment.overall_health
            if ass_health in ("CRITICAL", "HIGH", "WARNING", "DEGRADED", "HEALTHY"):
                return ass_health

        # Check key metrics for direct degradation
        for m in self.latest_observation.measurements.values():
            if m.state == MetricState.MEASUREMENT_FAILED:
                return "DEGRADED"

        return "HEALTHY"

    def get_metric_value(self, metric_name: str) -> Optional[Any]:
        """Safely retrieves a metric value from the latest observation."""
        if not self.latest_observation:
            return None
        m = self.latest_observation.measurements.get(metric_name)
        if m and m.is_valid:
            return m.value
        return None

    def get_metric_state(self, metric_name: str) -> str:
        """Returns the state string for a metric."""
        if not self.latest_observation:
            return "UNAVAILABLE"
        m = self.latest_observation.measurements.get(metric_name)
        if m:
            return m.state.value
        return "UNAVAILABLE"
