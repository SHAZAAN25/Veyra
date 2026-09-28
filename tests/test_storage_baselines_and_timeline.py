"""
Tests for VEYRA Persistent Baselines and PC Timeline.
Verifies evolutionary updates, anti-contamination incident guards, quality progression,
and chronological PC Timeline storage.
"""
import os
import tempfile
import unittest

from analyzer.contracts import BaselineMetricSummary, BaselineQuality
from storage.contracts import ConfigurationChangeRecord
from storage.history.baseline_store import PersistentBaselineStore
from storage.history.timeline_store import PersistentTimelineStore
from storage.sqlite_engine import SqliteStorageEngine


class TestStorageBaselinesAndTimeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_baselines.sqlite")
        self.engine = SqliteStorageEngine(db_path=self.db_path)
        self.baseline_store = PersistentBaselineStore(self.engine)
        self.timeline_store = PersistentTimelineStore(self.engine)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_baseline_persistence_and_evolution(self):
        # 1. Initial sample
        s1 = self.baseline_store.update_baseline_sample("rtt_ms", 20.0)
        self.assertEqual(s1.sample_count, 1)
        self.assertEqual(s1.mean, 20.0)
        self.assertEqual(s1.quality, BaselineQuality.INSUFFICIENT_DATA)

        # 2. Evolutionary updates
        for _ in range(14):
            self.baseline_store.update_baseline_sample("rtt_ms", 22.0)

        s15 = self.baseline_store.get_baseline("rtt_ms")
        self.assertEqual(s15.sample_count, 15)
        self.assertEqual(s15.quality, BaselineQuality.LOW_CONFIDENCE)

        # 3. Further updates to establish
        for _ in range(40):
            self.baseline_store.update_baseline_sample("rtt_ms", 21.0)

        s_est = self.baseline_store.get_baseline("rtt_ms")
        self.assertGreaterEqual(s_est.sample_count, 50)
        self.assertEqual(s_est.quality, BaselineQuality.ESTABLISHED)

    def test_incident_guard_prevents_baseline_contamination(self):
        """CRITICAL: Anomalous measurements during active incidents must NOT alter the baseline."""
        # Establish baseline around 20ms
        for _ in range(20):
            self.baseline_store.update_baseline_sample("rtt_ms", 20.0)

        pre_incident = self.baseline_store.get_baseline("rtt_ms")
        self.assertEqual(pre_incident.mean, 20.0)
        sample_count_before = pre_incident.sample_count

        # Severe spike during active incident
        updated = self.baseline_store.update_baseline_sample("rtt_ms", 500.0, is_incident_active=True)
        self.assertEqual(updated.mean, 20.0)
        self.assertEqual(updated.sample_count, sample_count_before)

        # Verify from database
        persisted = self.baseline_store.get_baseline("rtt_ms")
        self.assertEqual(persisted.mean, 20.0)
        self.assertEqual(persisted.sample_count, sample_count_before)

    def test_pc_timeline_chronological_ordering(self):
        self.timeline_store.record_event(
            event_type="WIFI_DISCONNECT",
            summary="Wi-Fi interface disconnected",
            timestamp_utc="2026-09-28T12:00:00Z"
        )
        self.timeline_store.record_event(
            event_type="WIFI_RECONNECT",
            summary="Wi-Fi reconnected to HomeNet",
            timestamp_utc="2026-09-28T12:01:00Z"
        )

        events = self.timeline_store.query_timeline()
        self.assertEqual(len(events), 2)
        # Most recent first
        self.assertEqual(events[0].event_type, "WIFI_RECONNECT")
        self.assertEqual(events[1].event_type, "WIFI_DISCONNECT")

    def test_configuration_change_history(self):
        change = ConfigurationChangeRecord(
            change_id="CHG-001",
            category="WIFI",
            attribute_name="channel",
            old_value="6",
            new_value="36",
            detected_at_utc="2026-09-28T12:00:00Z",
            significance="NORMAL"
        )
        self.engine.save_configuration_change(change)
        changes = self.engine.query_configuration_changes(category="WIFI")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].old_value, "6")
        self.assertEqual(changes[0].new_value, "36")


if __name__ == "__main__":
    unittest.main()
