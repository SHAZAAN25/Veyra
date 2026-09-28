"""
VEYRA Real Network Adapter Collector (Layer 1).
Inspects host physical/virtual adapters, connection states, negotiated link speeds, and IP addresses.
"""
import socket
import time
from typing import Dict, Optional

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from collectors.common import StatefulCollector, NetworkLayer


class AdapterCollector(StatefulCollector):
    def __init__(self):
        super().__init__("network_adapter")
        self._psutil_available = True
        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            self._psutil_available = False
            self._psutil = None

    def collect(self) -> Observation:
        start_time = time.perf_counter()
        measurements: Dict[str, Measurement] = {}

        if not self._psutil_available or self._psutil is None:
            self._mark_unsupported("psutil library is not available on host.")
            measurements["adapter_link_status"] = Measurement(
                metric_name="adapter_link_status",
                state=MetricState.COLLECTOR_UNAVAILABLE,
                value=None,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:psutil",
                error_message="Telemetry library not installed"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return self.create_observation(measurements, healthy=False, status_summary="UNAVAILABLE")

        try:
            stats = self._psutil.net_if_stats()
            addrs = self._psutil.net_if_addrs()

            active_name: Optional[str] = None
            active_speed: float = 0.0
            active_ip: Optional[str] = None
            active_mac: Optional[str] = None

            # Prioritize connected interfaces with valid IPv4
            for iface_name, iface_stat in stats.items():
                if iface_stat.isup and iface_name in addrs:
                    for addr in addrs[iface_name]:
                        # AF_INET is IPv4
                        if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                            active_name = iface_name
                            active_speed = float(iface_stat.speed)
                            active_ip = addr.address
                            break
                        elif addr.family == getattr(self._psutil, "AF_LINK", -1):
                            active_mac = addr.address
                    if active_name:
                        break

            if active_name is None:
                # No active network adapter found
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self._mark_degraded("No active non-loopback network adapter connected", duration_ms)
                measurements["adapter_name"] = Measurement(
                    metric_name="adapter_name",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.STRING,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:net_if_stats",
                    error_message="No active interface with IPv4 detected"
                )
                measurements["adapter_is_up"] = Measurement(
                    metric_name="adapter_is_up",
                    state=MetricState.AVAILABLE,
                    value=False,
                    unit=MetricUnit.BOOLEAN,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:net_if_stats"
                )
                return self.create_observation(measurements, healthy=False, status_summary="NO_ACTIVE_ADAPTER")

            # 1. Adapter Name
            measurements["adapter_name"] = Measurement(
                metric_name="adapter_name",
                state=MetricState.AVAILABLE,
                value=active_name,
                unit=MetricUnit.STRING,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:iface_name"
            )

            # 2. Is Up
            measurements["adapter_is_up"] = Measurement(
                metric_name="adapter_is_up",
                state=MetricState.AVAILABLE,
                value=True,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:isup"
            )

            # 3. Link Speed (Mbps)
            if active_speed > 0:
                measurements["adapter_link_speed_mbps"] = Measurement(
                    metric_name="adapter_link_speed_mbps",
                    state=MetricState.AVAILABLE,
                    value=active_speed,
                    unit=MetricUnit.MEGABITS_PER_SECOND,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:speed"
                )
            else:
                measurements["adapter_link_speed_mbps"] = Measurement(
                    metric_name="adapter_link_speed_mbps",
                    state=MetricState.NOT_SUPPORTED,
                    value=None,
                    unit=MetricUnit.MEGABITS_PER_SECOND,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:speed",
                    error_message="Interface driver does not report link speed"
                )

            # 4. IP Address
            if active_ip:
                measurements["adapter_ipv4_address"] = Measurement(
                    metric_name="adapter_ipv4_address",
                    state=MetricState.AVAILABLE,
                    value=active_ip,
                    unit=MetricUnit.STRING,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:ipv4"
                )

            # 5. MAC Address (Sanitized)
            if active_mac:
                measurements["adapter_mac_address"] = Measurement(
                    metric_name="adapter_mac_address",
                    state=MetricState.AVAILABLE,
                    value=active_mac,
                    unit=MetricUnit.STRING,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:mac"
                )

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_success(duration_ms)
            return self.create_observation(measurements, healthy=True, status_summary="OK")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_failed(str(e), duration_ms)
            measurements["adapter_name"] = Measurement(
                metric_name="adapter_name",
                state=MetricState.MEASUREMENT_FAILED,
                value=None,
                unit=MetricUnit.STRING,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:error",
                error_message=f"Failed to inspect network adapter: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary=f"ERROR: {e}")
