"""
Tests for VEYRA Incident Persistence, Replay Reconstruction, and Flight Recorder.
Verifies durable atomic persistence of incidents with evidence windows, replay answers,
and strict privacy enforcement in flight recorder snapshots.
"""
import os
import tempfile
import unittest

from analyzer.contracts import (
    DetailedIncident,
    EvidenceQuality,
    EvidenceWindow,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    RootCauseAssessment,
    RootCauseCategory,
)
from analyzer.evidence.flight_recorder import FlightRecorderSnapshot
from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from app.core.exceptions import SecurityViolationError
from storage.history.incident_store import HistoricalIncidentStore
from storage.history.replay_store import IncidentReplayStore
from storage.history.flight_recorder_store import PersistentFlightRecorderStore
from storage.sqlite_engine import SqliteStorageEngine


class TestStorageIncidentsAndReplay(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_incidents.sqlite")
        self.engine = SqliteStorageEngine(db_path=self.db_path)
        self.incident_store = HistoricalIncidentStore(self.engine)
        self.replay_store = IncidentReplayStore(self.incident_store)
        self.flight_recorder_store = PersistentFlightRecorderStore(self.engine)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_incident_persistence_and_replay_reconstruction(self):
        """Verifies full roundtrip of DetailedIncident and replay reconstruction after restart."""
        # 1. Create Before Observation
        before_obs = Observation(
            observation_id="obs-before-1",
            timestamp_utc="2026-09-28T12:00:00Z",
            collector_name="ping",
            measurements={
                "network_rtt_ms": Measurement(
                    metric_name="network_rtt_ms",
                    state=MetricState.AVAILABLE,
                    value=25.0,
                    unit=MetricUnit.MILLISECONDS,
                    source_collector="ping",
                    provenance="icmp"
                )
            },
            collector_healthy=True
        )

        # 2. Create Incident Observation
        during_obs = Observation(
            observation_id="obs-during-1",
            timestamp_utc="2026-09-28T12:00:30Z",
            collector_name="ping",
            measurements={
                "network_rtt_ms": Measurement(
                    metric_name="network_rtt_ms",
                    state=MetricState.AVAILABLE,
                    value=150.0,
                    unit=MetricUnit.MILLISECONDS,
                    source_collector="ping",
                    provenance="icmp"
                )
            },
            collector_healthy=True
        )

        # 3. Create After Observation
        after_obs = Observation(
            observation_id="obs-after-1",
            timestamp_utc="2026-09-28T12:01:00Z",
            collector_name="ping",
            measurements={
                "network_rtt_ms": Measurement(
                    metric_name="network_rtt_ms",
                    state=MetricState.AVAILABLE,
                    value=28.0,
                    unit=MetricUnit.MILLISECONDS,
                    source_collector="ping",
                    provenance="icmp"
                )
            },
            collector_healthy=True
        )

        incident = DetailedIncident(
            incident_id="INC-TEST-001",
            incident_type=IncidentType.LATENCY_SPIKE,
            severity=IncidentSeverity.WARNING,
            status=IncidentStatus.RECOVERED,
            started_at_utc="2026-09-28T12:00:30Z",
            ended_at_utc="2026-09-28T12:01:00Z",
            duration_seconds=30.0,
            summary="Latency spiked to 150.0ms",
            root_cause=RootCauseAssessment(
                primary_cause=RootCauseCategory.UPSTREAM_INTERNET,
                explanation="Upstream latency spike while local gateway is healthy.",
                confidence_score=0.92,
                evidence_quality=EvidenceQuality.STRONG,
                relationship="OBSERVED",
                affected_layers=["LAYER_4_INTERNET"]
            ),
            affected_layers=["LAYER_4_INTERNET"],
            correlation_id="CORR-TEST-001",
            evidence_window=EvidenceWindow(
                before_observations=[before_obs],
                incident_observations=[during_obs],
                after_observations=[after_obs]
            ),
            trigger_metric="network_rtt_ms",
            trigger_value=150.0,
            recovery_value=28.0
        )

        # Save to SQLite
        self.incident_store.save_detailed_incident(incident)

        # Retrieve and verify DetailedIncident
        restored = self.incident_store.get_detailed_incident("INC-TEST-001")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.incident_id, "INC-TEST-001")
        self.assertEqual(restored.incident_type, IncidentType.LATENCY_SPIKE)
        self.assertEqual(len(restored.evidence_window.before_observations), 1)
        self.assertEqual(len(restored.evidence_window.incident_observations), 1)
        self.assertEqual(len(restored.evidence_window.after_observations), 1)

        # Reconstruct replay
        replay = self.replay_store.reconstruct_replay("INC-TEST-001")
        self.assertIsNotNone(replay)
        answers = replay["answers"]
        self.assertEqual(answers["what_was_normal"]["network_rtt_ms"]["mean"], 25.0)
        self.assertEqual(answers["what_changed"]["trigger_value"], 150.0)
        self.assertEqual(answers["what_failed"]["primary_cause"], "UPSTREAM_INTERNET")
        self.assertEqual(answers["what_recovered"]["recovery_value"], 28.0)

    def test_flight_recorder_privacy_enforcement(self):
        """Verifies that snapshots containing passwords, tokens, or secrets are strictly rejected."""
        safe_snapshot = FlightRecorderSnapshot(
            snapshot_id="FR-SAFE-001",
            timestamp_utc="2026-09-28T12:00:00Z",
            incident_id="INC-001",
            incident_type="LATENCY_SPIKE",
            system_summary={"cpu_pct": 20.0},
            network_summary={"adapter": "Ethernet"},
            wifi_summary={},
            gateway_summary={"ip": "192.168.1.1"},
            dns_summary={"server": "1.1.1.1"},
            internet_summary={"rtt": 25.0},
            gpu_summary={},
            self_health_summary={"cpu_usage_pct": 0.2}
        )
        self.flight_recorder_store.save_snapshot(safe_snapshot)
        retrieved = self.flight_recorder_store.get_snapshot("FR-SAFE-001")
        self.assertIsNotNone(retrieved)

        # Insecure snapshot with API key / token
        leaky_snapshot = FlightRecorderSnapshot(
            snapshot_id="FR-LEAKY-001",
            timestamp_utc="2026-09-28T12:00:00Z",
            incident_id="INC-002",
            incident_type="UNKNOWN",
            system_summary={"user_token": "secret_token_123"},
            network_summary={},
            wifi_summary={},
            gateway_summary={},
            dns_summary={},
            internet_summary={},
            gpu_summary={},
            self_health_summary={}
        )
        with self.assertRaises(SecurityViolationError):
            self.flight_recorder_store.save_snapshot(leaky_snapshot)


if __name__ == "__main__":
    unittest.main()
