"""
VEYRA Persistent Incident Replay Engine.
Reconstructs complete chronological incident timelines (Before -> During -> After)
directly from SQLite historical storage across application restarts.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from storage.sqlite_engine import SqliteStorageEngine
from storage.history.incident_store import HistoricalIncidentStore

logger = logging.getLogger("veyra.storage.replay_store")


class IncidentReplayStore:
    """Reconstructs historical Before / During / After incident replay packages."""

    def __init__(self, incident_store: HistoricalIncidentStore):
        self.incident_store = incident_store
        self.engine = incident_store.engine

    def reconstruct_replay(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Reconstructs the full chronological replay of an incident from persistent storage.
        Answers:
          1. What was normal?
          2. What changed?
          3. What failed?
          4. What recovered?
          5. What remained degraded?
        """
        incident = self.incident_store.get_detailed_incident(incident_id)
        if not incident:
            return None

        before_obs = incident.evidence_window.before_observations
        during_obs = incident.evidence_window.incident_observations
        after_obs = incident.evidence_window.after_observations

        # 1. What was normal? (Baseline from Before window)
        normal_metrics: Dict[str, Any] = {}
        if before_obs:
            for obs in before_obs:
                for name, m in obs.measurements.items():
                    if m.is_valid and isinstance(m.value, (int, float)):
                        if name not in normal_metrics:
                            normal_metrics[name] = []
                        normal_metrics[name].append(m.value)

        normal_summary = {
            name: {
                "mean": round(sum(vals) / len(vals), 2),
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
            }
            for name, vals in normal_metrics.items()
            if vals
        }

        # 2. What changed? (Immediate trigger metric or state shift)
        what_changed = {
            "trigger_metric": incident.trigger_metric,
            "trigger_value": incident.trigger_value,
            "correlation_id": incident.correlation_id,
            "started_at_utc": incident.started_at_utc,
        }

        # 3. What failed?
        what_failed = {
            "incident_type": incident.incident_type.value,
            "primary_cause": incident.root_cause.primary_cause.value if incident.root_cause else "UNKNOWN",
            "cause_explanation": incident.root_cause.explanation if incident.root_cause else "",
            "confidence_score": incident.root_cause.confidence_score if incident.root_cause else 0.5,
            "affected_layers": incident.affected_layers,
            "severity": incident.severity.value,
            "duration_seconds": incident.duration_seconds,
        }

        # 4. What recovered?
        what_recovered = {
            "status": incident.status.value,
            "ended_at_utc": incident.ended_at_utc,
            "recovery_value": incident.recovery_value,
        }

        # 5. What remained degraded?
        remained_degraded: List[str] = []
        if after_obs:
            latest_obs = after_obs[-1]
            for name, m in latest_obs.measurements.items():
                if not m.is_valid:
                    remained_degraded.append(f"{name} is currently {m.state.value}")
                elif name in normal_summary and isinstance(m.value, (int, float)):
                    norm_max = normal_summary[name]["max"]
                    if norm_max > 0 and m.value > norm_max * 1.5:
                        remained_degraded.append(f"{name} ({m.value}) remains 50% above normal ({norm_max})")

        return {
            "incident_id": incident.incident_id,
            "summary": incident.summary,
            "timeline": {
                "before_samples_count": len(before_obs),
                "during_samples_count": len(during_obs),
                "after_samples_count": len(after_obs),
            },
            "answers": {
                "what_was_normal": normal_summary,
                "what_changed": what_changed,
                "what_failed": what_failed,
                "what_recovered": what_recovered,
                "what_remained_degraded": remained_degraded,
            }
        }
