"""
VEYRA Real Disk & Storage Collector.
Measures primary system drive capacity, usage percentage, and disk I/O rates.
"""
import os
import time
from typing import Dict, Optional

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from collectors.common import StatefulCollector


class DiskCollector(StatefulCollector):
    def __init__(self, target_path: Optional[str] = None):
        super().__init__("system_disk")
        self._target_path = target_path or ("C:\\" if os.name == "nt" else "/")
        self._last_io_time: Optional[float] = None
        self._last_read_bytes: Optional[int] = None
        self._last_write_bytes: Optional[int] = None
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
            measurements["disk_utilization_pct"] = Measurement(
                metric_name="disk_utilization_pct",
                state=MetricState.COLLECTOR_UNAVAILABLE,
                value=None,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance="os:disk",
                error_message="Telemetry library not installed"
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return self.create_observation(measurements, healthy=False, status_summary="UNAVAILABLE")

        try:
            # 1. Disk usage of target drive
            usage = self._psutil.disk_usage(self._target_path)
            total_gb = round(usage.total / (1024 ** 3), 2)
            used_gb = round(usage.used / (1024 ** 3), 2)
            free_gb = round(usage.free / (1024 ** 3), 2)
            util_pct = float(usage.percent)

            measurements["disk_total_gb"] = Measurement(
                metric_name="disk_total_gb",
                state=MetricState.AVAILABLE,
                value=total_gb,
                unit=MetricUnit.GIGABYTES,
                source_collector=self.name,
                provenance=f"os:disk_usage:{self._target_path}"
            )
            measurements["disk_used_gb"] = Measurement(
                metric_name="disk_used_gb",
                state=MetricState.AVAILABLE,
                value=used_gb,
                unit=MetricUnit.GIGABYTES,
                source_collector=self.name,
                provenance=f"os:disk_usage:{self._target_path}"
            )
            measurements["disk_free_gb"] = Measurement(
                metric_name="disk_free_gb",
                state=MetricState.AVAILABLE,
                value=free_gb,
                unit=MetricUnit.GIGABYTES,
                source_collector=self.name,
                provenance=f"os:disk_usage:{self._target_path}"
            )
            measurements["disk_utilization_pct"] = Measurement(
                metric_name="disk_utilization_pct",
                state=MetricState.AVAILABLE,
                value=util_pct,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance=f"os:disk_usage:{self._target_path}"
            )

            # 2. Disk I/O Activity
            current_time = time.monotonic()
            io_counters = self._psutil.disk_io_counters()

            if io_counters and self._last_io_time is not None:
                dt = current_time - self._last_io_time
                if dt > 0.1:
                    read_rate_mb = round((io_counters.read_bytes - (self._last_read_bytes or 0)) / (dt * 1024 * 1024), 2)
                    write_rate_mb = round((io_counters.write_bytes - (self._last_write_bytes or 0)) / (dt * 1024 * 1024), 2)
                    read_rate_mb = max(0.0, read_rate_mb)
                    write_rate_mb = max(0.0, write_rate_mb)

                    measurements["disk_read_mbps"] = Measurement(
                        metric_name="disk_read_mbps",
                        state=MetricState.AVAILABLE,
                        value=read_rate_mb,
                        unit=MetricUnit.MEGABYTES,
                        source_collector=self.name,
                        provenance="os:disk_io:read_rate"
                    )
                    measurements["disk_write_mbps"] = Measurement(
                        metric_name="disk_write_mbps",
                        state=MetricState.AVAILABLE,
                        value=write_rate_mb,
                        unit=MetricUnit.MEGABYTES,
                        source_collector=self.name,
                        provenance="os:disk_io:write_rate"
                    )
            else:
                # First sample: rate not available yet
                measurements["disk_read_mbps"] = Measurement(
                    metric_name="disk_read_mbps",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.MEGABYTES,
                    source_collector=self.name,
                    provenance="os:disk_io:read_rate",
                    error_message="Awaiting baseline sample interval"
                )
                measurements["disk_write_mbps"] = Measurement(
                    metric_name="disk_write_mbps",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.MEGABYTES,
                    source_collector=self.name,
                    provenance="os:disk_io:write_rate",
                    error_message="Awaiting baseline sample interval"
                )

            if io_counters:
                self._last_io_time = current_time
                self._last_read_bytes = io_counters.read_bytes
                self._last_write_bytes = io_counters.write_bytes

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_success(duration_ms)
            return self.create_observation(measurements, healthy=True, status_summary="OK")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_failed(str(e), duration_ms)
            measurements["disk_utilization_pct"] = Measurement(
                metric_name="disk_utilization_pct",
                state=MetricState.MEASUREMENT_FAILED,
                value=None,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance="os:disk",
                error_message=f"Disk measurement failed: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary=f"ERROR: {e}")
