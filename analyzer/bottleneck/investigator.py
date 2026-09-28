"""
VEYRA Hardware Bottleneck Investigator.
Correlates genuine system, GPU, memory, disk, network, and genuine thermal telemetry
to identify candidate hardware bottlenecks.
Strictly distinguishes OBSERVED vs INFERRED vs UNDETERMINED relationships.
Never claims causality without supporting evidence.
Never fabricates or infers thermal data.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from analyzer.contracts import BottleneckCandidate
from app.core.contracts import MetricState, Observation


class BottleneckConclusion(str, Enum):
    NO_CLEAR_BOTTLENECK = "NO CLEAR BOTTLENECK"
    CPU_BOTTLENECK_CANDIDATE = "CPU BOTTLENECK CANDIDATE"
    GPU_BOTTLENECK_CANDIDATE = "GPU BOTTLENECK CANDIDATE"
    MEMORY_PRESSURE = "MEMORY PRESSURE"
    STORAGE_PRESSURE = "STORAGE PRESSURE"
    NETWORK_BOTTLENECK_CANDIDATE = "NETWORK BOTTLENECK CANDIDATE"
    THERMAL_LIMITATION_CANDIDATE = "THERMAL LIMITATION CANDIDATE"
    MULTIPLE_CONSTRAINTS = "MULTIPLE CONSTRAINTS"
    INSUFFICIENT_DATA = "INSUFFICIENT DATA"


@dataclass
class HardwareBottleneckReport:
    """Comprehensive hardware constraint evaluation."""
    primary_conclusion: BottleneckConclusion
    candidates: List[BottleneckCandidate]
    confidence: float
    summary: str
    thermal_state: str  # "AVAILABLE", "UNAVAILABLE"
    thermal_details: Optional[Dict[str, Any]] = None
    background_workload_candidates: List[Dict[str, Any]] = field(default_factory=list)
    observed_conditions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_conclusion": self.primary_conclusion.value,
            "candidates": [
                {
                    "component": c.component,
                    "classification": c.classification,
                    "confidence": c.confidence,
                    "rationale": c.rationale,
                    "metrics_snapshot": c.metrics_snapshot,
                }
                for c in self.candidates
            ],
            "confidence": self.confidence,
            "summary": self.summary,
            "thermal_state": self.thermal_state,
            "thermal_details": self.thermal_details,
            "background_workload_candidates": self.background_workload_candidates,
            "observed_conditions": self.observed_conditions,
        }


class BottleneckInvestigator:
    """
    Correlates multi-subsystem telemetry to identify candidate hardware bottlenecks.
    Preserves backwards compatibility with investigate() -> List[BottleneckCandidate].
    """

    def investigate(self, observations: Dict[str, Observation]) -> List[BottleneckCandidate]:
        """Core candidate identification (Stage 2 compatibility)."""
        report = self.investigate_report(observations)
        return report.candidates

    def investigate_report(self, observations: Dict[str, Observation]) -> HardwareBottleneckReport:
        """Stage 5 Full Bottleneck Investigation with thermal and workload analysis."""
        candidates: List[BottleneckCandidate] = []
        observed_conditions: Dict[str, Any] = {}

        if not observations:
            return HardwareBottleneckReport(
                primary_conclusion=BottleneckConclusion.INSUFFICIENT_DATA,
                candidates=[],
                confidence=0.0,
                summary="No telemetry observations available for bottleneck investigation.",
                thermal_state="UNAVAILABLE",
                thermal_details={"message": "Temperature data unavailable."},
            )

        def get_val(obs_key: str, metric_key: str) -> Optional[float]:
            obs = observations.get(obs_key)
            if obs:
                m = obs.get_metric(metric_key)
                if m and m.state == MetricState.AVAILABLE and isinstance(m.value, (int, float)):
                    return float(m.value)
            return None

        cpu_util = get_val("cpu", "cpu_utilization_pct")
        ram_util = get_val("memory", "ram_utilization_pct")
        disk_util = get_val("disk", "disk_utilization_pct")
        gpu_util = get_val("gpu", "gpu_utilization_pct")
        gpu_mem_util = get_val("gpu", "gpu_memory_utilization_pct")
        packet_loss = get_val("internet", "internet_packet_loss_pct")
        latency = get_val("internet", "internet_latency_ms")

        # Thermal telemetry check (strictly genuine sensor values only)
        gpu_temp = get_val("gpu", "gpu_temperature_c")
        cpu_temp = get_val("cpu", "cpu_temperature_c")

        if cpu_util is not None:
            observed_conditions["cpu_utilization_pct"] = cpu_util
        if ram_util is not None:
            observed_conditions["ram_utilization_pct"] = ram_util
        if disk_util is not None:
            observed_conditions["disk_utilization_pct"] = disk_util
        if gpu_util is not None:
            observed_conditions["gpu_utilization_pct"] = gpu_util
        if gpu_mem_util is not None:
            observed_conditions["gpu_memory_utilization_pct"] = gpu_mem_util
        if packet_loss is not None:
            observed_conditions["internet_packet_loss_pct"] = packet_loss
        if latency is not None:
            observed_conditions["internet_latency_ms"] = latency

        # 1. RAM Pressure (OBSERVED: Physical Memory Exhaustion)
        if ram_util is not None and ram_util >= 92.0:
            candidates.append(BottleneckCandidate(
                component="RAM",
                classification="OBSERVED",
                confidence=0.88,
                rationale=f"System RAM utilization is at critical threshold ({ram_util}%).",
                metrics_snapshot={"ram_utilization_pct": ram_util}
            ))

        # 2. CPU Bottleneck Candidate
        if cpu_util is not None and cpu_util >= 90.0:
            if gpu_util is not None and gpu_util <= 45.0:
                candidates.append(BottleneckCandidate(
                    component="CPU",
                    classification="INFERRED",
                    confidence=0.75,
                    rationale=f"High CPU utilization ({cpu_util}%) with low GPU utilization ({gpu_util}%) suggests CPU execution bottleneck.",
                    metrics_snapshot={"cpu_utilization_pct": cpu_util, "gpu_utilization_pct": gpu_util}
                ))
            elif gpu_util is None:
                candidates.append(BottleneckCandidate(
                    component="CPU",
                    classification="OBSERVED",
                    confidence=0.80,
                    rationale=f"Sustained heavy processor load ({cpu_util}%).",
                    metrics_snapshot={"cpu_utilization_pct": cpu_util}
                ))

        # 3. GPU / VRAM Bottleneck Candidate
        if gpu_util is not None and gpu_util >= 96.0:
            candidates.append(BottleneckCandidate(
                component="GPU",
                classification="OBSERVED",
                confidence=0.85,
                rationale=f"GPU computing core is fully saturated ({gpu_util}%).",
                metrics_snapshot={"gpu_utilization_pct": gpu_util}
            ))
        if gpu_mem_util is not None and gpu_mem_util >= 90.0:
            candidates.append(BottleneckCandidate(
                component="VRAM",
                classification="OBSERVED",
                confidence=0.85,
                rationale=f"Dedicated GPU VRAM is near capacity ({gpu_mem_util}%).",
                metrics_snapshot={"gpu_memory_utilization_pct": gpu_mem_util}
            ))

        # 4. Disk / Storage Pressure
        if disk_util is not None and disk_util >= 95.0:
            candidates.append(BottleneckCandidate(
                component="DISK",
                classification="OBSERVED",
                confidence=0.80,
                rationale=f"Storage drive space or continuous I/O near maximum ({disk_util}%).",
                metrics_snapshot={"disk_utilization_pct": disk_util}
            ))

        # 5. Network Bottleneck Candidate
        if packet_loss is not None and packet_loss >= 10.0:
            candidates.append(BottleneckCandidate(
                component="NETWORK",
                classification="OBSERVED",
                confidence=0.90,
                rationale=f"Severe network packet loss detected ({packet_loss}%).",
                metrics_snapshot={"internet_packet_loss_pct": packet_loss}
            ))

        # 6. Thermal Limitation Candidate (ONLY IF GENUINE SENSOR DATA EXISTS)
        thermal_state = "UNAVAILABLE"
        thermal_details = {"message": "Temperature data unavailable."}

        if gpu_temp is not None or cpu_temp is not None:
            thermal_state = "AVAILABLE"
            thermal_details = {
                "gpu_temperature_c": gpu_temp,
                "cpu_temperature_c": cpu_temp,
            }
            if gpu_temp is not None and gpu_temp >= 87.0:
                candidates.append(BottleneckCandidate(
                    component="GPU_THERMAL",
                    classification="OBSERVED",
                    confidence=0.85,
                    rationale=f"GPU thermal sensor reached thermal limit ({gpu_temp}°C). Potential thermal throttling.",
                    metrics_snapshot={"gpu_temperature_c": gpu_temp}
                ))
            if cpu_temp is not None and cpu_temp >= 95.0:
                candidates.append(BottleneckCandidate(
                    component="CPU_THERMAL",
                    classification="OBSERVED",
                    confidence=0.85,
                    rationale=f"CPU thermal sensor reached critical junction temperature ({cpu_temp}°C). Potential thermal throttling.",
                    metrics_snapshot={"cpu_temperature_c": cpu_temp}
                ))

        # 7. Background Workload Candidates
        bg_workloads: List[Dict[str, Any]] = []
        cpu_obs = observations.get("cpu")
        if cpu_obs and hasattr(cpu_obs, "details") and isinstance(cpu_obs.details, dict):
            top_procs = cpu_obs.details.get("top_processes")
            if isinstance(top_procs, list):
                for proc in top_procs[:3]:
                    if isinstance(proc, dict) and proc.get("cpu_percent", 0) > 15.0:
                        bg_workloads.append({
                            "name": proc.get("name", "Unknown"),
                            "pid": proc.get("pid"),
                            "cpu_pct": proc.get("cpu_percent"),
                        })

        # Synthesize Primary Conclusion
        if not candidates:
            # Check if we have minimum valid observations
            if cpu_util is None and ram_util is None:
                conclusion = BottleneckConclusion.INSUFFICIENT_DATA
                summary = "Insufficient metric samples to evaluate hardware constraints."
                confidence = 0.0
            else:
                conclusion = BottleneckConclusion.NO_CLEAR_BOTTLENECK
                summary = "No hardware or network bottlenecks currently observed. All subsystems operating within normal bounds."
                confidence = 0.90
        elif len(candidates) > 1:
            conclusion = BottleneckConclusion.MULTIPLE_CONSTRAINTS
            comps = ", ".join(c.component for c in candidates)
            summary = f"Multiple simultaneous hardware constraints observed: {comps}."
            confidence = round(sum(c.confidence for c in candidates) / len(candidates), 2)
        else:
            primary = candidates[0]
            confidence = primary.confidence
            if primary.component == "CPU":
                conclusion = BottleneckConclusion.CPU_BOTTLENECK_CANDIDATE
            elif primary.component in ("GPU", "VRAM"):
                conclusion = BottleneckConclusion.GPU_BOTTLENECK_CANDIDATE
            elif primary.component == "RAM":
                conclusion = BottleneckConclusion.MEMORY_PRESSURE
            elif primary.component == "DISK":
                conclusion = BottleneckConclusion.STORAGE_PRESSURE
            elif primary.component == "NETWORK":
                conclusion = BottleneckConclusion.NETWORK_BOTTLENECK_CANDIDATE
            elif "THERMAL" in primary.component:
                conclusion = BottleneckConclusion.THERMAL_LIMITATION_CANDIDATE
            else:
                conclusion = BottleneckConclusion.NO_CLEAR_BOTTLENECK

            summary = f"Identified {conclusion.value}: {primary.rationale}"

        return HardwareBottleneckReport(
            primary_conclusion=conclusion,
            candidates=candidates,
            confidence=confidence,
            summary=summary,
            thermal_state=thermal_state,
            thermal_details=thermal_details,
            background_workload_candidates=bg_workloads,
            observed_conditions=observed_conditions,
        )
