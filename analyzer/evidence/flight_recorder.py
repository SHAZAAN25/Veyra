"""
VEYRA PC Health Flight Recorder Foundation.
Captures a structured, compact diagnostic snapshot around critical system and network events.
Strictly local-first and privacy-aware: zero passwords, tokens, or packet payloads are recorded.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List

from app.core.contracts import Observation, MetricState
from app.core.time import now_utc_iso
from analyzer.contracts import DetailedIncident, EvidenceQuality


@dataclass
class FlightRecorderSnapshot:
    snapshot_id: str
    timestamp_utc: str
    incident_id: Optional[str]
    incident_type: Optional[str]
    system_summary: Dict[str, Any]
    network_summary: Dict[str, Any]
    wifi_summary: Dict[str, Any]
    gateway_summary: Dict[str, Any]
    dns_summary: Dict[str, Any]
    internet_summary: Dict[str, Any]
    gpu_summary: Dict[str, Any]
    self_health_summary: Dict[str, Any]
    evidence_quality: EvidenceQuality = EvidenceQuality.STRONG


class FlightRecorder:
    """
    Flight recorder engine that extracts sanitized contextual snapshots from recent observations.
    """
    def create_snapshot(
        self,
        snapshot_id: str,
        observations: Dict[str, Observation],
        incident: Optional[DetailedIncident] = None
    ) -> FlightRecorderSnapshot:
        """Constructs a compact, privacy-safe flight recorder snapshot."""

        def extract_metrics(obs: Optional[Observation]) -> Dict[str, Any]:
            if not obs:
                return {"status": "UNAVAILABLE"}
            res = {}
            for name, m in obs.measurements.items():
                if m.state == MetricState.AVAILABLE:
                    res[name] = m.value
                else:
                    res[name] = m.state.value
            return res

        system_metrics = extract_metrics(observations.get("cpu"))
        system_metrics.update(extract_metrics(observations.get("memory")))
        system_metrics.update(extract_metrics(observations.get("disk")))

        return FlightRecorderSnapshot(
            snapshot_id=snapshot_id,
            timestamp_utc=now_utc_iso(),
            incident_id=incident.incident_id if incident else None,
            incident_type=incident.incident_type.value if incident else None,
            system_summary=system_metrics,
            network_summary=extract_metrics(observations.get("adapter")),
            wifi_summary=extract_metrics(observations.get("wifi")),
            gateway_summary=extract_metrics(observations.get("gateway")),
            dns_summary=extract_metrics(observations.get("dns")),
            internet_summary=extract_metrics(observations.get("internet")),
            gpu_summary=extract_metrics(observations.get("gpu")),
            self_health_summary=extract_metrics(observations.get("self")),
            evidence_quality=EvidenceQuality.STRONG if observations else EvidenceQuality.INSUFFICIENT
        )
