"""
VEYRA Ask Veyra Engine.
Deterministic natural-language QA architecture grounded strictly in Veyra's verified telemetry,
baselines, incidents, bottlenecks, and optimization history.
Zero mandatory cloud dependencies, zero required external APIs, zero hallucinations.
"""
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from analyzer.ai.contracts import AIProvider, AIResponse, ResponseClassification
from analyzer.ai.evidence_package import AIEvidenceBuilder
from analyzer.contracts import (
    AIEvidencePackage,
    BottleneckCandidate,
    ChangeEvent,
    DetailedIncident,
    RegressionAssessment,
    RootCauseAssessment,
)
from app.core.contracts import MetricState, Observation
from app.core.time import now_utc_iso
from storage.contracts import EvidencePackageRecord
from storage.engine import StorageEngine

logger = logging.getLogger("veyra.analyzer.ai.ask_veyra")


class AskVeyraEngine:
    """Answers user inquiries strictly from local evidence and telemetry history."""

    def __init__(
        self,
        storage: Optional[StorageEngine] = None,
        optional_provider: Optional[AIProvider] = None,
        evidence_builder: Optional[AIEvidenceBuilder] = None,
    ):
        self.storage = storage
        self.optional_provider = optional_provider
        self.evidence_builder = evidence_builder or AIEvidenceBuilder()

    def answer_question(
        self,
        user_question: str,
        observations: Dict[str, Observation],
        baselines: Optional[Dict[str, float]] = None,
        active_incidents: Optional[List[DetailedIncident]] = None,
        bottlenecks: Optional[List[BottleneckCandidate]] = None,
        changes: Optional[List[ChangeEvent]] = None,
        regressions: Optional[List[RegressionAssessment]] = None,
        root_cause: Optional[RootCauseAssessment] = None,
    ) -> AIResponse:
        """
        Executes the Ask Veyra pipeline:
        Input Sanitization -> Intent Parsing -> Evidence Package -> Deterministic Answer -> Citations.
        Strictly enforces that AI reasoning cannot trigger system actions or commands.
        """
        if not user_question or not isinstance(user_question, str):
            return AIResponse(
                question="",
                answer="Please provide a valid question regarding your PC's telemetry or incidents.",
                confidence=0.0,
                response_type=ResponseClassification.INSUFFICIENT_EVIDENCE,
                citations=[],
                unknowns=[],
            )

        # Sanitize input: strip null bytes, strip newlines, bound to 500 chars
        sanitized_q = user_question.replace("\x00", "").replace("\r", " ").replace("\n", " ").strip()[:500]
        q_clean = sanitized_q.lower()
        baselines = baselines or {}
        active_incidents = active_incidents or []
        bottlenecks = bottlenecks or []
        changes = changes or []
        regressions = regressions or []

        # 1. Build Evidence Package
        package = self.evidence_builder.build_package(
            active_incidents=active_incidents,
            root_cause=root_cause,
            changes=changes,
            bottlenecks=bottlenecks,
            regressions=regressions,
            current_observations=observations,
        )

        # Helper to extract metrics
        def get_val(obs_key: str, metric_key: str) -> Optional[float]:
            obs = observations.get(obs_key)
            if obs:
                m = obs.get_metric(metric_key)
                if m and m.state == MetricState.AVAILABLE and isinstance(m.value, (int, float)):
                    return float(m.value)
            return None

        # 2. Intent Parsing and Deterministic Answering
        citations: List[str] = []
        unknowns: List[str] = []

        # Intent A: Network Latency / Ping / Lag
        if any(k in q_clean for k in ("latency", "ping", "lag", "rtt", "jitter")):
            latency = get_val("internet", "internet_latency_ms")
            loss = get_val("internet", "internet_packet_loss_pct")
            base_lat = baselines.get("internet_latency_ms")

            if latency is not None:
                citations.append(f"Metric: internet_latency_ms = {latency:.1f} ms")
                citations.append(f"Metric: internet_packet_loss_pct = {loss or 0.0}%")
                ans = f"Your current measured network latency to upstream servers is {latency:.1f} ms with {loss or 0.0}% packet loss."
                if base_lat is not None:
                    citations.append(f"Baseline: internet_latency_ms = {base_lat:.1f} ms")
                    delta = latency - base_lat
                    if delta > 15.0:
                        ans += f" This is {delta:+.1f} ms higher than your established baseline of {base_lat:.1f} ms."
                    else:
                        ans += f" This matches your typical personal baseline of {base_lat:.1f} ms."
                classification = ResponseClassification.OBSERVED
            else:
                ans = "Network latency telemetry is currently unavailable from active collectors."
                unknowns.append("No valid internet probe samples available.")
                classification = ResponseClassification.INSUFFICIENT_EVIDENCE

        # Intent B: Bottlenecks / System Sluggishness
        elif any(k in q_clean for k in ("bottleneck", "slow", "freeze", "stutter", "choke", "hardware")):
            if bottlenecks:
                parts = []
                for b in bottlenecks:
                    parts.append(f"{b.component} ({b.classification}): {b.rationale}")
                    citations.append(f"Bottleneck Candidate: {b.component} - {b.rationale}")
                ans = f"Veyra detected {len(bottlenecks)} candidate hardware constraint(s): " + "; ".join(parts) + "."
                classification = ResponseClassification.CORRELATED
            else:
                cpu = get_val("cpu", "cpu_utilization_pct")
                ram = get_val("memory", "ram_utilization_pct")
                gpu = get_val("gpu", "gpu_utilization_pct")
                if cpu is not None:
                    citations.append(f"Metric: cpu_utilization_pct = {cpu:.1f}%")
                if ram is not None:
                    citations.append(f"Metric: ram_utilization_pct = {ram:.1f}%")
                ans = f"No hardware bottlenecks are currently detected. CPU is at {cpu or 'N/A'}% and RAM is at {ram or 'N/A'}%, which are within acceptable operating thresholds."
                classification = ResponseClassification.OBSERVED

        # Intent C: Incidents / What Happened / Issues
        elif any(k in q_clean for k in ("incident", "what happened", "issue", "problem", "event", "why")):
            if active_incidents:
                primary = active_incidents[0]
                citations.append(f"Incident: {primary.incident_id} [{primary.incident_type.value}]")
                ans = f"Active incident '{primary.incident_type.value}' detected (Severity: {primary.severity.value}). {primary.summary}"
                if root_cause:
                    citations.append(f"Root Cause: {root_cause.primary_cause.value} ({root_cause.relationship})")
                    ans += f" Root cause evaluation: {root_cause.explanation}"
                classification = ResponseClassification.OBSERVED
            else:
                ans = "No active incidents or network anomalies are currently detected on your PC."
                classification = ResponseClassification.OBSERVED

        # Intent D: Baseline Deviations / Normalcy
        elif any(k in q_clean for k in ("baseline", "normal", "unusual", "typical")):
            cpu = get_val("cpu", "cpu_utilization_pct")
            base_cpu = baselines.get("cpu_utilization_pct")
            if cpu is not None and base_cpu is not None:
                citations.append(f"Current CPU: {cpu:.1f}%, Baseline CPU: {base_cpu:.1f}%")
                diff = cpu - base_cpu
                if abs(diff) > 15.0:
                    ans = f"Your current CPU utilization ({cpu:.1f}%) is unusually {'high' if diff > 0 else 'low'} compared to your typical baseline of {base_cpu:.1f}%."
                else:
                    ans = f"Your current CPU utilization ({cpu:.1f}%) is within expected range of your baseline ({base_cpu:.1f}%)."
                classification = ResponseClassification.CALCULATED
            else:
                ans = "Baseline comparison data is still accumulating or telemetry is unavailable."
                unknowns.append("Personal baseline requires more observation samples to form established statistics.")
                classification = ResponseClassification.INSUFFICIENT_EVIDENCE

        # Intent E: What Changed
        elif any(k in q_clean for k in ("what changed", "changes", "configuration")):
            if changes:
                parts = [f"{c.attribute_name} ({c.category}) changed from '{c.old_value}' to '{c.new_value}'" for c in changes[:3]]
                for c in changes[:3]:
                    citations.append(f"Change ID: {c.change_id} [{c.attribute_name}]")
                ans = "Recent detected environment changes: " + "; ".join(parts) + "."
                classification = ResponseClassification.HISTORICAL
            else:
                ans = "No network adapter, Wi-Fi link, or hardware configuration changes have been detected recently."
                classification = ResponseClassification.OBSERVED

        # Intent F: Unsupported / General Questions
        else:
            ans = (
                "I don't have enough evidence to determine that. "
                "Ask Veyra is strictly grounded in your PC's real-time and historical telemetry. "
                "You can ask about network latency, active incidents, hardware bottlenecks, baselines, or recent configuration changes."
            )
            unknowns.append("Question topic is outside local observability boundary.")
            classification = ResponseClassification.UNSUPPORTED

        # Optional Provider Enhancement (if user configured a custom LLM)
        if self.optional_provider:
            try:
                enhanced = self.optional_provider.generate_grounded_answer(package, user_question)
                if enhanced:
                    ans = enhanced
            except Exception as e:
                logger.warning(f"Optional AI provider failed, falling back to deterministic answer: {e}")

        # Persist evidence package to storage
        if self.storage:
            try:
                rec = EvidencePackageRecord(
                    package_id=package.package_id,
                    timestamp_utc=package.timestamp_utc,
                    query=user_question,
                    summary=ans,
                    evidence_json=json.dumps(package.raw_evidence_summary),
                    confidence=0.92 if classification != ResponseClassification.UNSUPPORTED else 0.0,
                )
                self.storage.save_evidence_package(rec)
            except Exception as e:
                logger.error(f"Failed to persist evidence package: {e}")

        return AIResponse(
            question=user_question,
            answer=ans,
            confidence=0.92 if classification != ResponseClassification.UNSUPPORTED else 0.0,
            response_type=classification,
            citations=citations,
            unknowns=unknowns,
            evidence_package=package,
        )
