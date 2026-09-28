"""
Tests for VEYRA Incident Detection, Lifecycle State Machine, Hysteresis, and Grouping.
"""
import unittest

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from analyzer.contracts import IncidentType, IncidentSeverity, IncidentStatus
from analyzer.thresholds import DetectionThresholds, MetricHysteresisThreshold
from analyzer.incidents.lifecycle import IncidentTracker
from analyzer.incidents.detector import DeterministicIncidentDetector
from analyzer.incidents.grouping import IncidentCorrelator


class TestIncidentDetection(unittest.TestCase):
    def test_hysteresis_avoids_alert_flapping(self):
        # Trigger at 100, recover at 60
        threshold = MetricHysteresisThreshold(trigger_value=100.0, recovery_value=60.0, min_consecutive_triggers=1, min_consecutive_recoveries=1)
        tracker = IncidentTracker(IncidentType.LATENCY_SPIKE, IncidentSeverity.WARNING, threshold, cooldown_seconds=0.0)

        # 1. Normal latency (50ms) -> No incident
        self.assertIsNone(tracker.evaluate_metric(50.0, "latency", ["LAYER_4"]))

        # 2. Latency spikes to 120ms -> Incident TRIGGERED
        inc = tracker.evaluate_metric(120.0, "latency", ["LAYER_4"])
        self.assertIsNotNone(inc)
        self.assertEqual(inc.status, IncidentStatus.ACTIVE)

        # 3. Latency drops to 80ms (Between trigger 100 and recovery 60) -> Stays ACTIVE (Hysteresis!)
        inc2 = tracker.evaluate_metric(80.0, "latency", ["LAYER_4"])
        self.assertIsNotNone(inc2)
        self.assertEqual(inc2.status, IncidentStatus.ACTIVE)

        # 4. Latency drops to 55ms (Below recovery threshold 60ms) -> Incident RECOVERED
        inc3 = tracker.evaluate_metric(55.0, "latency", ["LAYER_4"])
        self.assertIsNotNone(inc3)
        self.assertEqual(inc3.status, IncidentStatus.RECOVERED)
        self.assertEqual(inc3.recovery_value, 55.0)

    def test_detector_detects_wifi_disconnect_and_reconnect(self):
        detector = DeterministicIncidentDetector()

        # Helper to construct minimal wifi observation
        def make_wifi_obs(connected: bool) -> Observation:
            return Observation(
                observation_id="test_obs",
                timestamp_utc="2026-09-28T00:00:00Z",
                collector_name="wifi",
                measurements={
                    "wifi_connected": Measurement(
                        metric_name="wifi_connected",
                        state=MetricState.AVAILABLE,
                        value=connected,
                        unit=MetricUnit.BOOLEAN,
                        source_collector="wifi",
                        provenance="test"
                    )
                },
                collector_healthy=True
            )

        # Baseline: Connected=True
        detector.evaluate_observations({"wifi": make_wifi_obs(True)})

        # Disconnect event
        incidents = detector.evaluate_observations({"wifi": make_wifi_obs(False)})
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].incident_type, IncidentType.WIFI_DISCONNECT)
        self.assertEqual(incidents[0].severity, IncidentSeverity.CRITICAL)

        # Reconnect event
        reconnect_incs = detector.evaluate_observations({"wifi": make_wifi_obs(True)})
        self.assertEqual(len(reconnect_incs), 1)
        self.assertEqual(reconnect_incs[0].incident_type, IncidentType.WIFI_RECONNECT)
        self.assertEqual(reconnect_incs[0].status, IncidentStatus.RECOVERED)

    def test_incident_grouping_correlation_id(self):
        correlator = IncidentCorrelator(grouping_window_seconds=10.0)
        threshold = MetricHysteresisThreshold(trigger_value=10.0, recovery_value=2.0)
        t1 = IncidentTracker(IncidentType.PACKET_LOSS_SPIKE, IncidentSeverity.HIGH, threshold)
        t2 = IncidentTracker(IncidentType.LATENCY_SPIKE, IncidentSeverity.WARNING, threshold)

        inc1 = t1.evaluate_metric(15.0, "loss", ["LAYER_4"])
        inc2 = t2.evaluate_metric(25.0, "latency", ["LAYER_4"])

        correlated = correlator.correlate([inc1, inc2])
        self.assertEqual(len(correlated), 2)
        # Both incidents must share the same correlation ID
        self.assertEqual(correlated[0].correlation_id, correlated[1].correlation_id)
        self.assertTrue(correlated[0].correlation_id.startswith("corr_"))


if __name__ == "__main__":
    unittest.main()
