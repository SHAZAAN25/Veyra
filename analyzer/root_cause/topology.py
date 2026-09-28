"""
VEYRA Cross-Layer Network Topology Foundation.
Models the layered PC -> Wi-Fi/Adapter -> Gateway -> DNS -> Internet pipeline.
Tracks operational health for each node without inferring failures beyond supporting evidence.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional

from app.core.contracts import Observation, MetricState


class TopologyNodeState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class TopologyNode:
    node_id: str
    layer_name: str
    state: TopologyNodeState = TopologyNodeState.UNKNOWN
    details: Dict[str, Any] = field(default_factory=dict)
    last_updated_monotonic: float = 0.0


class NetworkTopologyTracker:
    """
    Maintains the state of the 5-node network topology:
    [LAPTOP] -> [ADAPTER_WIFI] -> [GATEWAY] -> [DNS] -> [INTERNET]
    """
    def __init__(self):
        self.nodes: Dict[str, TopologyNode] = {
            "laptop": TopologyNode(node_id="laptop", layer_name="LAYER_0_HOST", state=TopologyNodeState.HEALTHY),
            "adapter": TopologyNode(node_id="adapter", layer_name="LAYER_1_ADAPTER"),
            "gateway": TopologyNode(node_id="gateway", layer_name="LAYER_2_GATEWAY"),
            "dns": TopologyNode(node_id="dns", layer_name="LAYER_3_DNS"),
            "internet": TopologyNode(node_id="internet", layer_name="LAYER_4_INTERNET"),
        }

    def update_topology(self, observations: Dict[str, Observation]) -> None:
        """Updates topology nodes based strictly on verified observations."""
        # 1. Adapter & Wi-Fi Node
        adapter_obs = observations.get("adapter")
        wifi_obs = observations.get("wifi")
        if adapter_obs:
            is_up = adapter_obs.get_metric("adapter_is_up")
            if is_up and is_up.state == MetricState.AVAILABLE and is_up.value is True:
                # Check Wi-Fi state if present
                if wifi_obs:
                    wifi_conn = wifi_obs.get_metric("wifi_connected")
                    if wifi_conn and wifi_conn.state == MetricState.AVAILABLE and wifi_conn.value is False:
                        self.nodes["adapter"].state = TopologyNodeState.DEGRADED
                        self.nodes["adapter"].details["reason"] = "Wi-Fi disconnected"
                    else:
                        self.nodes["adapter"].state = TopologyNodeState.HEALTHY
                else:
                    self.nodes["adapter"].state = TopologyNodeState.HEALTHY
            else:
                self.nodes["adapter"].state = TopologyNodeState.FAILED
                self.nodes["adapter"].details["reason"] = "Network adapter is down"

        # 2. Gateway Node (Layer 2)
        gw_obs = observations.get("gateway")
        if gw_obs:
            gw_reach = gw_obs.get_metric("gateway_reachable")
            if gw_reach and gw_reach.state == MetricState.AVAILABLE:
                self.nodes["gateway"].state = TopologyNodeState.HEALTHY if gw_reach.value else TopologyNodeState.FAILED
            else:
                self.nodes["gateway"].state = TopologyNodeState.UNAVAILABLE
        else:
            self.nodes["gateway"].state = TopologyNodeState.UNKNOWN

        # 3. DNS Node (Layer 3)
        dns_obs = observations.get("dns")
        if dns_obs:
            dns_succ = dns_obs.get_metric("dns_success")
            if dns_succ and dns_succ.state == MetricState.AVAILABLE:
                self.nodes["dns"].state = TopologyNodeState.HEALTHY if dns_succ.value else TopologyNodeState.FAILED
            else:
                self.nodes["dns"].state = TopologyNodeState.UNAVAILABLE
        else:
            self.nodes["dns"].state = TopologyNodeState.UNKNOWN

        # 4. Internet Node (Layer 4)
        inet_obs = observations.get("internet")
        if inet_obs:
            inet_reach = inet_obs.get_metric("internet_reachable")
            loss = inet_obs.get_metric("internet_packet_loss_pct")
            if inet_reach and inet_reach.state == MetricState.AVAILABLE:
                if not inet_reach.value:
                    self.nodes["internet"].state = TopologyNodeState.FAILED
                elif loss and loss.state == MetricState.AVAILABLE and float(loss.value) > 10.0:
                    self.nodes["internet"].state = TopologyNodeState.DEGRADED
                else:
                    self.nodes["internet"].state = TopologyNodeState.HEALTHY
            else:
                self.nodes["internet"].state = TopologyNodeState.UNAVAILABLE
        else:
            self.nodes["internet"].state = TopologyNodeState.UNKNOWN

    def get_topology_summary(self) -> Dict[str, str]:
        return {nid: node.state.value for nid, node in self.nodes.items()}
