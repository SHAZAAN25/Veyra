"""
Tests for VEYRA Hardware Bottleneck Investigator.
"""
import unittest

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from analyzer.bottleneck.investigator import BottleneckInvestigator


class TestBottleneckInvestigator(unittest.TestCase):
    def setUp(self):
        self.investigator = BottleneckInvestigator()

    def test_ram_bottleneck_candidate_observed(self):
        obs = {
            "memory": Observation(
                observation_id="obs_mem",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="memory",
                measurements={"ram_utilization_pct": Measurement("ram_utilization_pct", MetricState.AVAILABLE, 95.0, MetricUnit.PERCENTAGE, "mem", "test")},
                collector_healthy=True
            )
        }
        candidates = self.investigator.investigate(obs)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].component, "RAM")
        self.assertEqual(candidates[0].classification, "OBSERVED")
        self.assertGreaterEqual(candidates[0].confidence, 0.8)

    def test_cpu_bottleneck_inferred_with_low_gpu(self):
        obs = {
            "cpu": Observation(
                observation_id="obs_cpu",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="cpu",
                measurements={"cpu_utilization_pct": Measurement("cpu_utilization_pct", MetricState.AVAILABLE, 94.0, MetricUnit.PERCENTAGE, "cpu", "test")},
                collector_healthy=True
            ),
            "gpu": Observation(
                observation_id="obs_gpu",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="gpu",
                measurements={
                    "gpu_utilization_pct": Measurement("gpu_utilization_pct", MetricState.AVAILABLE, 25.0, MetricUnit.PERCENTAGE, "gpu", "test")
                },
                collector_healthy=True
            )
        }
        candidates = self.investigator.investigate(obs)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].component, "CPU")
        self.assertEqual(candidates[0].classification, "INFERRED")
        self.assertIn("suggests CPU execution bottleneck", candidates[0].rationale)

    def test_balanced_workload_no_bottlenecks(self):
        obs = {
            "cpu": Observation("obs_cpu", "2026-09-28T00:00:00Z", "cpu", {"cpu_utilization_pct": Measurement("cpu_utilization_pct", MetricState.AVAILABLE, 35.0, MetricUnit.PERCENTAGE, "cpu", "test")}, True),
            "memory": Observation("obs_mem", "2026-09-28T00:00:00Z", "mem", {"ram_utilization_pct": Measurement("ram_utilization_pct", MetricState.AVAILABLE, 50.0, MetricUnit.PERCENTAGE, "mem", "test")}, True),
            "gpu": Observation("obs_gpu", "2026-09-28T00:00:00Z", "gpu", {"gpu_utilization_pct": Measurement("gpu_utilization_pct", MetricState.AVAILABLE, 60.0, MetricUnit.PERCENTAGE, "gpu", "test")}, True)
        }
        candidates = self.investigator.investigate(obs)
        self.assertEqual(len(candidates), 0)


if __name__ == "__main__":
    unittest.main()
