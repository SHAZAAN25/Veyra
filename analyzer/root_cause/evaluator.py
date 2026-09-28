"""
VEYRA Deterministic Root-Cause Evaluator.
Analyzes verified observations and topology states to deduce the root cause domain.
Strictly distinguishes OBSERVED vs PROBABLE vs UNDETERMINED relationships.
Supports 'Cause undetermined' as a primary valid result whenever evidence is inconclusive.
"""
from typing import Dict, List, Optional

from app.core.contracts import Observation, MetricState
from analyzer.contracts import (
    RootCauseAssessment,
    RootCauseCategory,
    EvidenceQuality,
    DetailedIncident,
    IncidentType
)
from analyzer.root_cause.topology import NetworkTopologyTracker, TopologyNodeState


class RootCauseEvaluator:
    """
    Evaluates incidents across the layered topology to determine root cause with deterministic confidence.
    """
    def __init__(self, topology_tracker: NetworkTopologyTracker):
        self.topology = topology_tracker

    def evaluate_incident_root_cause(
        self,
        incident: DetailedIncident,
        observations: Dict[str, Observation]
    ) -> RootCauseAssessment:
        inc_type = incident.incident_type
        topo_states = self.topology.get_topology_summary()

        # 1. Local Wi-Fi Disconnect / Adapter Failure (OBSERVED directly on Layer 1)
        if inc_type == IncidentType.WIFI_DISCONNECT:
            return RootCauseAssessment(
                primary_cause=RootCauseCategory.WIFI_LINK,
                explanation="Local Wi-Fi interface disconnected from access point.",
                confidence_score=0.98,
                evidence_quality=EvidenceQuality.STRONG,
                relationship="OBSERVED",
                supporting_evidence=["WLAN AutoConfig reported disconnected state directly"],
                affected_layers=["LAYER_1_ADAPTER"]
            )

        if inc_type == IncidentType.NETWORK_ADAPTER_CHANGE:
            return RootCauseAssessment(
                primary_cause=RootCauseCategory.LOCAL_DEVICE_ADAPTER,
                explanation="Local physical/virtual network adapter transitioned state or link speed.",
                confidence_score=0.95,
                evidence_quality=EvidenceQuality.STRONG,
                relationship="OBSERVED",
                supporting_evidence=["Local adapter configuration or operational status changed"],
                affected_layers=["LAYER_1_ADAPTER"]
            )

        # 2. Gateway Failure (OBSERVED on Layer 2)
        if inc_type == IncidentType.GATEWAY_UNREACHABLE or topo_states.get("gateway") == "FAILED":
            return RootCauseAssessment(
                primary_cause=RootCauseCategory.GATEWAY_LOCAL_NETWORK,
                explanation="Default gateway is unresponsive to ICMP probes. Local LAN or access point failure. Upstream internet cannot be reliably assessed through failed gateway.",
                confidence_score=0.95,
                evidence_quality=EvidenceQuality.STRONG,
                relationship="OBSERVED",
                supporting_evidence=["ICMP echo to default gateway timed out"],
                affected_layers=["LAYER_2_GATEWAY"]
            )

        # 3. DNS Failure (OBSERVED on Layer 3 when Gateway is healthy)
        if inc_type == IncidentType.DNS_FAILURE or (topo_states.get("dns") == "FAILED" and topo_states.get("gateway") == "HEALTHY"):
            return RootCauseAssessment(
                primary_cause=RootCauseCategory.DNS_SUBSYSTEM,
                explanation="DNS name resolution failed while default gateway and physical link remain healthy.",
                confidence_score=0.90,
                evidence_quality=EvidenceQuality.STRONG,
                relationship="OBSERVED",
                supporting_evidence=["getaddrinfo failed with socket.gaierror while gateway is reachable"],
                affected_layers=["LAYER_3_DNS"]
            )

        # 4. Upstream Internet Failure (PROBABLE on Layer 4 when Gateway & DNS are healthy)
        if inc_type == IncidentType.INTERNET_UNREACHABLE:
            if topo_states.get("gateway") == "HEALTHY":
                return RootCauseAssessment(
                    primary_cause=RootCauseCategory.UPSTREAM_INTERNET,
                    explanation="Default gateway is responsive but all upstream ICMP probes to 1.1.1.1 failed. Upstream ISP or routing outage.",
                    confidence_score=0.88,
                    evidence_quality=EvidenceQuality.STRONG,
                    relationship="PROBABLE",
                    supporting_evidence=["Gateway reachable (Layer 2 OK) but 100% packet loss to upstream targets (Layer 4 Fail)"],
                    affected_layers=["LAYER_4_INTERNET"]
                )

        # 5. Wi-Fi Degradation (PROBABLE correlation: low RSSI causing latency/loss)
        if inc_type in {IncidentType.LATENCY_SPIKE, IncidentType.PACKET_LOSS_SPIKE, IncidentType.JITTER_SPIKE}:
            wifi_obs = observations.get("wifi")
            if wifi_obs:
                sig_m = wifi_obs.get_metric("wifi_signal_pct")
                if sig_m and sig_m.state == MetricState.AVAILABLE and float(sig_m.value) < 45.0:
                    return RootCauseAssessment(
                        primary_cause=RootCauseCategory.WIFI_LINK,
                        explanation=f"Network degradation correlated with weak Wi-Fi signal ({sig_m.value}%). RF attenuation or interference.",
                        confidence_score=0.82,
                        evidence_quality=EvidenceQuality.MODERATE,
                        relationship="PROBABLE",
                        supporting_evidence=[f"Wi-Fi signal strength dropped to {sig_m.value}% during latency/loss event"],
                        affected_layers=["LAYER_1_ADAPTER", "LAYER_4_INTERNET"]
                    )

        # 6. System Resource Pressure
        if inc_type == IncidentType.SYSTEM_RESOURCE_PRESSURE:
            return RootCauseAssessment(
                primary_cause=RootCauseCategory.SYSTEM_RESOURCE_PRESSURE,
                explanation="Severe CPU or RAM utilization pressure on host machine.",
                confidence_score=0.90,
                evidence_quality=EvidenceQuality.STRONG,
                relationship="OBSERVED",
                supporting_evidence=["Host system performance counters exceeded 90% threshold"],
                affected_layers=["LAYER_0_HOST"]
            )

        # 7. GPU Resource Pressure
        if inc_type == IncidentType.GPU_RESOURCE_PRESSURE:
            return RootCauseAssessment(
                primary_cause=RootCauseCategory.GPU_COMPUTE_PRESSURE,
                explanation="Dedicated GPU utilization, VRAM allocation, or die temperature reached critical limits.",
                confidence_score=0.90,
                evidence_quality=EvidenceQuality.STRONG,
                relationship="OBSERVED",
                supporting_evidence=["GPU hardware sensor reported critical threshold crossing"],
                affected_layers=["LAYER_0_HOST"]
            )

        # 8. Observation Gap / System Sleep
        if inc_type == IncidentType.OBSERVATION_GAP_SLEEP_RESUME:
            return RootCauseAssessment(
                primary_cause=RootCauseCategory.OBSERVATION_GAP_SUSPENSION,
                explanation="System entered connected standby or sleep state. No network outage occurred.",
                confidence_score=0.99,
                evidence_quality=EvidenceQuality.STRONG,
                relationship="OBSERVED",
                supporting_evidence=["Monotonic vs wall clock discrepancy detected system suspension"],
                affected_layers=["LAYER_0_HOST"]
            )

        # 9. Inconclusive Evidence -> "Cause undetermined" (Valid and Successful Outcome)
        return RootCauseAssessment(
            primary_cause=RootCauseCategory.CAUSE_UNDETERMINED,
            explanation="Evidence is insufficient or multiple layers report transient fluctuations without conclusive causality.",
            confidence_score=0.25,
            evidence_quality=EvidenceQuality.INSUFFICIENT,
            relationship="UNDETERMINED",
            supporting_evidence=["Metric threshold crossed but no single layer fault dominates evidence"],
            affected_layers=list(incident.affected_layers)
        )
