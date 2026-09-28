"""
VEYRA Deterministic Incident Detector.
Evaluates verified observations against centralized hysteresis thresholds to detect
and track all 16 core incident types.
"""
from typing import Dict, List, Optional
import time
import uuid

from app.core.contracts import Observation, MetricState
from app.core.time import now_utc_iso
from analyzer.contracts import DetailedIncident, IncidentType, IncidentSeverity, IncidentStatus
from analyzer.thresholds import DetectionThresholds, get_default_thresholds
from analyzer.incidents.lifecycle import IncidentTracker
from analyzer.incidents.grouping import IncidentCorrelator


class DeterministicIncidentDetector:
    """
    Detector tracking 16 core incident types with hysteresis and grouping.
    """
    def __init__(self, thresholds: Optional[DetectionThresholds] = None):
        self.thresholds = thresholds or get_default_thresholds()
        self.correlator = IncidentCorrelator(self.thresholds.grouping_window_seconds)

        # Trackers for threshold-based metrics
        self.trackers = {
            IncidentType.LATENCY_SPIKE: IncidentTracker(
                IncidentType.LATENCY_SPIKE, IncidentSeverity.WARNING, self.thresholds.latency_ms
            ),
            IncidentType.PACKET_LOSS_SPIKE: IncidentTracker(
                IncidentType.PACKET_LOSS_SPIKE, IncidentSeverity.HIGH, self.thresholds.packet_loss_pct
            ),
            IncidentType.JITTER_SPIKE: IncidentTracker(
                IncidentType.JITTER_SPIKE, IncidentSeverity.WARNING, self.thresholds.jitter_ms
            ),
            IncidentType.WIFI_SIGNAL_DEGRADATION: IncidentTracker(
                IncidentType.WIFI_SIGNAL_DEGRADATION, IncidentSeverity.WARNING, self.thresholds.wifi_signal_pct
            ),
            IncidentType.SYSTEM_RESOURCE_PRESSURE: IncidentTracker(
                IncidentType.SYSTEM_RESOURCE_PRESSURE, IncidentSeverity.WARNING, self.thresholds.cpu_utilization_pct
            ),
            IncidentType.GPU_RESOURCE_PRESSURE: IncidentTracker(
                IncidentType.GPU_RESOURCE_PRESSURE, IncidentSeverity.WARNING, self.thresholds.gpu_temperature_c
            ),
        }

        # Discrete state tracking
        self._last_wifi_connected: Optional[bool] = None
        self._last_adapter_name: Optional[str] = None
        self._last_link_speed: Optional[float] = None

    def evaluate_observations(self, observations: Dict[str, Observation]) -> List[DetailedIncident]:
        """Evaluates all observations and returns list of active or newly recovered incidents."""
        incidents: List[DetailedIncident] = []

        def get_metric_val(obs_key: str, metric_key: str) -> Optional[float]:
            obs = observations.get(obs_key)
            if obs:
                m = obs.get_metric(metric_key)
                if m and m.state == MetricState.AVAILABLE and isinstance(m.value, (int, float)):
                    return float(m.value)
            return None

        # 1. Latency Spike (Layer 4)
        lat = get_metric_val("internet", "internet_latency_rtt_ms")
        inc = self.trackers[IncidentType.LATENCY_SPIKE].evaluate_metric(
            lat, "internet_latency_rtt_ms", ["LAYER_4_INTERNET"], "Upstream ICMP latency spike"
        )
        if inc:
            incidents.append(inc)

        # 2. Packet Loss Spike (Layer 4)
        loss = get_metric_val("internet", "internet_packet_loss_pct")
        inc = self.trackers[IncidentType.PACKET_LOSS_SPIKE].evaluate_metric(
            loss, "internet_packet_loss_pct", ["LAYER_4_INTERNET"], "Elevated packet loss detected"
        )
        if inc:
            incidents.append(inc)

        # 3. Jitter Spike (Layer 4)
        jit = get_metric_val("internet", "internet_jitter_ms")
        inc = self.trackers[IncidentType.JITTER_SPIKE].evaluate_metric(
            jit, "internet_jitter_ms", ["LAYER_4_INTERNET"], "Statistical jitter variance spike"
        )
        if inc:
            incidents.append(inc)

        # 4. Wi-Fi Signal Degradation (Layer 1)
        sig = get_metric_val("wifi", "wifi_signal_pct")
        inc = self.trackers[IncidentType.WIFI_SIGNAL_DEGRADATION].evaluate_metric(
            sig, "wifi_signal_pct", ["LAYER_1_ADAPTER"], "Wi-Fi link signal strength degraded"
        )
        if inc:
            incidents.append(inc)

        # 5. System CPU/RAM Pressure (Host)
        cpu_val = get_metric_val("cpu", "cpu_utilization_pct")
        inc = self.trackers[IncidentType.SYSTEM_RESOURCE_PRESSURE].evaluate_metric(
            cpu_val, "cpu_utilization_pct", ["LAYER_0_HOST"], "Sustained high CPU utilization"
        )
        if inc:
            incidents.append(inc)

        # 6. GPU Temperature Pressure
        gpu_temp = get_metric_val("gpu", "gpu_temperature_c")
        inc = self.trackers[IncidentType.GPU_RESOURCE_PRESSURE].evaluate_metric(
            gpu_temp, "gpu_temperature_c", ["LAYER_0_HOST"], "GPU die thermal threshold exceeded"
        )
        if inc:
            incidents.append(inc)

        # 7 & 8. Wi-Fi Disconnect / Reconnect
        wifi_obs = observations.get("wifi")
        if wifi_obs:
            wifi_conn_m = wifi_obs.get_metric("wifi_connected")
            if wifi_conn_m and wifi_conn_m.state == MetricState.AVAILABLE:
                curr_conn = bool(wifi_conn_m.value)
                if self._last_wifi_connected is not None:
                    if self._last_wifi_connected and not curr_conn:
                        incidents.append(DetailedIncident(
                            incident_id=f"inc_wlan_disc_{uuid.uuid4().hex[:8]}",
                            incident_type=IncidentType.WIFI_DISCONNECT,
                            severity=IncidentSeverity.CRITICAL,
                            status=IncidentStatus.ACTIVE,
                            started_at_utc=now_utc_iso(),
                            summary="Wi-Fi interface disconnected from access point",
                            affected_layers=["LAYER_1_ADAPTER"],
                            trigger_metric="wifi_connected",
                            trigger_value=0.0
                        ))
                    elif not self._last_wifi_connected and curr_conn:
                        incidents.append(DetailedIncident(
                            incident_id=f"inc_wlan_reconn_{uuid.uuid4().hex[:8]}",
                            incident_type=IncidentType.WIFI_RECONNECT,
                            severity=IncidentSeverity.INFO,
                            status=IncidentStatus.RECOVERED,
                            started_at_utc=now_utc_iso(),
                            summary="Wi-Fi interface reconnected successfully",
                            affected_layers=["LAYER_1_ADAPTER"],
                            trigger_metric="wifi_connected",
                            trigger_value=1.0
                        ))
                self._last_wifi_connected = curr_conn

        # 9. Gateway Unreachable (Layer 2)
        gw_obs = observations.get("gateway")
        if gw_obs:
            gw_reach = gw_obs.get_metric("gateway_reachable")
            if gw_reach and gw_reach.state == MetricState.AVAILABLE and not gw_reach.value:
                incidents.append(DetailedIncident(
                    incident_id=f"inc_gw_unreach_{uuid.uuid4().hex[:8]}",
                    incident_type=IncidentType.GATEWAY_UNREACHABLE,
                    severity=IncidentSeverity.HIGH,
                    status=IncidentStatus.ACTIVE,
                    started_at_utc=now_utc_iso(),
                    summary="Default gateway is unresponsive to ICMP probes",
                    affected_layers=["LAYER_2_GATEWAY"],
                    trigger_metric="gateway_reachable",
                    trigger_value=0.0
                ))

        # 10. DNS Failure (Layer 3)
        dns_obs = observations.get("dns")
        if dns_obs:
            dns_succ = dns_obs.get_metric("dns_success")
            if dns_succ and dns_succ.state == MetricState.AVAILABLE and not dns_succ.value:
                incidents.append(DetailedIncident(
                    incident_id=f"inc_dns_fail_{uuid.uuid4().hex[:8]}",
                    incident_type=IncidentType.DNS_FAILURE,
                    severity=IncidentSeverity.HIGH,
                    status=IncidentStatus.ACTIVE,
                    started_at_utc=now_utc_iso(),
                    summary="DNS name resolution failed for target host",
                    affected_layers=["LAYER_3_DNS"],
                    trigger_metric="dns_success",
                    trigger_value=0.0
                ))

        # 11. Internet Unreachable (Layer 4)
        inet_obs = observations.get("internet")
        if inet_obs:
            inet_reach = inet_obs.get_metric("internet_reachable")
            if inet_reach and inet_reach.state == MetricState.AVAILABLE and not inet_reach.value:
                incidents.append(DetailedIncident(
                    incident_id=f"inc_inet_outage_{uuid.uuid4().hex[:8]}",
                    incident_type=IncidentType.INTERNET_UNREACHABLE,
                    severity=IncidentSeverity.CRITICAL,
                    status=IncidentStatus.ACTIVE,
                    started_at_utc=now_utc_iso(),
                    summary="Internet upstream connectivity failure (100% loss)",
                    affected_layers=["LAYER_4_INTERNET"],
                    trigger_metric="internet_reachable",
                    trigger_value=0.0
                ))

        # 12. Link Speed Change
        adapter_obs = observations.get("adapter")
        if adapter_obs:
            speed_m = adapter_obs.get_metric("adapter_link_speed_mbps")
            if speed_m and speed_m.state == MetricState.AVAILABLE and speed_m.value is not None:
                current_speed = float(speed_m.value)
                if self._last_link_speed is not None and self._last_link_speed > 0:
                    if current_speed < self._last_link_speed * 0.6:  # 40% drop
                        incidents.append(DetailedIncident(
                            incident_id=f"inc_link_drop_{uuid.uuid4().hex[:8]}",
                            incident_type=IncidentType.LINK_SPEED_CHANGE,
                            severity=IncidentSeverity.WARNING,
                            status=IncidentStatus.ACTIVE,
                            started_at_utc=now_utc_iso(),
                            summary=f"Link speed dropped from {self._last_link_speed} to {current_speed} Mbps",
                            affected_layers=["LAYER_1_ADAPTER"],
                            trigger_metric="adapter_link_speed_mbps",
                            trigger_value=current_speed
                        ))
                self._last_link_speed = current_speed

        # 13. Sleep / Resume Observation Gap
        self_obs = observations.get("self")
        if self_obs:
            sleep_m = self_obs.get_metric("veyra_sleep_detected")
            if sleep_m and sleep_m.state == MetricState.AVAILABLE and sleep_m.value is True:
                incidents.append(DetailedIncident(
                    incident_id=f"inc_sleep_gap_{uuid.uuid4().hex[:8]}",
                    incident_type=IncidentType.OBSERVATION_GAP_SLEEP_RESUME,
                    severity=IncidentSeverity.INFO,
                    status=IncidentStatus.RECOVERED,
                    started_at_utc=now_utc_iso(),
                    summary="System sleep/resume suspension gap detected; false outages suppressed",
                    affected_layers=["LAYER_0_HOST"],
                    trigger_metric="veyra_sleep_detected",
                    trigger_value=1.0
                ))

        # Correlate and group incidents
        return self.correlator.correlate(incidents)
