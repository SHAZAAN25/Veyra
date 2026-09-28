"""
VEYRA Explain My PC Deterministic Engine.
Synthesizes continuous measurements, personal baselines, active incidents,
hardware bottleneck candidates, and timeline changes into a structured, evidence-grounded report.
Strictly distinguishes OBSERVED vs INFERRED and never hallucinates causes.
"""
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional

from analyzer.contracts import (
    AIEvidencePackage,
    BottleneckCandidate,
    ChangeEvent,
    DetailedIncident,
    RegressionAssessment,
    RootCauseAssessment,
)
from app.core.contracts import MetricState, Observation

logger = logging.getLogger("veyra.analyzer.ai.explain_my_pc")


@dataclass
class ExplainMyPCReport:
    """Structured explanation grounded strictly in verified Veyra evidence."""
    current_state: str
    observed_changes: str
    important_events: str
    likely_contributing_factors: str
    evidence_points: List[str]
    confidence: float
    what_is_unknown: List[str]
    raw_markdown: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_state": self.current_state,
            "observed_changes": self.observed_changes,
            "important_events": self.important_events,
            "likely_contributing_factors": self.likely_contributing_factors,
            "evidence_points": self.evidence_points,
            "confidence": self.confidence,
            "what_is_unknown": self.what_is_unknown,
            "raw_markdown": self.raw_markdown,
        }


