"""
VEYRA Real Gateway Collector (Layer 2).
Discovers the active IPv4 default gateway and measures reachability and local hop latency.
"""
import re
import time
from typing import Dict, Optional

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from app.core.security import run_safe_subprocess
from collectors.common import StatefulCollector, NetworkLayer


class GatewayCollector(StatefulCollector):
    def __init__(self, override_gateway: Optional[str] = None):
        super().__init__("connectivity_gateway")
        self._override_gateway = override_gateway
        self._cached_gateway: Optional[str] = None
        self._last_discovery_time: float = 0.0

    def _discover_gateway(self) -> Optional[str]:
        if self._override_gateway:
            return self._override_gateway

        now = time.monotonic()
        if self._cached_gateway and (now - self._last_discovery_time) < 30.0:
            return self._cached_gateway

        try:
            res = run_safe_subprocess(["ipconfig"], timeout_seconds=3.0)
            if res.returncode == 0:
                matches = re.findall(r"Default Gateway[ .]*: ([0-9.]+)", res.stdout)
                for gw in matches:
                    if gw != "0.0.0.0" and not gw.startswith("127."):
                        self._cached_gateway = gw
                        self._last_discovery_time = now
                        return gw
        except Exception as e:
            self.logger.warning("GATEWAY_DISCOVERY_ERROR", f"Failed to discover gateway: {e}")

        return None

    def collect(self) -> Observation:
        start_time = time.perf_counter()
        measurements: Dict[str, Measurement] = {}

        gateway_ip = self._discover_gateway()

        if not gateway_ip:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_degraded("No default gateway discovered on host.", duration_ms)
            measurements["gateway_reachable"] = Measurement(
                metric_name="gateway_reachable",
                state=MetricState.AVAILABLE,
                value=False,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_2_GATEWAY.value}:ipconfig"
            )
            measurements["gateway_ip"] = Measurement(
                metric_name="gateway_ip",
                state=MetricState.UNAVAILABLE,
                value=None,
                unit=MetricUnit.STRING,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_2_GATEWAY.value}:ipconfig",
                error_message="Default gateway not assigned"
            )
            measurements["gateway_rtt_ms"] = Measurement(
                metric_name="gateway_rtt_ms",
                state=MetricState.UNAVAILABLE,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_2_GATEWAY.value}:ping",
                error_message="No gateway to probe"
            )
            return self.create_observation(measurements, healthy=False, status_summary="NO_GATEWAY")

        # 1. Gateway IP
        measurements["gateway_ip"] = Measurement(
            metric_name="gateway_ip",
            state=MetricState.AVAILABLE,
            value=gateway_ip,
            unit=MetricUnit.STRING,
            source_collector=self.name,
            provenance=f"{NetworkLayer.LAYER_2_GATEWAY.value}:discovery"
        )

        # 2. Probe Gateway Latency via ping
        try:
            ping_res = run_safe_subprocess(
                ["ping", "-n", "2", "-w", "1000", gateway_ip],
                timeout_seconds=3.0
            )

            time_matches = re.findall(r"time[=<](\d+)ms", ping_res.stdout)
            if time_matches:
                rtts = [float(t) for t in time_matches]
                avg_rtt = round(sum(rtts) / len(rtts), 2)

                measurements["gateway_reachable"] = Measurement(
                    metric_name="gateway_reachable",
                    state=MetricState.AVAILABLE,
                    value=True,
                    unit=MetricUnit.BOOLEAN,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_2_GATEWAY.value}:icmp"
                )
                measurements["gateway_rtt_ms"] = Measurement(
                    metric_name="gateway_rtt_ms",
                    state=MetricState.AVAILABLE,
                    value=avg_rtt,
                    unit=MetricUnit.MILLISECONDS,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_2_GATEWAY.value}:icmp:{gateway_ip}"
                )
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self._mark_success(duration_ms)
                return self.create_observation(measurements, healthy=True, status_summary="OK")

            else:
                # Gateway unreachable or timed out
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self._mark_degraded(f"Gateway {gateway_ip} did not respond to ICMP.", duration_ms)
                measurements["gateway_reachable"] = Measurement(
                    metric_name="gateway_reachable",
                    state=MetricState.AVAILABLE,
                    value=False,
                    unit=MetricUnit.BOOLEAN,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_2_GATEWAY.value}:icmp:{gateway_ip}"
                )
                measurements["gateway_rtt_ms"] = Measurement(
                    metric_name="gateway_rtt_ms",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.MILLISECONDS,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_2_GATEWAY.value}:icmp:{gateway_ip}",
                    error_message="Gateway ICMP probe timed out"
                )
                return self.create_observation(measurements, healthy=False, status_summary="GATEWAY_UNREACHABLE")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_failed(str(e), duration_ms)
            measurements["gateway_reachable"] = Measurement(
                metric_name="gateway_reachable",
                state=MetricState.MEASUREMENT_FAILED,
                value=None,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_2_GATEWAY.value}:error",
                error_message=f"Gateway probe failed: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary=f"ERROR: {e}")
