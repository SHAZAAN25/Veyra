"""
VEYRA Cross-Layer Root Cause Investigator.
Assembles the topological diagnosis graph from Local PC to Upstream Internet,
determines deterministic root cause, and generates evidence-grounded assessments.
"""
import logging
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from app.core.time import now_utc_iso
from diagnostics.contracts import (
    CrossLayerGraph,
    DiagnosticLayer,
    DiagnosticReport,
    DiagnosticStatus,
    GraphNode,
    LayerStatus,
    TestItemResult,
)
from diagnostics.probes import (
    AdapterProbe,
    DnsProbe,
    GatewayProbe,
    InternetProbe,
    SystemResourceProbe,
    WifiProbe,
)

logger = logging.getLogger("veyra.diagnostics.investigator")


class CrossLayerInvestigator:
    """Executes multi-layer diagnostics and constructs the cross-layer root cause graph."""

    def __init__(
        self,
        system_probe: Optional[SystemResourceProbe] = None,
        adapter_probe: Optional[AdapterProbe] = None,
        wifi_probe: Optional[WifiProbe] = None,
        gateway_probe: Optional[GatewayProbe] = None,
        dns_probe: Optional[DnsProbe] = None,
        internet_probe: Optional[InternetProbe] = None,
    ):
        self.system_probe = system_probe or SystemResourceProbe()
        self.adapter_probe = adapter_probe or AdapterProbe()
        self.wifi_probe = wifi_probe or WifiProbe()
        self.gateway_probe = gateway_probe or GatewayProbe()
        self.dns_probe = dns_probe or DnsProbe()
        self.internet_probe = internet_probe or InternetProbe()

    def run_investigation(
        self,
        target: str = "internet",
        run_type: str = "FULL_SYSTEM_AND_NETWORK",
        timeout_seconds: float = 15.0,
        cancel_event: Optional[threading.Event] = None,
        historical_incidents: Optional[List[Any]] = None,
    ) -> DiagnosticReport:
        """
        Executes bounded deterministic probes across all layers.
        Checks cancel_event between steps for immediate cancellation safety.
        """
        run_id = f"diag_{uuid.uuid4().hex[:12]}"
        start_utc = now_utc_iso()
        t0 = time.perf_counter()

        test_results: List[TestItemResult] = []
        evidence: List[str] = []
        affected_layers: List[str] = []

        # 1. System Resource Probe
        if cancel_event and cancel_event.is_set():
            return self._build_cancelled_report(run_id, target, run_type, start_utc, t0)
        sys_res = self.system_probe.execute(timeout_seconds=2.0)
        test_results.append(sys_res)

        # 2. Network Adapter Probe
        if cancel_event and cancel_event.is_set():
            return self._build_cancelled_report(run_id, target, run_type, start_utc, t0)
        adapter_res = self.adapter_probe.execute(timeout_seconds=2.0)
        test_results.append(adapter_res)

        # 3. Wi-Fi Interface Probe
        if cancel_event and cancel_event.is_set():
            return self._build_cancelled_report(run_id, target, run_type, start_utc, t0)
        wifi_res = self.wifi_probe.execute(timeout_seconds=2.5)
        test_results.append(wifi_res)

        # 4. Gateway Reachability Probe
        if cancel_event and cancel_event.is_set():
            return self._build_cancelled_report(run_id, target, run_type, start_utc, t0)
        gateway_res = self.gateway_probe.execute(timeout_seconds=3.0)
        test_results.append(gateway_res)

        # 5. DNS Resolution Probe
        if cancel_event and cancel_event.is_set():
            return self._build_cancelled_report(run_id, target, run_type, start_utc, t0)
        dns_res = self.dns_probe.execute(timeout_seconds=3.0)
        test_results.append(dns_res)

        # 6. Internet Upstream Probe
        if cancel_event and cancel_event.is_set():
            return self._build_cancelled_report(run_id, target, run_type, start_utc, t0)
        internet_res = self.internet_probe.execute(timeout_seconds=3.5)
        test_results.append(internet_res)

        duration = time.perf_counter() - t0

        # Construct Graph Nodes
        nodes: Dict[str, GraphNode] = {
            "pc": GraphNode(
                node_id="pc",
                name="Local Host PC",
                layer=DiagnosticLayer.LOCAL_PC,
                status=sys_res.status,
                details=f"CPU: {sys_res.details.get('cpu_utilization_pct')}%, RAM: {sys_res.details.get('ram_utilization_pct')}%",
                metrics=sys_res.details,
            ),
            "adapter": GraphNode(
                node_id="adapter",
                name="Network Adapter",
                layer=DiagnosticLayer.ADAPTER,
                status=adapter_res.status,
                details=f"Active adapters: {adapter_res.details.get('active_adapters_count', 0)}",
                metrics=adapter_res.details,
            ),
            "wifi": GraphNode(
                node_id="wifi",
                name="Wi-Fi Link",
                layer=DiagnosticLayer.WIFI,
                status=wifi_res.status,
                details=f"SSID: {wifi_res.details.get('ssid')}, Signal: {wifi_res.details.get('signal_pct')}%",
                metrics=wifi_res.details,
            ),
            "gateway": GraphNode(
                node_id="gateway",
                name="Default Gateway",
                layer=DiagnosticLayer.GATEWAY,
                status=gateway_res.status,
                details=f"IP: {gateway_res.details.get('gateway_ip')}, Latency: {gateway_res.latency_ms} ms, Loss: {gateway_res.packet_loss_pct}%",
                metrics=gateway_res.details,
            ),
            "dns": GraphNode(
                node_id="dns",
                name="DNS Subsystem",
                layer=DiagnosticLayer.DNS,
                status=dns_res.status,
                details=f"Avg query: {dns_res.latency_ms} ms, Failures: {dns_res.details.get('failures', 0)}",
                metrics=dns_res.details,
            ),
            "internet": GraphNode(
                node_id="internet",
                name="Internet Upstream",
                layer=DiagnosticLayer.INTERNET,
                status=internet_res.status,
                details=f"Target: {internet_res.target}, Latency: {internet_res.latency_ms} ms, Loss: {internet_res.packet_loss_pct}%",
                metrics=internet_res.details,
            ),
        }

        # Deterministic Root Cause & Assessment Calculation
        primary_node, assessment, confidence, recs = self._assess_root_cause(nodes, test_results)

        for nid, node in nodes.items():
            if node.status in (LayerStatus.FAILED, LayerStatus.DEGRADED):
                affected_layers.append(node.layer.value)
                node.evidence.append(f"Layer status is {node.status.value}: {node.details}")
                evidence.append(f"{node.name} is {node.status.value}: {node.details}")

        graph = CrossLayerGraph(
            nodes=nodes,
            primary_root_cause_node=primary_node,
            summary=assessment,
        )

        # Related incident IDs if provided
        related_ids = []
        if historical_incidents:
            for inc in historical_incidents:
                iid = getattr(inc, "incident_id", None) or getattr(inc, "id", None)
                if iid:
                    related_ids.append(str(iid))

        return DiagnosticReport(
            run_id=run_id,
            target=target,
            run_type=run_type,
            status=DiagnosticStatus.COMPLETED,
            started_at_utc=start_utc,
            ended_at_utc=now_utc_iso(),
            duration_seconds=round(duration, 3),
            graph=graph,
            assessment=assessment,
            confidence=confidence,
            affected_layers=affected_layers,
            test_results=test_results,
            evidence=evidence,
            recommendations=recs,
            related_incident_ids=related_ids,
            historical_context=f"Correlated with {len(related_ids)} recent incidents." if related_ids else "No recent correlated incidents.",
        )

    def _assess_root_cause(
        self,
        nodes: Dict[str, GraphNode],
        results: List[TestItemResult]
    ) -> Tuple[Optional[str], str, float, List[str]]:
        """Determines the primary root cause node and generates structured recommendations."""
        pc_node = nodes["pc"]
        adapter_node = nodes["adapter"]
        wifi_node = nodes["wifi"]
        gateway_node = nodes["gateway"]
        dns_node = nodes["dns"]
        internet_node = nodes["internet"]

        recs: List[str] = []

        # 1. Local Adapter Failure
        if adapter_node.status == LayerStatus.FAILED:
            recs.append("Check physical network cable or re-enable the network adapter.")
            return (
                "adapter",
                "Local Network Adapter Issue: No active or operational network interface found.",
                0.95,
                recs
            )

        # 2. Wi-Fi Issue
        if wifi_node.status == LayerStatus.FAILED:
            recs.append("Connect to an authorized Wi-Fi network or enable your Wi-Fi interface.")
            return (
                "wifi",
                "Wi-Fi Connection Issue: Wi-Fi adapter is disconnected.",
                0.90,
                recs
            )
        if wifi_node.status == LayerStatus.DEGRADED:
            recs.append("Reposition PC closer to the access point or switch to the 5 GHz band.")
            return (
                "wifi",
                f"Wi-Fi Signal Degradation: Signal strength is critically low ({wifi_node.metrics.get('signal_pct')}%).",
                0.85,
                recs
            )

        # 3. Gateway Failure
        if gateway_node.status == LayerStatus.FAILED:
            recs.append("Verify router/gateway power, check local Ethernet cable, or restart local router.")
            return (
                "gateway",
                "Default Gateway Issue: Local router/gateway is unreachable from this device.",
                0.92,
                recs
            )

        # 4. DNS Failure
        if dns_node.status == LayerStatus.FAILED and gateway_node.status == LayerStatus.HEALTHY:
            recs.append("Flush DNS cache using 'ipconfig /flushdns' or configure reliable fallback DNS servers (1.1.1.1, 8.8.8.8).")
            return (
                "dns",
                "DNS Subsystem Issue: Gateway is reachable, but domain resolution queries failed completely.",
                0.92,
                recs
            )

        # 5. Upstream Internet Failure
        if internet_node.status == LayerStatus.FAILED and gateway_node.status == LayerStatus.HEALTHY:
            recs.append("Check ISP modem status or contact internet service provider regarding upstream outage.")
            return (
                "internet",
                "Upstream Internet Outage: Local network is operational, but public internet reachability is completely down.",
                0.90,
                recs
            )

        # 6. Degraded Internet or High Jitter
        if internet_node.status == LayerStatus.DEGRADED:
            loss = internet_node.metrics.get("packet_loss_pct", 0)
            lat = internet_node.metrics.get("latency_ms")
            recs.append("Inspect concurrent downloads or streaming on the local network; test over wired connection.")
            return (
                "internet",
                f"Internet Upstream Degradation: Observed packet loss ({loss}%) or elevated latency ({lat} ms).",
                0.85,
                recs
            )

        # 7. System Resource Pressure
        if pc_node.status in (LayerStatus.FAILED, LayerStatus.DEGRADED):
            recs.append("Inspect background tasks consuming excessive CPU or RAM.")
            return (
                "pc",
                "Local System Resource Pressure: Heavy CPU or memory saturation is degrading system responsiveness.",
                0.88,
                recs
            )

        # 8. All Layers Healthy
        recs.append("System and network connections are operating within normal parameters.")
        return (
            None,
            "All Diagnostic Layers Healthy: No local, gateway, DNS, or upstream network issues detected.",
            0.95,
            recs
        )

    def _build_cancelled_report(
        self,
        run_id: str,
        target: str,
        run_type: str,
        start_utc: str,
        t0: float,
    ) -> DiagnosticReport:
        return DiagnosticReport(
            run_id=run_id,
            target=target,
            run_type=run_type,
            status=DiagnosticStatus.CANCELLED,
            started_at_utc=start_utc,
            ended_at_utc=now_utc_iso(),
            duration_seconds=round(time.perf_counter() - t0, 3),
            assessment="Diagnostic investigation cancelled by user or timeout.",
            confidence=0.0,
            evidence=["Investigation terminated early via cancellation signal."],
        )