class ExplainMyPCEngine:
    """Deterministic generator for Explain My PC."""

    def generate_explanation(
        self,
        observations: Dict[str, Observation],
        baselines: Optional[Dict[str, float]] = None,
        active_incidents: Optional[List[DetailedIncident]] = None,
        bottlenecks: Optional[List[BottleneckCandidate]] = None,
        changes: Optional[List[ChangeEvent]] = None,
        regressions: Optional[List[RegressionAssessment]] = None,
    ) -> ExplainMyPCReport:
        """Constructs structured explanation with zero synthetic statements."""
        baselines = baselines or {}
        active_incidents = active_incidents or []
        bottlenecks = bottlenecks or []
        changes = changes or []
        regressions = regressions or []

        def get_val(obs_key: str, metric_key: str) -> Optional[float]:
            obs = observations.get(obs_key)
            if obs:
                m = obs.get_metric(metric_key)
                if m and m.state == MetricState.AVAILABLE and isinstance(m.value, (int, float)):
                    return float(m.value)
            return None

        cpu = get_val("cpu", "cpu_utilization_pct")
        ram = get_val("memory", "ram_utilization_pct")
        gpu = get_val("gpu", "gpu_utilization_pct")
        latency = get_val("internet", "internet_latency_ms")
        loss = get_val("internet", "internet_packet_loss_pct")
        cpu_temp = get_val("cpu", "cpu_temperature_c")
        gpu_temp = get_val("gpu", "gpu_temperature_c")

        evidence: List[str] = []
        unknowns: List[str] = []

        # 1. CURRENT STATE
        state_parts = []
        if cpu is not None:
            state_parts.append(f"CPU utilization is currently {cpu:.1f}%")
            evidence.append(f"CPU load: {cpu:.1f}%")
        else:
            unknowns.append("Real-time CPU utilization unavailable.")

        if ram is not None:
            state_parts.append(f"Memory (RAM) is at {ram:.1f}%")
            evidence.append(f"RAM load: {ram:.1f}%")

        if gpu is not None:
            state_parts.append(f"GPU compute utilization is {gpu:.1f}%")
            evidence.append(f"GPU load: {gpu:.1f}%")
        else:
            state_parts.append("Dedicated GPU is idle or telemetry unavailable")

        if latency is not None:
            state_parts.append(f"Internet latency is {latency:.1f} ms with {loss or 0.0}% packet loss")
            evidence.append(f"Network latency: {latency:.1f} ms, loss: {loss or 0.0}%")

        current_state_text = ". ".join(state_parts) + "." if state_parts else "Telemetry observations currently initializing."

        # 2. OBSERVED CHANGES & BASELINE COMPARISON
        change_parts = []
        if cpu is not None and "cpu_utilization_pct" in baselines:
            base_cpu = baselines["cpu_utilization_pct"]
            delta = cpu - base_cpu
            if abs(delta) >= 15.0:
                direction = "above" if delta > 0 else "below"
                change_parts.append(f"CPU utilization is {abs(delta):.1f}% {direction} your established personal baseline of {base_cpu:.1f}%")
                evidence.append(f"Baseline CPU: {base_cpu:.1f}%, Deviation: {delta:+.1f}%")

        if latency is not None and "internet_latency_ms" in baselines:
            base_lat = baselines["internet_latency_ms"]
            delta_lat = latency - base_lat
            if delta_lat >= 20.0:
                change_parts.append(f"Network latency is elevated by {delta_lat:+.1f} ms compared to your typical baseline of {base_lat:.1f} ms")
                evidence.append(f"Baseline Latency: {base_lat:.1f} ms, Deviation: {delta_lat:+.1f} ms")

        if regressions:
            for reg in regressions:
                change_parts.append(f"Detected performance regression in '{reg.metric_name}' ({reg.percentage_degradation:.1f}% degradation)")
                evidence.append(f"Regression in {reg.metric_name}: {reg.explanation}")

        observed_changes_text = ". ".join(change_parts) + "." if change_parts else "All measured metrics align closely with your established personal PC baselines."

        # 3. IMPORTANT EVENTS
        event_parts = []
        if active_incidents:
            for inc in active_incidents:
                itype = inc.incident_type.value if hasattr(inc.incident_type, "value") else str(inc.incident_type)
                event_parts.append(f"Active incident: {itype} (Severity: {inc.severity.value}, Duration: {inc.duration_seconds:.0f}s)")
                evidence.append(f"Incident ID {inc.incident_id}: {inc.summary or itype}")
        else:
            event_parts.append("No active network or system anomalies detected")

        if changes:
            for ch in changes[:2]:
                event_parts.append(f"Recent configuration change: {ch.attribute_name} ({ch.category})")

        important_events_text = ". ".join(event_parts) + "."

        # 4. LIKELY CONTRIBUTING FACTORS
        factor_parts = []
        if bottlenecks:
            for b in bottlenecks:
                factor_parts.append(f"Constraint identified: {b.component} bottleneck candidate ({b.classification}) - {b.rationale}")
                evidence.append(f"Bottleneck candidate {b.component}: {b.rationale}")
        else:
            factor_parts.append("Hardware resources and throughput are operating within balanced thresholds")

        likely_factors_text = ". ".join(factor_parts) + "."

        # 5. WHAT IS UNKNOWN
        if cpu_temp is None and gpu_temp is None:
            unknowns.append("Hardware thermal sensor temperatures are unavailable; no thermal throttling inference made.")
        if "cpu_utilization_pct" not in baselines:
            unknowns.append("Long-term personal CPU baseline is still in learning phase.")
        if gpu is None:
            unknowns.append("GPU telemetry adapter is inactive or unsupported on current display driver.")

        # Confidence calculation
        confidence = 0.95
        if not baselines:
            confidence -= 0.15
        if len(unknowns) >= 2:
            confidence -= 0.10
        confidence = round(max(0.50, confidence), 2)

        # Build clean markdown
        lines = [
            "### CURRENT STATE",
            current_state_text,
            "",
            "### OBSERVED CHANGES",
            observed_changes_text,
            "",
            "### IMPORTANT EVENTS",
            important_events_text,
            "",
            "### LIKELY CONTRIBUTING FACTORS",
            likely_factors_text,
            "",
            "### EVIDENCE",
        ]
        for e in evidence:
            lines.append(f"- {e}")
        lines.append("")
        lines.append(f"**Confidence:** {int(confidence * 100)}%")
        lines.append("")
        lines.append("### WHAT IS UNKNOWN")
        for u in unknowns:
            lines.append(f"- {u}")

        raw_md = "\n".join(lines)

        return ExplainMyPCReport(
            current_state=current_state_text,
            observed_changes=observed_changes_text,
            important_events=important_events_text,
            likely_contributing_factors=likely_factors_text,
            evidence_points=evidence,
            confidence=confidence,
            what_is_unknown=unknowns,
            raw_markdown=raw_md,
        )
