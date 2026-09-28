"""
VEYRA Real GPU Collector.
Queries hardware GPU metrics using safe Windows interfaces (e.g. nvidia-smi).
Gracefully handles systems with AMD/Intel or missing dedicated GPU by emitting explicit NOT_SUPPORTED states.
Never fabricates GPU telemetry.
"""
import time
from typing import Dict, Optional

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from app.core.security import run_safe_subprocess
from app.core.exceptions import SecurityViolationError
from collectors.common import StatefulCollector


class GpuCollector(StatefulCollector):
    def __init__(self):
        super().__init__("hardware_gpu")
        self._smi_command = [
            "nvidia-smi",
            "--query-gpu=name,driver_version,utilization.gpu,utilization.memory,memory.total,memory.used,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits"
        ]

    def collect(self) -> Observation:
        start_time = time.perf_counter()
        measurements: Dict[str, Measurement] = {}

        try:
            res = run_safe_subprocess(self._smi_command, timeout_seconds=2.0)
            if res.returncode != 0 or not res.stdout.strip():
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self._mark_unsupported("NVIDIA GPU or nvidia-smi utility not available on host.")
                return self._build_unsupported_observation("nvidia-smi returned non-zero or empty output")

            # Parse CSV output: e.g. "NVIDIA GeForce RTX 4050 Laptop GPU, 591.59, 0, 1, 6141, 737, 50, 13.74"
            line = res.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]

            if len(parts) < 7:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self._mark_degraded("Malformed nvidia-smi output format", duration_ms)
                return self._build_unsupported_observation("Malformed nvidia-smi CSV line")

            name = parts[0]
            driver = parts[1]
            gpu_util = float(parts[2]) if parts[2] != "[N/A]" else None
            mem_util = float(parts[3]) if parts[3] != "[N/A]" else None
            mem_total = float(parts[4]) if parts[4] != "[N/A]" else None
            mem_used = float(parts[5]) if parts[5] != "[N/A]" else None
            temp = float(parts[6]) if parts[6] != "[N/A]" else None
            power = float(parts[7]) if len(parts) > 7 and parts[7] != "[N/A]" else None

            # 1. GPU Name
            measurements["gpu_name"] = Measurement(
                metric_name="gpu_name",
                state=MetricState.AVAILABLE,
                value=name,
                unit=MetricUnit.STRING,
                source_collector=self.name,
                provenance="hardware:nvidia-smi:name"
            )

            # 2. Driver version
            measurements["gpu_driver_version"] = Measurement(
                metric_name="gpu_driver_version",
                state=MetricState.AVAILABLE,
                value=driver,
                unit=MetricUnit.STRING,
                source_collector=self.name,
                provenance="hardware:nvidia-smi:driver"
            )

            # 3. GPU Utilization
            if gpu_util is not None:
                measurements["gpu_utilization_pct"] = Measurement(
                    metric_name="gpu_utilization_pct",
                    state=MetricState.AVAILABLE,
                    value=gpu_util,
                    unit=MetricUnit.PERCENTAGE,
                    source_collector=self.name,
                    provenance="hardware:nvidia-smi:utilization.gpu"
                )
            else:
                measurements["gpu_utilization_pct"] = Measurement(
                    metric_name="gpu_utilization_pct",
                    state=MetricState.NOT_SUPPORTED,
                    value=None,
                    unit=MetricUnit.PERCENTAGE,
                    source_collector=self.name,
                    provenance="hardware:nvidia-smi:utilization.gpu",
                    error_message="Utilization not reported by driver"
                )

            # 4. Memory Utilization
            if mem_util is not None:
                measurements["gpu_memory_utilization_pct"] = Measurement(
                    metric_name="gpu_memory_utilization_pct",
                    state=MetricState.AVAILABLE,
                    value=mem_util,
                    unit=MetricUnit.PERCENTAGE,
                    source_collector=self.name,
                    provenance="hardware:nvidia-smi:utilization.memory"
                )
            else:
                measurements["gpu_memory_utilization_pct"] = Measurement(
                    metric_name="gpu_memory_utilization_pct",
                    state=MetricState.NOT_SUPPORTED,
                    value=None,
                    unit=MetricUnit.PERCENTAGE,
                    source_collector=self.name,
                    provenance="hardware:nvidia-smi:utilization.memory"
                )

            # 5. Memory Used (MB)
            if mem_used is not None:
                measurements["gpu_memory_used_mb"] = Measurement(
                    metric_name="gpu_memory_used_mb",
                    state=MetricState.AVAILABLE,
                    value=mem_used,
                    unit=MetricUnit.MEGABYTES,
                    source_collector=self.name,
                    provenance="hardware:nvidia-smi:memory.used"
                )
            else:
                measurements["gpu_memory_used_mb"] = Measurement(
                    metric_name="gpu_memory_used_mb",
                    state=MetricState.NOT_SUPPORTED,
                    value=None,
                    unit=MetricUnit.MEGABYTES,
                    source_collector=self.name,
                    provenance="hardware:nvidia-smi:memory.used"
                )

            # 6. Temperature (C)
            if temp is not None:
                measurements["gpu_temperature_c"] = Measurement(
                    metric_name="gpu_temperature_c",
                    state=MetricState.AVAILABLE,
                    value=temp,
                    unit=MetricUnit.CELSIUS,
                    source_collector=self.name,
                    provenance="hardware:nvidia-smi:temperature.gpu"
                )
            else:
                measurements["gpu_temperature_c"] = Measurement(
                    metric_name="gpu_temperature_c",
                    state=MetricState.NOT_SUPPORTED,
                    value=None,
                    unit=MetricUnit.CELSIUS,
                    source_collector=self.name,
                    provenance="hardware:nvidia-smi:temperature.gpu"
                )

            # 7. Power Draw (W)
            if power is not None:
                measurements["gpu_power_draw_w"] = Measurement(
                    metric_name="gpu_power_draw_w",
                    state=MetricState.AVAILABLE,
                    value=power,
                    unit=MetricUnit.COUNT,
                    source_collector=self.name,
                    provenance="hardware:nvidia-smi:power.draw"
                )

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_success(duration_ms)
            return self.create_observation(measurements, healthy=True, status_summary="OK")

        except (SecurityViolationError, Exception) as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_unsupported(f"GPU telemetry unavailable: {e}")
            return self._build_unsupported_observation(str(e))

    def _build_unsupported_observation(self, reason: str) -> Observation:
        measurements: Dict[str, Measurement] = {
            "gpu_utilization_pct": Measurement(
                metric_name="gpu_utilization_pct",
                state=MetricState.NOT_SUPPORTED,
                value=None,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance="hardware:gpu",
                error_message=reason
            ),
            "gpu_temperature_c": Measurement(
                metric_name="gpu_temperature_c",
                state=MetricState.NOT_SUPPORTED,
                value=None,
                unit=MetricUnit.CELSIUS,
                source_collector=self.name,
                provenance="hardware:gpu",
                error_message=reason
            )
        }
        return self.create_observation(measurements, healthy=False, status_summary="UNSUPPORTED")
