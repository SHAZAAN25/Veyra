"""
VEYRA Incident Lifecycle State Machine.
Enforces DETECTED -> ACTIVE -> RECOVERED transitions with hysteresis and cooldown.
Eliminates alert flapping by requiring independent trigger and recovery thresholds.
"""
import time
import uuid
from typing import Dict, Optional, List

from app.core.time import now_utc_iso, monotonic_time
from analyzer.contracts import DetailedIncident, IncidentStatus, IncidentSeverity, IncidentType
from analyzer.thresholds import MetricHysteresisThreshold


class IncidentTracker:
    """
    Tracks state transitions and hysteresis for an individual incident type.
    """
    def __init__(
        self,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        threshold: Optional[MetricHysteresisThreshold] = None,
        cooldown_seconds: float = 10.0
    ):
        self.incident_type = incident_type
        self.severity = severity
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds

        self.active_incident: Optional[DetailedIncident] = None
        self._consecutive_triggers = 0
        self._consecutive_recoveries = 0
        self._last_recovery_time = 0.0

    def evaluate_metric(
        self,
        current_val: Optional[float],
        metric_name: str,
        affected_layers: List[str],
        summary: str = ""
    ) -> Optional[DetailedIncident]:
        """
        Evaluates current metric value against hysteresis thresholds.
        Returns the incident object if an active or updated event exists.
        """
        if self.threshold is None or current_val is None:
            return None

        now = monotonic_time()

        # Check if in cooldown
        if self.active_incident is None and (now - self._last_recovery_time) < self.cooldown_seconds:
            return None

        # 1. Trigger condition check
        # For signal strength, lower is worse (trigger when current_val <= trigger_value)
        is_lower_worse = (self.incident_type == IncidentType.WIFI_SIGNAL_DEGRADATION)

        if is_lower_worse:
            triggered = (current_val <= self.threshold.trigger_value)
            recovered = (current_val >= self.threshold.recovery_value)
        else:
            triggered = (current_val >= self.threshold.trigger_value)
            recovered = (current_val <= self.threshold.recovery_value)

        # 2. State Machine Logic
        if self.active_incident is None:
            # Currently healthy
            if triggered:
                self._consecutive_triggers += 1
                if self._consecutive_triggers >= self.threshold.min_consecutive_triggers:
                    # Transition to DETECTED / ACTIVE
                    self.active_incident = DetailedIncident(
                        incident_id=f"inc_{self.incident_type.value.lower()}_{uuid.uuid4().hex[:8]}",
                        incident_type=self.incident_type,
                        severity=self.severity,
                        status=IncidentStatus.ACTIVE,
                        started_at_utc=now_utc_iso(),
                        summary=summary or f"{self.incident_type.value}: {current_val}{self.threshold.unit}",
                        affected_layers=affected_layers,
                        trigger_metric=metric_name,
                        trigger_value=current_val
                    )
                    self._consecutive_triggers = 0
                    self._consecutive_recoveries = 0
                    return self.active_incident
            else:
                self._consecutive_triggers = 0
            return None

        else:
            # Currently active incident
            if recovered:
                self._consecutive_recoveries += 1
                if self._consecutive_recoveries >= self.threshold.min_consecutive_recoveries:
                    # Transition to RECOVERED
                    recovered_inc = self.active_incident
                    recovered_inc.status = IncidentStatus.RECOVERED
                    recovered_inc.ended_at_utc = now_utc_iso()
                    recovered_inc.recovery_value = current_val

                    self._last_recovery_time = now
                    self.active_incident = None
                    self._consecutive_recoveries = 0
                    self._consecutive_triggers = 0
                    return recovered_inc
            else:
                self._consecutive_recoveries = 0

            return self.active_incident
