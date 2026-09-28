"""
VEYRA Real CPU Collector.
Measures real processor utilization, core counts, and operating frequencies.
Never fabricates values; handles unsupported frequency/load counters explicitly.
"""
import time
from typing import Dict

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from collectors.common import StatefulCollector


class CpuCollector(StatefulCollector):
    def __init__(self):
        super().__init__("system_cpu")
        self._psutil_available = True
        try:
            import psutil
            self._psutil = psutil
            # Warm up cpu_percent
            self._psutil.cpu_percent(interval=None)
        except ImportError:
            self._psutil_available = False
            self._psutil = None

    def collect(self) -> Observation:
        start_time = time.perf_counter()
        measurements: Dict[str, Measurement] = {}

        if not self._psutil_available or self._psutil is None:
            self._mark_unsupported("psutil library is not available on host.")
            measurements["cpu_utilization_pct"] = Measurement(
                metric_name="cpu_utilization_pct",
                state=MetricState.COLLECTOR_UNAVAILABLE,
                value=None,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance="os:cpu",
                error_message="Telemetry library not installed"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return self.create_observation(measurements, healthy=False, status_summary="UNAVAILABLE")

        try:
            # 1. Utilization percentage
            cpu_pct = float(self._psutil.cpu_percent(interval=None))
            measurements["cpu_utilization_pct"] = Measurement(
                metric_name="cpu_utilization_pct",
                state=MetricState.AVAILABLE,
                value=cpu_pct,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance="os:cpu_percent"
            )

            # 2. Logical Cores
            logical_cores = self._psutil.cpu_count(logical=True)
            if logical_cores is not None:
                measurements["cpu_count_logical"] = Measurement(
                    metric_name="cpu_count_logical",
                    state=MetricState.AVAILABLE,
                    value=int(logical_cores),
                    unit=MetricUnit.COUNT,
                    source_collector=self.name,
                    provenance="os:cpu_count"
                )
            else:
                measurements["cpu_count_logical"] = Measurement(
                    metric_name="cpu_count_logical",
                    state=MetricState.NOT_SUPPORTED,
                    value=None,
                    unit=MetricUnit.COUNT,
                    source_collector=self.name,
                    provenance="os:cpu_count",
                    error_message="Logical core count not reported by OS"
                )

            # 3. Physical Cores
            physical_cores = self._psutil.cpu_count(logical=False)
            if physical_cores is not None:
                measurements["cpu_count_physical"] = Measurement(
                    metric_name="cpu_count_physical",
                    state=MetricState.AVAILABLE,
                    value=int(physical_cores),
                    unit=MetricUnit.COUNT,
                    source_collector=self.name,
                    provenance="os:cpu_count"
                )
            else:
                measurements["cpu_count_physical"] = Measurement(
                    metric_name="cpu_count_physical",
                    state=MetricState.NOT_SUPPORTED,
                    value=None,
                    unit=MetricUnit.COUNT,
                    source_collector=self.name,
                    provenance="os:cpu_count",
                    error_message="Physical core count not reported by OS"
                )

            # 4. Frequencies
            try:
                freq = self._psutil.cpu_freq()
                if freq and freq.current > 0:
                    measurements["cpu_freq_current_mhz"] = Measurement(
                        metric_name="cpu_freq_current_mhz",
                        state=MetricState.AVAILABLE,
                        value=float(freq.current),
                        unit=MetricUnit.HERTZ,
                        source_collector=self.name,
                        provenance="os:cpu_freq"
                    )
                else:
                    measurements["cpu_freq_current_mhz"] = Measurement(
                        metric_name="cpu_freq_current_mhz",
                        state=MetricState.NOT_SUPPORTED,
                        value=None,
                        unit=MetricUnit.HERTZ,
                        source_collector=self.name,
                        provenance="os:cpu_freq",
                        error_message="CPU frequency reporting not supported on host"
                    )
            except Exception as e:
                measurements["cpu_freq_current_mhz"] = Measurement(
                    metric_name="cpu_freq_current_mhz",
                    state=MetricState.NOT_SUPPORTED,
                    value=None,
                    unit=MetricUnit.HERTZ,
                    source_collector=self.name,
                    provenance="os:cpu_freq",
                    error_message=str(e)
                )

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_success(duration_ms)
            return self.create_observation(measurements, healthy=True, status_summary="OK")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_failed(str(e), duration_ms)
            measurements["cpu_utilization_pct"] = Measurement(
                metric_name="cpu_utilization_pct",
                state=MetricState.MEASUREMENT_FAILED,
                value=None,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance="os:cpu",
                error_message=f"CPU measurement failed: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary=f"ERROR: {e}")
