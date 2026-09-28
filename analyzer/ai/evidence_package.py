"""
VEYRA Evidence-Grounded AI Package Builder.
Compiles verified deterministic facts into structured evidence packages for future AI interfaces.
Enforces the rule: AI must never invent root causes, override deterministic thresholds,
or make ungrounded claims.
"""
import uuid
from typing import Dict, List, Optional

from app.core.contracts import Observation
from app.core.time import now_utc_iso
from analyzer.contracts import (
    AIEvidencePackage,
    DetailedIncident,
    RootCauseAssessment,
    ChangeEvent,
    BottleneckCandidate,
    RegressionAssessment,
    EvidenceQuality
)


class AIEvidenceBuilder:
    """
    Constructs deterministic, evidence-grounded packages for future AI consumption.
    """
    def build_package(
        self,
        active_incidents: List[DetailedIncident],
        root_cause: Optional[RootCauseAssessment],
        changes: List[ChangeEvent],
        bottlenecks: List[BottleneckCandidate],
        regressions: List[RegressionAssessment],
        current_observations: Dict[str, Observation]
    ) -> AIEvidencePackage:
        # Determine overall evidence quality
        quality = EvidenceQuality.STRONG if (active_incidents or current_observations) else EvidenceQuality.INSUFFICIENT

        # Construct concise deterministic summary
        if active_incidents:
            primary_inc = active_incidents[0]
            summary = f"Active event: {primary_inc.incident_type.value} ({primary_inc.severity.value}). "
            if root_cause:
                summary += f"Root cause: {root_cause.primary_cause.value} ({root_cause.relationship})."
        else:
            summary = "System and network operating within established baseline parameters."

        raw_summary = {
            obs_key: {m_name: m.value for m_name, m in obs.measurements.items()}
            for obs_key, obs in current_observations.items()
        }

        return AIEvidencePackage(
            package_id=f"aipkg_{int(uuid.uuid4().int % 10000000)}",
            timestamp_utc=now_utc_iso(),
            summary=summary,
            root_cause=root_cause,
            active_incidents=active_incidents,
            recent_changes=changes,
            bottlenecks=bottlenecks,
            regressions=regressions,
            evidence_quality=quality,
            raw_evidence_summary=raw_summary
        )
