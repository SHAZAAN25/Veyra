"""
VEYRA Real Memory (RAM) Collector.
Measures physical and committed RAM allocation and utilization.
"""
import time
from typing import Dict

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from collectors.common import StatefulCollector


class MemoryCollector(StatefulCollector):
    def __init__(self):
        super().__init__("system_memory")
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
            measurements["ram_utilization_pct"] = Measurement(
                metric_name="ram_utilization_pct",
                state=MetricState.COLLECTOR_UNAVAILABLE,
                value=None,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance="os:ram",
                error_message="Telemetry library not installed"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return self.create_observation(measurements, healthy=False, status_summary="UNAVAILABLE")

        try:
            vmem = self._psutil.virtual_memory()

            # 1. Total RAM (MB)
            total_mb = round(vmem.total / (1024 * 1024), 2)
            measurements["ram_total_mb"] = Measurement(
                metric_name="ram_total_mb",
                state=MetricState.AVAILABLE,
                value=total_mb,
                unit=MetricUnit.MEGABYTES,
                source_collector=self.name,
                provenance="os:virtual_memory:total"
            )

            # 2. Used RAM (MB)
            used_mb = round(vmem.used / (1024 * 1024), 2)
            measurements["ram_used_mb"] = Measurement(
                metric_name="ram_used_mb",
                state=MetricState.AVAILABLE,
                value=used_mb,
                unit=MetricUnit.MEGABYTES,
                source_collector=self.name,
                provenance="os:virtual_memory:used"
            )

            # 3. Available RAM (MB)
            available_mb = round(vmem.available / (1024 * 1024), 2)
            measurements["ram_available_mb"] = Measurement(
                metric_name="ram_available_mb",
                state=MetricState.AVAILABLE,
                value=available_mb,
                unit=MetricUnit.MEGABYTES,
                source_collector=self.name,
                provenance="os:virtual_memory:available"
            )

            # 4. Utilization Percentage (%)
            util_pct = float(vmem.percent)
            measurements["ram_utilization_pct"] = Measurement(
                metric_name="ram_utilization_pct",
                state=MetricState.AVAILABLE,
                value=util_pct,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance="os:virtual_memory:percent"
            )

            # 5. Swap / Pagefile Memory
            try:
                smem = self._psutil.swap_memory()
                swap_used_mb = round(smem.used / (1024 * 1024), 2)
                measurements["ram_swap_used_mb"] = Measurement(
                    metric_name="ram_swap_used_mb",
                    state=MetricState.AVAILABLE,
                    value=swap_used_mb,
                    unit=MetricUnit.MEGABYTES,
                    source_collector=self.name,
                    provenance="os:swap_memory:used"
                )
            except Exception:
                measurements["ram_swap_used_mb"] = Measurement(
                    metric_name="ram_swap_used_mb",
                    state=MetricState.NOT_SUPPORTED,
                    value=None,
                    unit=MetricUnit.MEGABYTES,
                    source_collector=self.name,
                    provenance="os:swap_memory",
                    error_message="Swap memory stats unavailable"
                )

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_success(duration_ms)
            return self.create_observation(measurements, healthy=True, status_summary="OK")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_failed(str(e), duration_ms)
            measurements["ram_utilization_pct"] = Measurement(
                metric_name="ram_utilization_pct",
                state=MetricState.MEASUREMENT_FAILED,
                value=None,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance="os:ram",
                error_message=f"Memory measurement failed: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary=f"ERROR: {e}")
