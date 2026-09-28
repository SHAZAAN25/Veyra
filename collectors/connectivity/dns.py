"""
VEYRA Real DNS Collector (Layer 3).
Measures real DNS query resolution latency and success/failure states.
"""
import socket
import time
from typing import Dict, Optional

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from collectors.common import StatefulCollector, NetworkLayer


class DnsCollector(StatefulCollector):
    def __init__(self, target_host: str = "google.com"):
        super().__init__("connectivity_dns")
        self.target_host = target_host

    def collect(self) -> Observation:
        start_time = time.perf_counter()
        measurements: Dict[str, Measurement] = {}

        # 1. Target host
        measurements["dns_target_host"] = Measurement(
            metric_name="dns_target_host",
            state=MetricState.AVAILABLE,
            value=self.target_host,
            unit=MetricUnit.STRING,
            source_collector=self.name,
            provenance=f"{NetworkLayer.LAYER_3_DNS.value}:target"
        )

        try:
            dns_start = time.perf_counter()
            # Perform real resolution
            addr_info = socket.getaddrinfo(self.target_host, 80, family=socket.AF_INET)
            dns_duration_ms = round((time.perf_counter() - dns_start) * 1000.0, 2)

            resolved_ip = addr_info[0][4][0] if addr_info else "UNKNOWN"

            # 2. Success state
            measurements["dns_success"] = Measurement(
                metric_name="dns_success",
                state=MetricState.AVAILABLE,
                value=True,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_3_DNS.value}:socket:getaddrinfo"
            )

            # 3. Response time (ms)
            measurements["dns_response_ms"] = Measurement(
                metric_name="dns_response_ms",
                state=MetricState.AVAILABLE,
                value=dns_duration_ms,
                unit=MetricUnit.MILLISECONDS,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_3_DNS.value}:latency"
            )

            # 4. Resolved IP
            measurements["dns_resolved_ip"] = Measurement(
                metric_name="dns_resolved_ip",
                state=MetricState.AVAILABLE,
                value=resolved_ip,
                unit=MetricUnit.STRING,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_3_DNS.value}:resolved_ip"
            )

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_success(duration_ms)
            return self.create_observation(measurements, healthy=True, status_summary="RESOLVED")

        except socket.gaierror as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_degraded(f"DNS resolution failed: {e}", duration_ms)
            measurements["dns_success"] = Measurement(
                metric_name="dns_success",
                state=MetricState.AVAILABLE,
                value=False,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_3_DNS.value}:error"
            )
            measurements["dns_response_ms"] = Measurement(
                metric_name="dns_response_ms",
                state=MetricState.UNAVAILABLE,
                value=None,
                unit=MetricUnit.MILLISECONDS,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_3_DNS.value}:error",
                error_message=f"DNS query error: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary="DNS_FAILURE")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_failed(str(e), duration_ms)
            measurements["dns_success"] = Measurement(
                metric_name="dns_success",
                state=MetricState.MEASUREMENT_FAILED,
                value=None,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_3_DNS.value}:error",
                error_message=f"DNS execution exception: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary=f"ERROR: {e}")
