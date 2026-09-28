"""
Tests for VEYRA Personal PC Baseline Engine.
"""
import unittest

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from analyzer.contracts import BaselineQuality
from analyzer.baseline.personal_baseline import PersonalBaselineEngine


class TestPersonalBaseline(unittest.TestCase):
    def test_baseline_insufficient_samples(self):
        engine = PersonalBaselineEngine(min_samples_for_baseline=15)
        # Record only 5 observations
        for i in range(5):
            obs = Observation(
                observation_id=f"obs_{i}",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="ping",
                measurements={
                    "latency": Measurement(
                        metric_name="latency",
                        state=MetricState.AVAILABLE,
                        value=20.0 + i,
                        unit=MetricUnit.MILLISECONDS,
                        source_collector="ping",
                        provenance="test"
                    )
                },
                collector_healthy=True
            )
            engine.record_observation(obs)

        baseline = engine.get_baseline("latency")
        self.assertEqual(baseline.quality, BaselineQuality.INSUFFICIENT_DATA)
        self.assertEqual(baseline.sample_count, 5)

    def test_baseline_established_statistics(self):
        engine = PersonalBaselineEngine(min_samples_for_baseline=15)
        # Record 35 observations with known values: 20ms baseline with small variations
        for i in range(35):
            val = 20.0 if i % 2 == 0 else 22.0
            obs = Observation(
                observation_id=f"obs_{i}",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="ping",
                measurements={
                    "latency": Measurement(
                        metric_name="latency",
                        state=MetricState.AVAILABLE,
                        value=val,
                        unit=MetricUnit.MILLISECONDS,
                        source_collector="ping",
                        provenance="test"
                    )
                },
                collector_healthy=True
            )
            engine.record_observation(obs)

        baseline = engine.get_baseline("latency")
        self.assertEqual(baseline.quality, BaselineQuality.ESTABLISHED)
        self.assertEqual(baseline.sample_count, 35)
        self.assertAlmostEqual(baseline.mean, 20.97, places=1)
        self.assertEqual(baseline.min_value, 20.0)
        self.assertEqual(baseline.max_value, 22.0)
        self.assertGreater(baseline.std_dev, 0.0)

    def test_baseline_deviation_evaluation(self):
        engine = PersonalBaselineEngine(min_samples_for_baseline=10)
        for i in range(20):
            obs = Observation(
                observation_id=f"obs_{i}",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="ping",
                measurements={
                    "ping": Measurement(
                        metric_name="ping",
                        state=MetricState.AVAILABLE,
                        value=20.0,
                        unit=MetricUnit.MILLISECONDS,
                        source_collector="ping",
                        provenance="test"
                    )
                },
                collector_healthy=True
            )
            engine.record_observation(obs)

        # Value of 22ms is normal
        ratio, abnormal = engine.evaluate_deviation("ping", 22.0)
        self.assertFalse(abnormal)

        # Value of 60ms is 3x baseline -> abnormal!
        ratio2, abnormal2 = engine.evaluate_deviation("ping", 60.0)
        self.assertTrue(abnormal2)
        self.assertEqual(ratio2, 3.0)


if __name__ == "__main__":
    unittest.main()
