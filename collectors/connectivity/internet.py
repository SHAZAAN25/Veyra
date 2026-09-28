"""
VEYRA Real Internet Connectivity, Latency, Packet Loss & Jitter Collector (Layer 4).
Measures real RTT latency, packet loss percentage, and calculates statistical jitter
using the RFC 3550 / RFC 1889 Mean Absolute Deviation method over successive packets.
Never fabricates jitter from a single ping sample.
"""
import re
import time
from typing import Dict, List, Optional

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from app.core.security import run_safe_subprocess
from collectors.common import StatefulCollector, NetworkLayer


def calculate_rfc3550_jitter(rtt_samples: List[float]) -> Optional[float]:
    """
    Computes statistical jitter as the mean absolute deviation of consecutive RTT samples:
    Jitter = (1 / (N - 1)) * sum(|RTT[i+1] - RTT[i]|) for i in 0 .. N-2
    Returns None if fewer than 2 valid samples exist.
    """
    if len(rtt_samples) < 2:
        return None
    diffs = [abs(rtt_samples[i + 1] - rtt_samples[i]) for i in range(len(rtt_samples) - 1)]
    return round(sum(diffs) / len(diffs), 2)


class InternetCollector(StatefulCollector):
    def __init__(self, target_host: str = "1.1.1.1", probe_count: int = 4, timeout_ms: int = 1000):
        super().__init__("connectivity_internet")
        self.target_host = target_host
        self.probe_count = max(2, probe_count)
        self.timeout_ms = timeout_ms

    def collect(self) -> Observation:
        start_time = time.perf_counter()
        measurements: Dict[str, Measurement] = {}

        cmd = ["ping", "-n", str(self.probe_count), "-w", str(self.timeout_ms), self.target_host]

        try:
            # Enforce max execution timeout proportional to probes
            max_sec = (self.probe_count * (self.timeout_ms / 1000.0)) + 3.0
            res = run_safe_subprocess(cmd, timeout_seconds=max_sec)

            # Parse individual packet reply times
            rtt_matches = re.findall(r"time[=<](\d+)ms", res.stdout)
            rtts = [float(t) for t in rtt_matches]

            sent = self.probe_count
            received = len(rtts)
            lost = sent - received
            loss_pct = round((lost / sent) * 100.0, 1)

            is_reachable = (received > 0)

            # 1. Reachable
            measurements["internet_reachable"] = Measurement(
                metric_name="internet_reachable",
                state=MetricState.AVAILABLE,
                value=is_reachable,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_4_INTERNET.value}:ping:{self.target_host}"
            )

            # 2. Packet Loss (%)
            measurements["internet_packet_loss_pct"] = Measurement(
                metric_name="internet_packet_loss_pct",
                state=MetricState.AVAILABLE,
                value=loss_pct,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_4_INTERNET.value}:ping:{self.target_host}:loss"
            )

            # 3. Latency RTT (ms)
            if received > 0:
                avg_rtt = round(sum(rtts) / len(rtts), 2)
                measurements["internet_latency_rtt_ms"] = Measurement(
                    metric_name="internet_latency_rtt_ms",
                    state=MetricState.AVAILABLE,
                    value=avg_rtt,
                    unit=MetricUnit.MILLISECONDS,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_4_INTERNET.value}:ping:{self.target_host}:avg_rtt"
                )
            else:
                measurements["internet_latency_rtt_ms"] = Measurement(
                    metric_name="internet_latency_rtt_ms",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.MILLISECONDS,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_4_INTERNET.value}:ping:{self.target_host}",
                    error_message=f"All {self.probe_count} ping probes timed out"
                )

            # 4. Statistical Jitter (ms) via RFC 3550
            if received >= 2:
                jitter_val = calculate_rfc3550_jitter(rtts)
                measurements["internet_jitter_ms"] = Measurement(
                    metric_name="internet_jitter_ms",
                    state=MetricState.AVAILABLE,
                    value=jitter_val,
                    unit=MetricUnit.MILLISECONDS,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_4_INTERNET.value}:rfc3550_mad"
                )
            else:
                measurements["internet_jitter_ms"] = Measurement(
                    metric_name="internet_jitter_ms",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.MILLISECONDS,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_4_INTERNET.value}:rfc3550_mad",
                    error_message="At least 2 packets required to calculate statistical jitter"
                )

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            if is_reachable:
                self._mark_success(duration_ms)
                return self.create_observation(measurements, healthy=True, status_summary="CONNECTED")
            else:
                self._mark_degraded(f"100% packet loss to upstream target {self.target_host}", duration_ms)
                return self.create_observation(measurements, healthy=False, status_summary="OUTAGE")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_failed(str(e), duration_ms)
            measurements["internet_reachable"] = Measurement(
                metric_name="internet_reachable",
                state=MetricState.MEASUREMENT_FAILED,
                value=None,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_4_INTERNET.value}:error",
                error_message=f"Ping execution error: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary=f"ERROR: {e}")
