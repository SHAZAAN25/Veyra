"""
VEYRA Telemetry Collection Coordinator.
Orchestrates modular collectors across System, GPU, Network, Wi-Fi, and Connectivity layers.
Enforces non-blocking execution, collector health tracking, Veyra self-resource monitoring,
and system sleep/gap detection.
"""
import os
import time
from typing import Dict, List, Optional

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from app.core.logging import get_logger
from app.core.time import TimeTracker, now_utc_iso
from collectors import BaseCollector, CollectorHealth, CollectorHealthStatus
from collectors.system.cpu import CpuCollector
from collectors.system.memory import MemoryCollector
from collectors.system.disk import DiskCollector
from collectors.gpu.gpu_collector import GpuCollector
from collectors.network.adapter import AdapterCollector
from collectors.network.throughput import ThroughputCollector
from collectors.wifi.wifi_collector import WifiCollector
from collectors.connectivity.gateway import GatewayCollector
from collectors.connectivity.internet import InternetCollector
from collectors.connectivity.dns import DnsCollector


class CollectionCoordinator:
    """
    Coordinates modular collectors and aggregates observations into verified cycles.
    Tracks self-monitoring metrics and detects system suspension gaps.
    """
    def __init__(self, expected_interval_seconds: float = 2.0):
        self.logger = get_logger("coordinator")
        self.expected_interval = expected_interval_seconds
        self.time_tracker = TimeTracker()

        # Initialize all modular collectors
        self.collectors: Dict[str, BaseCollector] = {
            "cpu": CpuCollector(),
            "memory": MemoryCollector(),
            "disk": DiskCollector(),
            "gpu": GpuCollector(),
            "adapter": AdapterCollector(),
            "throughput": ThroughputCollector(),
            "wifi": WifiCollector(),
            "gateway": GatewayCollector(),
            "internet": InternetCollector(),
            "dns": DnsCollector(),
        }

        # Self-resource tracking
        self._process = None
        try:
            import psutil
            self._process = psutil.Process(os.getpid())
            # Warm up cpu percent
            self._process.cpu_percent(interval=None)
        except Exception:
            pass

    def run_cycle(self) -> Dict[str, Observation]:
        """
        Executes a single synchronized collection cycle across all collectors.
        Returns a dictionary of observations keyed by collector identifier.
        """
        cycle_start = time.perf_counter()

        # 1. Sleep / Gap Detection
        elapsed_seconds, sleep_detected = self.time_tracker.check_interval(self.expected_interval)
        if sleep_detected:
            self.logger.warning(
                "SYSTEM_SLEEP_DETECTED",
                f"System suspension/gap detected ({round(elapsed_seconds, 1)}s). Avoiding false outage classification."
            )

        cycle_observations: Dict[str, Observation] = {}

        # 2. Execute Each Collector with Complete Failure Isolation
        for key, collector in self.collectors.items():
            try:
                obs = collector.collect()
                cycle_observations[key] = obs
            except Exception as e:
                self.logger.error("COLLECTOR_EXECUTION_FAILURE", f"Collector '{key}' raised unexpected exception: {e}")
                # Create emergency failed observation
                failed_obs = Observation(
                    observation_id=f"obs_err_{key}_{int(time.time())}",
                    timestamp_utc=now_utc_iso(),
                    collector_name=collector.name,
                    measurements={
                        f"{key}_status": Measurement(
                            metric_name=f"{key}_status",
                            state=MetricState.MEASUREMENT_FAILED,
                            value=None,
                            unit=MetricUnit.STRING,
                            source_collector=collector.name,
                            provenance="coordinator:exception",
                            error_message=f"Unhandled collector crash: {e}"
                        )
                    },
                    collector_healthy=False,
                    status_summary=f"CRASH: {e}"
                )
                cycle_observations[key] = failed_obs

        # 3. Collect Veyra Self-Monitoring Foundation
        cycle_duration_ms = round((time.perf_counter() - cycle_start) * 1000.0, 2)
        self_obs = self._collect_self_metrics(cycle_duration_ms, cycle_observations, sleep_detected)
        cycle_observations["self"] = self_obs

        return cycle_observations

    def _collect_self_metrics(
        self,
        cycle_duration_ms: float,
        observations: Dict[str, Observation],
        sleep_detected: bool
    ) -> Observation:
        """Collects internal Veyra resource usage and collector health metrics."""
        measurements: Dict[str, Measurement] = {}

        # 1. Cycle Latency
        measurements["veyra_cycle_duration_ms"] = Measurement(
            metric_name="veyra_cycle_duration_ms",
            state=MetricState.AVAILABLE,
            value=cycle_duration_ms,
            unit=MetricUnit.MILLISECONDS,
            source_collector="veyra_self",
            provenance="coordinator:cycle_timing"
        )

        # 2. System Sleep Flag
        measurements["veyra_sleep_detected"] = Measurement(
            metric_name="veyra_sleep_detected",
            state=MetricState.AVAILABLE,
            value=sleep_detected,
            unit=MetricUnit.BOOLEAN,
            source_collector="veyra_self",
            provenance="time_tracker:gap_detector"
        )

        # 3. Healthy / Unhealthy Collector Counts
        healthy_count = sum(1 for obs in observations.values() if obs.collector_healthy)
        total_count = len(observations)

        measurements["veyra_healthy_collectors_count"] = Measurement(
            metric_name="veyra_healthy_collectors_count",
            state=MetricState.AVAILABLE,
            value=healthy_count,
            unit=MetricUnit.COUNT,
            source_collector="veyra_self",
            provenance="coordinator:health_summary"
        )
        measurements["veyra_total_collectors_count"] = Measurement(
            metric_name="veyra_total_collectors_count",
            state=MetricState.AVAILABLE,
            value=total_count,
            unit=MetricUnit.COUNT,
            source_collector="veyra_self",
            provenance="coordinator:health_summary"
        )

        # 4. Process CPU & Memory usage
        if self._process is not None:
            try:
                proc_cpu = float(self._process.cpu_percent(interval=None))
                proc_mem_mb = round(self._process.memory_info().rss / (1024 * 1024), 2)

                measurements["veyra_process_cpu_pct"] = Measurement(
                    metric_name="veyra_process_cpu_pct",
                    state=MetricState.AVAILABLE,
                    value=proc_cpu,
                    unit=MetricUnit.PERCENTAGE,
                    source_collector="veyra_self",
                    provenance="os:process:cpu"
                )
                measurements["veyra_process_memory_mb"] = Measurement(
                    metric_name="veyra_process_memory_mb",
                    state=MetricState.AVAILABLE,
                    value=proc_mem_mb,
                    unit=MetricUnit.MEGABYTES,
                    source_collector="veyra_self",
                    provenance="os:process:memory"
                )
            except Exception:
                pass

        return Observation(
            observation_id=f"obs_self_{int(time.time()*1000)}",
            timestamp_utc=now_utc_iso(),
            collector_name="veyra_self",
            measurements=measurements,
            collector_healthy=True,
            status_summary="OK"
        )

    def get_collector_health_map(self) -> Dict[str, CollectorHealth]:
        """Returns the health status of all registered collectors."""
        return {key: collector.check_health() for key, collector in self.collectors.items()}

    def get_hardware_capabilities(self) -> Dict[str, bool]:
        """
        Exposes hardware capabilities cleanly for future consumption (e.g. Future Optimization Engine).
        Does NOT execute optimizations.
        """
        gpu_health = self.collectors["gpu"].check_health()
        wifi_health = self.collectors["wifi"].check_health()
        return {
            "has_dedicated_gpu": gpu_health.status != CollectorHealthStatus.UNSUPPORTED,
            "has_wifi_adapter": wifi_health.status != CollectorHealthStatus.UNSUPPORTED,
            "has_psutil": getattr(self.collectors["cpu"], "_psutil_available", False)
        }
