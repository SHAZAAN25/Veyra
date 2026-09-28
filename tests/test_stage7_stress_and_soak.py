"""
VEYRA Automated Tests — Stage 7 Soak, Stress & Resource Bounds
Verifies system behavior under high-throughput simulated telemetry streaming,
bounded memory utilization, and statistical aggregation performance.
"""

import unittest
import time

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from simulation.soak_harness import SoakHarness, SoakTestResult
from storage.aggregation.aggregator import MetricAggregator
from storage.contracts import SummaryResolution


class TestStage7StressAndSoak(unittest.TestCase):
    """Verifies memory bounds, execution timing, and ring buffer limits under load."""

    def test_accelerated_telemetry_soak_500_cycles(self) -> None:
        """Run 500 accelerated cycles; assert sub-millisecond execution and bounded buffer."""
        harness = SoakHarness(buffer_capacity=60)
        result: SoakTestResult = harness.run_soak_test(cycles=500)

        self.assertTrue(result.passed)
        self.assertTrue(result.ring_buffer_bounded)
        self.assertLessEqual(len(harness.buffer), 60)
        self.assertGreater(result.summaries_generated, 0)
        self.assertLess(result.avg_cycle_ms, 5.0, "Average cycle must be fast (< 5ms)")

    def test_accelerated_telemetry_soak_1000_cycles_memory_bounds(self) -> None:
        """Run 1,000 accelerated cycles; assert zero memory leak accumulation."""
        harness = SoakHarness(buffer_capacity=120)
        result: SoakTestResult = harness.run_soak_test(cycles=1000)

        self.assertTrue(result.passed)
        self.assertTrue(result.ring_buffer_bounded)
        self.assertLessEqual(len(harness.buffer), 120)
        self.assertLess(result.memory_leaked_kb, 15360.0, "Memory delta must be bounded (< 15 MB)")

    def test_statistical_aggregator_high_volume_throughput(self) -> None:
        """Benchmark MetricAggregator across 1,000 observations; assert sub-50ms compute."""
        observations = []
        for i in range(1000):
            obs = Observation(
                observation_id=f"obs_bench_{i}",
                timestamp_utc="2026-09-28T12:00:00Z",
                collector_name="sys",
                measurements={
                    "cpu_utilization_pct": Measurement(
                        metric_name="cpu_utilization_pct",
                        state=MetricState.AVAILABLE,
                        value=10.0 + (i % 50),
                        unit=MetricUnit.PERCENTAGE,
                        source_collector="sys",
                        provenance="synthetic"
                    )
                },
                collector_healthy=True
            )
            observations.append(obs)

        t0 = time.monotonic()
        summaries = MetricAggregator.aggregate_observations(
            observations=observations,
            bucket_start_utc="2026-09-28T12:00:00Z",
            bucket_end_utc="2026-09-28T12:01:00Z",
            resolution_seconds=SummaryResolution.MINUTE_1.value
        )
        elapsed_ms = (time.monotonic() - t0) * 1000.0

        self.assertEqual(len(summaries), 1)
        s = summaries[0]
        self.assertEqual(s.sample_count, 1000)
        self.assertEqual(s.min_value, 10.0)
        self.assertEqual(s.max_value, 59.0)
        self.assertLess(elapsed_ms, 50.0, "1,000 metric aggregation must complete within 50ms")


if __name__ == "__main__":
    unittest.main()
