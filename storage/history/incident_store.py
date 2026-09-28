"""
VEYRA Historical Incident Store.
Provides atomic persistence and query interfaces for Stage 2 DetailedIncident
objects, contextual evidence windows, and incident frequency analytics.
"""
from datetime import datetime, timezone, timedelta
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from analyzer.contracts import (
    DetailedIncident,
    EvidenceQuality,
    EvidenceWindow,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    RootCauseAssessment,
    RootCauseCategory,
)
from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from app.core.time import now_utc_iso
from storage.contracts import IncidentRecord, IncidentEvidenceRecord, TimelineEventRecord
from storage.sqlite_engine import SqliteStorageEngine

logger = logging.getLogger("veyra.storage.incident_store")


class HistoricalIncidentStore:
    """Manages persistent storage, deduplication, and analytics for incidents."""

    def __init__(self, engine: SqliteStorageEngine):
        self.engine = engine

    def save_detailed_incident(self, incident: DetailedIncident) -> None:
        """
        Atomically persists a DetailedIncident, its evidence window observations,
        and creates a corresponding PC Timeline event.
        """
        record = IncidentRecord(
            incident_id=incident.incident_id,
            incident_type=incident.incident_type.value if hasattr(incident.incident_type, "value") else str(incident.incident_type),
            severity=incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity),
            status=incident.status.value if hasattr(incident.status, "value") else str(incident.status),
            started_at_utc=incident.started_at_utc,
            ended_at_utc=incident.ended_at_utc,
            duration_seconds=incident.duration_seconds,
            summary=incident.summary,
            primary_cause=incident.root_cause.primary_cause.value if incident.root_cause else "UNKNOWN",
            cause_explanation=incident.root_cause.explanation if incident.root_cause else "",
            confidence_score=incident.root_cause.confidence_score if incident.root_cause else 0.5,
            evidence_quality=incident.root_cause.evidence_quality.value if incident.root_cause else "MODERATE",
            relationship=incident.root_cause.relationship if incident.root_cause else "UNDETERMINED",
            affected_layers=incident.affected_layers,
            correlation_id=incident.correlation_id,
            trigger_metric=incident.trigger_metric,
            trigger_value=incident.trigger_value,
            recovery_value=incident.recovery_value,
            baseline_context_json=json.dumps(incident.baseline_context or {}),
        )

        evidence_records: List[IncidentEvidenceRecord] = []

        # Convert before observations
        for obs in incident.evidence_window.before_observations:
            evidence_records.append(self._observation_to_evidence(obs, incident.incident_id, "BEFORE"))

        # Convert incident observations
        for obs in incident.evidence_window.incident_observations:
            evidence_records.append(self._observation_to_evidence(obs, incident.incident_id, "DURING"))

        # Convert after observations
        for obs in incident.evidence_window.after_observations:
            evidence_records.append(self._observation_to_evidence(obs, incident.incident_id, "AFTER"))

        # Persist incident + evidence atomically
        self.engine.save_incident_record(record, evidence_records)

        # Record timeline event
        timeline_event = TimelineEventRecord(
            event_id=f"EVT-{uuid.uuid4().hex[:12]}",
            timestamp_utc=incident.started_at_utc,
            event_type=f"INCIDENT_{incident.status.value}",
            severity=incident.severity.value,
            source="incident_detector",
            reference_id=incident.incident_id,
            summary=incident.summary,
            details_json=json.dumps({
                "incident_type": record.incident_type,
                "correlation_id": record.correlation_id,
                "primary_cause": record.primary_cause,
                "duration_seconds": record.duration_seconds
            })
        )
        self.engine.save_timeline_event(timeline_event)

    def get_detailed_incident(self, incident_id: str) -> Optional[DetailedIncident]:
        """Reconstructs a DetailedIncident along with its full EvidenceWindow."""
        rec = self.engine.get_incident_record(incident_id)
        if not rec:
            return None

        # Fetch evidence records
        raw_evidence = self.engine.get_incident_evidence(incident_id)
        before_obs: List[Observation] = []
        during_obs: List[Observation] = []
        after_obs: List[Observation] = []

        for e in raw_evidence:
            obs = self._evidence_to_observation(e)
            if e.window_type == "BEFORE":
                before_obs.append(obs)
            elif e.window_type == "DURING":
                during_obs.append(obs)
            elif e.window_type == "AFTER":
                after_obs.append(obs)

        evidence_window = EvidenceWindow(
            before_observations=before_obs,
            incident_observations=during_obs,
            after_observations=after_obs
        )

        root_cause = RootCauseAssessment(
            primary_cause=RootCauseCategory(rec.primary_cause) if rec.primary_cause in RootCauseCategory._value2member_map_ else RootCauseCategory.CAUSE_UNDETERMINED,
            explanation=rec.cause_explanation,
            confidence_score=rec.confidence_score,
            evidence_quality=EvidenceQuality(rec.evidence_quality) if rec.evidence_quality in EvidenceQuality._value2member_map_ else EvidenceQuality.MODERATE,
            relationship=rec.relationship,
            affected_layers=rec.affected_layers,
            supporting_evidence=[]
        )

        return DetailedIncident(
            incident_id=rec.incident_id,
            incident_type=IncidentType(rec.incident_type) if rec.incident_type in IncidentType._value2member_map_ else IncidentType.PACKET_LOSS_SPIKE,
            severity=IncidentSeverity(rec.severity) if rec.severity in IncidentSeverity._value2member_map_ else IncidentSeverity.WARNING,
            status=IncidentStatus(rec.status) if rec.status in IncidentStatus._value2member_map_ else IncidentStatus.ACTIVE,
            started_at_utc=rec.started_at_utc,
            ended_at_utc=rec.ended_at_utc,
            duration_seconds=rec.duration_seconds,
            summary=rec.summary,
            root_cause=root_cause,
            affected_layers=rec.affected_layers,
            correlation_id=rec.correlation_id,
            evidence_window=evidence_window,
            trigger_metric=rec.trigger_metric,
            trigger_value=rec.trigger_value,
            recovery_value=rec.recovery_value,
            baseline_context=json.loads(rec.baseline_context_json or "{}")
        )

    def query_incidents(
        self,
        incident_type: Optional[IncidentType] = None,
        severity: Optional[IncidentSeverity] = None,
        status: Optional[IncidentStatus] = None,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        limit: int = 100
    ) -> List[IncidentRecord]:
        """Queries incidents matching filters."""
        return self.engine.query_incident_records(
            incident_type=incident_type.value if incident_type else None,
            severity=severity.value if severity else None,
            status=status.value if status else None,
            start_utc=start_utc,
            end_utc=end_utc,
            limit=limit
        )

    def get_incident_frequency(
        self,
        incident_type: IncidentType,
        window_days: int = 30
    ) -> Dict[str, Any]:
        """
        Answers historical frequency questions:
        - "How often has this happened?"
        - "When was previous occurrence?"
        - "Average duration?"
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        records = self.engine.query_incident_records(
            incident_type=incident_type.value,
            start_utc=cutoff,
            limit=500
        )

        total_count = len(records)
        if total_count == 0:
            return {
                "incident_type": incident_type.value,
                "window_days": window_days,
                "total_occurrences": 0,
                "last_occurrence_utc": None,
                "average_duration_seconds": 0.0,
                "trend": "STABLE"
            }

        durations = [r.duration_seconds for r in records if r.duration_seconds > 0]
        avg_dur = round(sum(durations) / len(durations), 1) if durations else 0.0
        last_utc = records[0].started_at_utc

        # Simple frequency trend: count in first half vs second half of window
        half_cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days / 2.0)).isoformat()
        recent_half = sum(1 for r in records if r.started_at_utc >= half_cutoff)
        older_half = total_count - recent_half

        if recent_half > older_half * 1.5 and recent_half >= 3:
            trend = "INCREASING"
        elif recent_half < older_half * 0.5 and older_half >= 3:
            trend = "DECREASING"
        else:
            trend = "STABLE"

        return {
            "incident_type": incident_type.value,
            "window_days": window_days,
            "total_occurrences": total_count,
            "last_occurrence_utc": last_utc,
            "average_duration_seconds": avg_dur,
            "trend": trend
        }

    @staticmethod
    def _observation_to_evidence(obs: Observation, incident_id: str, window_type: str) -> IncidentEvidenceRecord:
        """Extracts bounded telemetry measurements for safe persistent evidence storage."""
        metrics_dict: Dict[str, Any] = {}
        for name, m in obs.measurements.items():
            metrics_dict[name] = {
                "state": m.state.value,
                "value": m.value,
                "unit": m.unit.value,
                "confidence": m.confidence,
                "provenance": m.provenance
            }

        return IncidentEvidenceRecord(
            evidence_id=f"EVD-{uuid.uuid4().hex[:12]}",
            incident_id=incident_id,
            window_type=window_type,
            timestamp_utc=obs.timestamp_utc,
            metrics_json=json.dumps(metrics_dict)
        )

    @staticmethod
    def _evidence_to_observation(evd: IncidentEvidenceRecord) -> Observation:
        """Reconstructs an Observation from persistent evidence record."""
        raw = json.loads(evd.metrics_json or "{}")
        measurements: Dict[str, Measurement] = {}

        for name, data in raw.items():
            state = MetricState(data["state"])
            unit = MetricUnit(data["unit"]) if data.get("unit") in MetricUnit._value2member_map_ else MetricUnit.STRING
            measurements[name] = Measurement(
                metric_name=name,
                state=state,
                value=data.get("value"),
                unit=unit,
                source_collector="evidence_replay",
                provenance=data.get("provenance", "history"),
                timestamp_utc=evd.timestamp_utc,
                confidence=data.get("confidence", 1.0)
            )

        return Observation(
            observation_id=evd.evidence_id,
            timestamp_utc=evd.timestamp_utc,
            collector_name="historical_store",
            measurements=measurements,
            collector_healthy=True,
            status_summary="RECONSTRUCTED_FROM_EVIDENCE"
        )
