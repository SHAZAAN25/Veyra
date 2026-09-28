"""
VEYRA Optimization Opportunity Engine.
Analyzes continuous observations, incidents, bottlenecks, and active gaming state
to deterministically generate evidence-backed, reversible optimization opportunities.
Zero arbitrary or speculative recommendations.
"""
import logging
from typing import Any, Dict, List, Optional
import uuid

from analyzer.contracts import BottleneckCandidate, DetailedIncident
from app.core.contracts import MetricState, Observation
from app.core.time import now_utc_iso
from optimization.contracts import (
    OptimizationCategory,
    OptimizationOpportunity,
    OptimizationRiskLevel,
)

logger = logging.getLogger("veyra.optimization.opportunities")


class OptimizationOpportunityEngine:
    """Discovers evidence-backed optimization opportunities."""

    def evaluate_opportunities(
        self,
        observations: Dict[str, Observation],
        active_incidents: Optional[List[DetailedIncident]] = None,
        bottlenecks: Optional[List[BottleneckCandidate]] = None,
        is_gaming_active: bool = False,
    ) -> List[OptimizationOpportunity]:
        """Scans current conditions and yields concrete candidates with full evidence."""
        opportunities: List[OptimizationOpportunity] = []

        def get_val(obs_key: str, metric_key: str) -> Optional[float]:
            obs = observations.get(obs_key)
            if obs:
                m = obs.get_metric(metric_key)
                if m and m.state == MetricState.AVAILABLE and isinstance(m.value, (int, float)):
                    return float(m.value)
            return None

        # 1. DNS Cache Flush & Resolver Refresh
        dns_latency = get_val("internet", "dns_latency_ms")
        has_dns_incident = False
        if active_incidents:
            for inc in active_incidents:
                if "DNS" in str(inc.incident_type):
                    has_dns_incident = True
                    break

        if (dns_latency is not None and dns_latency >= 100.0) or has_dns_incident:
            evidence = []
            if dns_latency:
                evidence.append(f"DNS lookup latency is elevated ({dns_latency} ms >= 100 ms baseline threshold).")
            if has_dns_incident:
                evidence.append("Active DNS resolution failure incident detected.")

            opportunities.append(OptimizationOpportunity(
                id="opp_dns_flush",
                title="Flush Local DNS Resolver Cache",
                description="Clears potentially stale, corrupt, or poisoned local DNS records causing query delays.",
                category=OptimizationCategory.NETWORK,
                evidence=evidence,
                affected_subsystem="DNS Resolver",
                risk=OptimizationRiskLevel.SAFE,
                expected_effect="Reduces initial domain name resolution delays by up to 40-70ms.",
                confidence=0.88,
                current_state={"dns_latency_ms": dns_latency, "has_incident": has_dns_incident},
                proposed_state={"action": "ipconfig /flushdns"},
                reversible=True,
                requires_elevation=False,
                verification_plan="Query safe domain addresses across a 15-second stabilization window and verify lookup latency.",
                rollback_plan="Re-query authoritative DNS nameservers to restore local cache entries.",
                target_metric="dns_latency_ms",
            ))

        # 2. Background Process Priority Optimization
        cpu_util = get_val("cpu", "cpu_utilization_pct")
        cpu_obs = observations.get("cpu")
        top_procs = []
        if cpu_obs and hasattr(cpu_obs, "details") and isinstance(cpu_obs.details, dict):
            procs = cpu_obs.details.get("top_processes", [])
            if isinstance(procs, list):
                top_procs = procs

        if (cpu_util is not None and cpu_util >= 85.0) or is_gaming_active:
            for proc in top_procs[:2]:
                if isinstance(proc, dict):
                    pname = proc.get("name", "")
                    cpu_p = proc.get("cpu_percent", 0.0)
                    pid = proc.get("pid")
                    # Ignore system critical tasks
                    if cpu_p >= 18.0 and pid and not any(k in pname.lower() for k in ("system", "idle", "cs2", "game", "veyra")):
                        opportunities.append(OptimizationOpportunity(
                            id=f"opp_proc_{pid}",
                            title=f"Lower Background Task Priority: {pname}",
                            description=f"Process '{pname}' is consuming {cpu_p}% CPU during heavy processor load.",
                            category=OptimizationCategory.BACKGROUND_WORKLOAD,
                            evidence=[
                                f"Observed CPU utilization is high ({cpu_util}%).",
                                f"Background process '{pname}' [PID {pid}] is consuming {cpu_p}% CPU.",
                            ],
                            affected_subsystem="Process Scheduling",
                            risk=OptimizationRiskLevel.RECOMMENDED,
                            expected_effect="Frees CPU execution cycles and reduces frame-time jitter for primary tasks.",
                            confidence=0.85,
                            current_state={"pid": pid, "process_name": pname, "cpu_percent": cpu_p, "priority": "NORMAL"},
                            proposed_state={"pid": pid, "priority": "BELOW_NORMAL"},
                            reversible=True,
                            requires_elevation=False,
                            verification_plan="Monitor total CPU load and target process consumption over 30 seconds.",
                            rollback_plan="Restore target process priority class back to original priority.",
                            target_metric="cpu_utilization_pct",
                        ))
                        break

        # 3. Gaming High Performance Power Plan Hint
        if is_gaming_active:
            opportunities.append(OptimizationOpportunity(
                id="opp_power_gaming",
                title="Switch Power Scheme to High Performance",
                description="Prevents aggressive CPU core down-clocking and core parking during active gaming sessions.",
                category=OptimizationCategory.GAMING,
                evidence=[
                    "Active gaming session detected.",
                    "Power scheme optimization stabilizes CPU clock frequency during load transitions.",
                ],
                affected_subsystem="Windows Power Subsystem",
                risk=OptimizationRiskLevel.SAFE,
                expected_effect="Minimizes clock-speed frequency drops during sudden gameplay spikes.",
                confidence=0.82,
                current_state={"gaming_active": True},
                proposed_state={"power_scheme": "High Performance"},
                reversible=True,
                requires_elevation=False,
                verification_plan="Verify active power scheme GUID and observe CPU frequency stability.",
                rollback_plan="Restore previous power scheme GUID from snapshot upon session end.",
                target_metric="cpu_clock_stability",
            ))

        return opportunities
