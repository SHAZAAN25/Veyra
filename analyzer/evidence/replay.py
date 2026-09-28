"""
VEYRA Incident Replay Foundation.
Reconstructs the chronological timeline of an event across:
BEFORE -> DURING -> AFTER
Answers deterministically:
- What was normal?
- What changed?
- What failed?
- What recovered?
- What remained degraded?
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from app.core.contracts import MetricState
from analyzer.contracts import DetailedIncident, EvidenceWindow


@dataclass
class ReplayTimelinePhase:
    phase_name: str  # "BEFORE", "DURING", "AFTER"
    observation_count: int
    metric_averages: Dict[str, float]
    state_changes: List[str]


@dataclass
class IncidentReplaySummary:
    incident_id: str
    incident_type: str
    severity: str
    what_was_normal: Dict[str, Any]
    what_changed: str
    what_failed: List[str]
    what_recovered: List[str]
    what_remained_degraded: List[str]
    timeline_phases: List[ReplayTimelinePhase] = field(default_factory=list)


class IncidentReplayEngine:
    """
    Analyzes an incident's EvidenceWindow to produce an explainable replay timeline.
    """
    def generate_replay(self, incident: DetailedIncident) -> IncidentReplaySummary:
        window = incident.evidence_window

        # 1. Analyze "Before" phase (Normal baseline)
        normal_metrics: Dict[str, Any] = {}
        if window.before_observations:
            for obs in window.before_observations:
                for k, m in obs.measurements.items():
                    if m.state == MetricState.AVAILABLE and isinstance(m.value, (int, float)):
                        normal_metrics.setdefault(k, []).append(float(m.value))
        what_was_normal = {k: round(sum(v) / len(v), 2) for k, v in normal_metrics.items()}

        # 2. Analyze "What Changed?"
        what_changed = (
            f"Metric '{incident.trigger_metric}' triggered incident with value {incident.trigger_value} "
            f"exceeding normal baseline."
            if incident.trigger_metric else "Anomaly condition detected across observations."
        )

        # 3. Analyze "What Failed?"
        what_failed = list(incident.affected_layers)
        if not what_failed:
            what_failed = [incident.incident_type.value]

        # 4. Analyze "What Recovered?"
        what_recovered: List[str] = []
        what_remained_degraded: List[str] = []

        if incident.status.value == "RECOVERED":
            what_recovered.append(f"Trigger metric '{incident.trigger_metric}' recovered to {incident.recovery_value}")
        else:
            what_remained_degraded.append(f"Active event: '{incident.incident_type.value}' still active")

        # 5. Timeline phases
        timeline = [
            ReplayTimelinePhase(
                phase_name="BEFORE",
                observation_count=len(window.before_observations),
                metric_averages=what_was_normal,
                state_changes=[]
            ),
            ReplayTimelinePhase(
                phase_name="DURING",
                observation_count=len(window.incident_observations),
                metric_averages={incident.trigger_metric: float(incident.trigger_value)} if incident.trigger_value else {},
                state_changes=[what_changed]
            ),
            ReplayTimelinePhase(
                phase_name="AFTER",
                observation_count=len(window.after_observations),
                metric_averages={},
                state_changes=what_recovered
            )
        ]

        return IncidentReplaySummary(
            incident_id=incident.incident_id,
            incident_type=incident.incident_type.value,
            severity=incident.severity.value,
            what_was_normal=what_was_normal,
            what_changed=what_changed,
            what_failed=what_failed,
            what_recovered=what_recovered,
            what_remained_degraded=what_remained_degraded,
            timeline_phases=timeline
        )
