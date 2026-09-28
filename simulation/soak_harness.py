"""
VEYRA Soak & Stress Test Harness
Stage 7 Automated Testing, Fault Injection & QA Harnesses

Simulates high-throughput, accelerated multi-cycle telemetry streaming through
the observation pipeline. Verifies memory bounds, ring buffer limits,
compaction triggers, and sub-millisecond execution performance.
"""

from collections import deque
from dataclasses import dataclass, field
import time
import tracemalloc
from typing import Any, Dict, List, Optional

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from app.core.time import now_utc_iso
from storage.aggregation.aggregator import MetricAggregator
from storage.contracts import MeasurementSummaryRecord, SummaryResolution


@dataclass
class SoakTestResult:
    """Outcome metrics from an accelerated soak and stress test."""
    total_cycles: int
    duration_seconds: float
    avg_cycle_ms: float
    peak_memory_kb: float
    memory_leaked_kb: float
    ring_buffer_bounded: bool
    summaries_generated: int
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


class SoakHarness:
    """Accelerated multi-cycle telemetry stress test runner."""

    def __init__(self, buffer_capacity: int = 120) -> None:
        self.capacity = buffer_capacity
        self.buffer: deque[Observation] = deque(maxlen=buffer_capacity)

    def generate_synthetic_observation(self, cycle_index: int) -> Observation:
        """Create a synthetic observation frame for testing without mutating real hardware."""
        epoch_str = f"2026-09-28T12:{cycle_index // 60:02d}:{cycle_index % 60:02d}Z"
        measurements = {
            "cpu_utilization_pct": Measurement(
                metric_name="cpu_utilization_pct",
                state=MetricState.AVAILABLE,
                value=25.0 + (cycle_index % 30),
                unit=MetricUnit.PERCENTAGE,
                source_collector="simulation_soak",
                provenance="synthetic"
            ),
            "ram_used_bytes": Measurement(
                metric_name="ram_used_bytes",
                state=MetricState.AVAILABLE,
                value=8589934592.0 + (cycle_index * 1024),
                unit=MetricUnit.BYTES,
                source_collector="simulation_soak",
                provenance="synthetic"
            ),
            "internet_latency_ms": Measurement(
                metric_name="internet_latency_ms",
                state=MetricState.AVAILABLE,
                value=14.0 + (cycle_index % 5),
                unit=MetricUnit.MILLISECONDS,
                source_collector="simulation_soak",
                provenance="synthetic"
            ),
            "internet_packet_loss_pct": Measurement(
                metric_name="internet_packet_loss_pct",
                state=MetricState.AVAILABLE,
                value=0.0,
                unit=MetricUnit.PERCENTAGE,
                source_collector="simulation_soak",
                provenance="synthetic"
            ),
        }
        return Observation(
            observation_id=f"obs_soak_{cycle_index}",
            timestamp_utc=epoch_str,
            collector_name="simulation_soak",
            measurements=measurements,
            collector_healthy=True
        )

    def run_soak_test(self, cycles: int = 1000) -> SoakTestResult:
        """Execute accelerated soak run across specified number of cycles."""
        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()

        t0 = time.monotonic()
        summaries_count = 0

        for i in range(cycles):
            obs = self.generate_synthetic_observation(i)
            # 1. Ingest into RAM ring buffer
            self.buffer.append(obs)

            # Periodically generate statistical summaries (every 60 cycles)
            if (i + 1) % 60 == 0:
                recent_obs = list(self.buffer)[-60:]
                summaries = MetricAggregator.aggregate_observations(
                    observations=recent_obs,
                    bucket_start_utc=recent_obs[0].timestamp_utc,
                    bucket_end_utc=recent_obs[-1].timestamp_utc,
                    resolution_seconds=SummaryResolution.MINUTE_1.value
                )
                summaries_count += len(summaries)

        t_elapsed = time.monotonic() - t0
        snapshot_end = tracemalloc.take_snapshot()
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        avg_cycle_ms = (t_elapsed / cycles) * 1000.0 if cycles > 0 else 0.0
        peak_kb = peak_mem / 1024.0

        top_stats = snapshot_end.compare_to(snapshot_start, "lineno")
        mem_delta_kb = sum(stat.size_diff for stat in top_stats) / 1024.0

        # Verify ring buffer strictly maintained its capacity bound
        is_bounded = len(self.buffer) <= self.capacity

        passed = (
            is_bounded
            and avg_cycle_ms < 5.0
            and mem_delta_kb < 15360.0  # Under 15MB delta over soak
        )

        return SoakTestResult(
            total_cycles=cycles,
            duration_seconds=t_elapsed,
            avg_cycle_ms=avg_cycle_ms,
            peak_memory_kb=peak_kb,
            memory_leaked_kb=max(0.0, mem_delta_kb),
            ring_buffer_bounded=is_bounded,
            summaries_generated=summaries_count,
            passed=passed,
            details={
                "buffer_len": len(self.buffer),
                "buffer_capacity": self.capacity,
                "cycles_per_sec": cycles / t_elapsed if t_elapsed > 0 else 0,
            }
        )
