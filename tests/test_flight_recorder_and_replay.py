"""
Tests for VEYRA PC Health Flight Recorder and Incident Replay Engine.
"""
import unittest

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from analyzer.contracts import DetailedIncident, IncidentType, IncidentSeverity, IncidentStatus, EvidenceWindow
from analyzer.evidence.flight_recorder import FlightRecorder
from analyzer.evidence.replay import IncidentReplayEngine


class TestFlightRecorderAndReplay(unittest.TestCase):
    def test_flight_recorder_snapshot_privacy_and_structure(self):
        recorder = FlightRecorder()
        obs = {
            "cpu": Observation("obs_cpu", "2026-09-28T00:00:00Z", "cpu", {"cpu_utilization_pct": Measurement("cpu_utilization_pct", MetricState.AVAILABLE, 22.5, MetricUnit.PERCENTAGE, "cpu", "test")}, True),
            "wifi": Observation("obs_wf", "2026-09-28T00:00:00Z", "wifi", {"wifi_ssid": Measurement("wifi_ssid", MetricState.AVAILABLE, "Veyra_Secure", MetricUnit.STRING, "wifi", "test")}, True)
        }

        incident = DetailedIncident(
            incident_id="inc_test_99",
            incident_type=IncidentType.LATENCY_SPIKE,
            severity=IncidentSeverity.WARNING,
            status=IncidentStatus.ACTIVE,
            started_at_utc="2026-09-28T00:00:00Z"
        )

        snapshot = recorder.create_snapshot("snap_01", obs, incident)
        self.assertEqual(snapshot.snapshot_id, "snap_01")
        self.assertEqual(snapshot.incident_id, "inc_test_99")
        self.assertIn("cpu_utilization_pct", snapshot.system_summary)
        self.assertIn("wifi_ssid", snapshot.wifi_summary)

        # STRICT PRIVACY CHECK: Verify no sensitive keys exist
        raw_repr = str(snapshot.__dict__)
        self.assertNotIn("password", raw_repr.lower())
        self.assertNotIn("token", raw_repr.lower())
        self.assertNotIn("bearer", raw_repr.lower())

    def test_incident_replay_chronological_answers(self):
        replay_engine = IncidentReplayEngine()

        before_obs = [
            Observation("b1", "2026-09-28T00:00:00Z", "ping", {"latency": Measurement("latency", MetricState.AVAILABLE, 20.0, MetricUnit.MILLISECONDS, "p", "t")}, True),
            Observation("b2", "2026-09-28T00:00:01Z", "ping", {"latency": Measurement("latency", MetricState.AVAILABLE, 22.0, MetricUnit.MILLISECONDS, "p", "t")}, True)
        ]
        during_obs = [
            Observation("d1", "2026-09-28T00:00:02Z", "ping", {"latency": Measurement("latency", MetricState.AVAILABLE, 140.0, MetricUnit.MILLISECONDS, "p", "t")}, False)
        ]

        incident = DetailedIncident(
            incident_id="inc_replay_01",
            incident_type=IncidentType.LATENCY_SPIKE,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.RECOVERED,
            started_at_utc="2026-09-28T00:00:02Z",
            ended_at_utc="2026-09-28T00:00:15Z",
            trigger_metric="latency",
            trigger_value=140.0,
            recovery_value=35.0,
            affected_layers=["LAYER_4_INTERNET"],
            evidence_window=EvidenceWindow(before_observations=before_obs, incident_observations=during_obs)
        )

        replay = replay_engine.generate_replay(incident)
        self.assertEqual(replay.incident_id, "inc_replay_01")
        # 1. What was normal? (Average of before observations: 21.0)
        self.assertEqual(replay.what_was_normal.get("latency"), 21.0)
        # 2. What changed?
        self.assertIn("140.0", replay.what_changed)
        # 3. What failed?
        self.assertIn("LAYER_4_INTERNET", replay.what_failed)
        # 4. What recovered?
        self.assertTrue(any("recovered to 35.0" in r for r in replay.what_recovered))
        # 5. Timeline phases
        self.assertEqual(len(replay.timeline_phases), 3)


if __name__ == "__main__":
    unittest.main()
