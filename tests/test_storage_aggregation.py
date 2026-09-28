"""
Tests for VEYRA Metric Aggregation Engine.
Verifies statistical accuracy, non-fabrication of missing data, and data quality states.
"""
import unittest

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from storage.contracts import DataQuality, SummaryResolution
from storage.aggregation.aggregator import MetricAggregator


class TestStorageAggregation(unittest.TestCase):
    def test_statistical_aggregation_accuracy(self):
        """Verifies min, max, mean, median, and p95 calculations over real measurements."""
        values = [10.0, 12.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 80.0, 100.0]
        observations = []
        for i, val in enumerate(values):
            obs = Observation(
                observation_id=f"obs-{i}",
                timestamp_utc="2026-09-28T12:00:00Z",
                collector_name="test_col",
                measurements={
                    "network_rtt_ms": Measurement(
                        metric_name="network_rtt_ms",
                        state=MetricState.AVAILABLE,
                        value=val,
                        unit=MetricUnit.MILLISECONDS,
                        source_collector="ping",
                        provenance="test"
                    )
                },
                collector_healthy=True
            )
            observations.append(obs)

        summaries = MetricAggregator.aggregate_observations(
            observations=observations,
            bucket_start_utc="2026-09-28T12:00:00Z",
            bucket_end_utc="2026-09-28T12:01:00Z",
            resolution_seconds=SummaryResolution.MINUTE_1.value
        )

        self.assertEqual(len(summaries), 1)
        s = summaries[0]
        self.assertEqual(s.metric_name, "network_rtt_ms")
        self.assertEqual(s.sample_count, 10)
        self.assertEqual(s.min_value, 10.0)
        self.assertEqual(s.max_value, 100.0)
        self.assertEqual(s.mean_value, 38.2)
        self.assertEqual(s.median_value, 27.5)
        self.assertEqual(s.data_quality, DataQuality.VALID)

    def test_unavailable_measurements_never_become_zero(self):
        """CRITICAL: Enforces that missing or unavailable data is NOT converted to 0.0."""
        obs = Observation(
            observation_id="obs-unavail",
            timestamp_utc="2026-09-28T12:00:00Z",
            collector_name="ping",
            measurements={
                "network_packet_loss_pct": Measurement(
                    metric_name="network_packet_loss_pct",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.PERCENTAGE,
                    source_collector="ping",
                    provenance="timeout"
                )
            },
            collector_healthy=False
        )

        summaries = MetricAggregator.aggregate_observations(
            observations=[obs],
            bucket_start_utc="2026-09-28T12:00:00Z",
            bucket_end_utc="2026-09-28T12:01:00Z"
        )

        self.assertEqual(len(summaries), 1)
        s = summaries[0]
        self.assertEqual(s.data_quality, DataQuality.UNAVAILABLE)
        self.assertIsNone(s.mean_value)
        self.assertIsNone(s.min_value)
        self.assertIsNone(s.max_value)
        self.assertEqual(s.unavailable_count, 1)

    def test_zero_percent_packet_loss_is_real_measurement(self):
        """Verifies that genuine 0.0% packet loss is preserved as 0.0 and VALID."""
        obs = Observation(
            observation_id="obs-zero-loss",
            timestamp_utc="2026-09-28T12:00:00Z",
            collector_name="ping",
            measurements={
                "network_packet_loss_pct": Measurement(
                    metric_name="network_packet_loss_pct",
                    state=MetricState.AVAILABLE,
                    value=0.0,
                    unit=MetricUnit.PERCENTAGE,
                    source_collector="ping",
                    provenance="icmp"
                )
            },
            collector_healthy=True
        )

        summaries = MetricAggregator.aggregate_observations(
            observations=[obs],
            bucket_start_utc="2026-09-28T12:00:00Z",
            bucket_end_utc="2026-09-28T12:01:00Z"
        )

        self.assertEqual(len(summaries), 1)
        s = summaries[0]
        self.assertEqual(s.mean_value, 0.0)
        self.assertEqual(s.min_value, 0.0)
        self.assertEqual(s.max_value, 0.0)
        self.assertEqual(s.unavailable_count, 0)
        self.assertEqual(s.data_quality, DataQuality.VALID)


if __name__ == "__main__":
    unittest.main()
