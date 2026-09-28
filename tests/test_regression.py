"""
Tests for VEYRA Performance Regression Detector.
"""
import unittest

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from analyzer.baseline.personal_baseline import PersonalBaselineEngine
from analyzer.regression.detector import RegressionDetector


class TestRegressionDetection(unittest.TestCase):
    def test_regression_insufficient_samples_does_not_fire(self):
        baseline = PersonalBaselineEngine(min_samples_for_baseline=15)
        detector = RegressionDetector(baseline, regression_threshold_pct=40.0)

        # Baseline only has 3 samples
        for i in range(3):
            obs = Observation(
                observation_id=f"obs_{i}",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="ping",
                measurements={"internet_latency_rtt_ms": Measurement("internet_latency_rtt_ms", MetricState.AVAILABLE, 25.0, MetricUnit.MILLISECONDS, "ping", "test")},
                collector_healthy=True
            )
            baseline.record_observation(obs)

        # Current observations have 80ms (high latency), but baseline is insufficient
        current_obs = [
            Observation(
                observation_id="curr_1",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="ping",
                measurements={"internet_latency_rtt_ms": Measurement("internet_latency_rtt_ms", MetricState.AVAILABLE, 80.0, MetricUnit.MILLISECONDS, "ping", "test")},
                collector_healthy=True
            )
        ]

        reg = detector.evaluate_regression(current_obs, "internet_latency_rtt_ms")
        self.assertFalse(reg.is_significant)
        self.assertIn("Insufficient baseline", reg.explanation)

    def test_genuine_regression_detected(self):
        baseline = PersonalBaselineEngine(min_samples_for_baseline=15)
        detector = RegressionDetector(baseline, regression_threshold_pct=40.0)

        # Populate established baseline: 25ms average over 25 samples
        for i in range(25):
            obs = Observation(
                observation_id=f"obs_{i}",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="ping",
                measurements={"internet_latency_rtt_ms": Measurement("internet_latency_rtt_ms", MetricState.AVAILABLE, 25.0, MetricUnit.MILLISECONDS, "ping", "test")},
                collector_healthy=True
            )
            baseline.record_observation(obs)

        # Current observations average 50ms (+100% degradation)
        current_obs = [
            Observation(
                observation_id=f"curr_{i}",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="ping",
                measurements={"internet_latency_rtt_ms": Measurement("internet_latency_rtt_ms", MetricState.AVAILABLE, 50.0, MetricUnit.MILLISECONDS, "ping", "test")},
                collector_healthy=True
            )
            for i in range(5)
        ]

        reg = detector.evaluate_regression(current_obs, "internet_latency_rtt_ms")
        self.assertTrue(reg.is_significant)
        self.assertAlmostEqual(reg.percentage_degradation, 100.0, places=1)
        self.assertGreater(reg.confidence, 0.6)
        self.assertIn("degraded by 100.0%", reg.explanation)


if __name__ == "__main__":
    unittest.main()
