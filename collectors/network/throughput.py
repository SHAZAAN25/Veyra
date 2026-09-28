"""
VEYRA Real Local Network Throughput Collector.
Calculates actual RX/TX network throughput (Mbps) using local OS network delta counters.
Strictly local and lightweight; never calls external speed-test servers continuously.
"""
import time
from typing import Dict, Optional

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from collectors.common import StatefulCollector, NetworkLayer


class ThroughputCollector(StatefulCollector):
    def __init__(self):
        super().__init__("network_throughput")
        self._last_time: Optional[float] = None
        self._last_bytes_recv: Optional[int] = None
        self._last_bytes_sent: Optional[int] = None
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
            measurements["network_rx_mbps"] = Measurement(
                metric_name="network_rx_mbps",
                state=MetricState.COLLECTOR_UNAVAILABLE,
                value=None,
                unit=MetricUnit.MEGABITS_PER_SECOND,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:throughput",
                error_message="Telemetry library not installed"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return self.create_observation(measurements, healthy=False, status_summary="UNAVAILABLE")

        try:
            counters = self._psutil.net_io_counters()
            current_time = time.monotonic()

            if self._last_time is not None and counters:
                dt = current_time - self._last_time
                if dt > 0.1:
                    delta_recv = max(0, counters.bytes_recv - (self._last_bytes_recv or 0))
                    delta_sent = max(0, counters.bytes_sent - (self._last_bytes_sent or 0))

                    # Convert bytes/sec to Megabits/sec (Mbps)
                    rx_mbps = round((delta_recv * 8.0) / (dt * 1_000_000.0), 3)
                    tx_mbps = round((delta_sent * 8.0) / (dt * 1_000_000.0), 3)

                    measurements["network_rx_mbps"] = Measurement(
                        metric_name="network_rx_mbps",
                        state=MetricState.AVAILABLE,
                        value=rx_mbps,
                        unit=MetricUnit.MEGABITS_PER_SECOND,
                        source_collector=self.name,
                        provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:net_io_counters:rx"
                    )
                    measurements["network_tx_mbps"] = Measurement(
                        metric_name="network_tx_mbps",
                        state=MetricState.AVAILABLE,
                        value=tx_mbps,
                        unit=MetricUnit.MEGABITS_PER_SECOND,
                        source_collector=self.name,
                        provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:net_io_counters:tx"
                    )
                else:
                    measurements["network_rx_mbps"] = Measurement(
                        metric_name="network_rx_mbps",
                        state=MetricState.UNAVAILABLE,
                        value=None,
                        unit=MetricUnit.MEGABITS_PER_SECOND,
                        source_collector=self.name,
                        provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:throughput",
                        error_message="Sampling interval too short"
                    )
                    measurements["network_tx_mbps"] = Measurement(
                        metric_name="network_tx_mbps",
                        state=MetricState.UNAVAILABLE,
                        value=None,
                        unit=MetricUnit.MEGABITS_PER_SECOND,
                        source_collector=self.name,
                        provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:throughput",
                        error_message="Sampling interval too short"
                    )
            else:
                # First baseline cycle
                measurements["network_rx_mbps"] = Measurement(
                    metric_name="network_rx_mbps",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.MEGABITS_PER_SECOND,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:throughput",
                    error_message="Awaiting baseline throughput sample"
                )
                measurements["network_tx_mbps"] = Measurement(
                    metric_name="network_tx_mbps",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.MEGABITS_PER_SECOND,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:throughput",
                    error_message="Awaiting baseline throughput sample"
                )

            if counters:
                self._last_time = current_time
                self._last_bytes_recv = counters.bytes_recv
                self._last_bytes_sent = counters.bytes_sent

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_success(duration_ms)
            return self.create_observation(measurements, healthy=True, status_summary="OK")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_failed(str(e), duration_ms)
            measurements["network_rx_mbps"] = Measurement(
                metric_name="network_rx_mbps",
                state=MetricState.MEASUREMENT_FAILED,
                value=None,
                unit=MetricUnit.MEGABITS_PER_SECOND,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:throughput",
                error_message=f"Throughput calculation error: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary=f"ERROR: {e}")
