"""
Tests for VEYRA Master StorageEngine Facade.
Verifies unified lifecycle orchestration: ephemeral RAM buffer, summary flushes,
compaction triggers, and BaseStorageEngine protocol compliance.
"""
import os
import tempfile
import unittest

from app.core.config import StorageConfig
from app.core.contracts import HistoricalSummary, Incident, Observation, Measurement, MetricState, MetricUnit
from storage.engine import StorageEngine


class TestStorageFacade(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_facade.sqlite")
        self.config = StorageConfig(max_storage_size_mb=25)
        self.facade = StorageEngine(db_path=self.db_path, config=self.config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_buffer_flush_to_sqlite_summaries(self):
        # 1. Append observations into RAM buffer
        for i in range(10):
            obs = Observation(
                observation_id=f"obs-{i}",
                timestamp_utc="2026-09-28T12:00:00Z",
                collector_name="sys",
                measurements={
                    "cpu_utilization_pct": Measurement(
                        metric_name="cpu_utilization_pct",
                        state=MetricState.AVAILABLE,
                        value=20.0 + i,
                        unit=MetricUnit.PERCENTAGE,
                        source_collector="sys",
                        provenance="psutil"
                    )
                },
                collector_healthy=True
            )
            self.facade.append_raw_observation(obs)

        # 2. Flush buffer into SQLite summaries
        summaries = self.facade.flush_buffer_to_summaries(
            bucket_start_utc="2026-09-28T12:00:00Z",
            bucket_end_utc="2026-09-28T12:01:00Z",
            clear_buffer=True
        )

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].sample_count, 10)
        self.assertEqual(summaries[0].min_value, 20.0)
        self.assertEqual(summaries[0].max_value, 29.0)

        # Buffer should be cleared
        self.assertEqual(len(self.facade.sqlite.get_buffered_observations()), 0)

        # Query via BaseStorageEngine protocol
        hist_summaries = self.facade.query_summaries(
            metric_name="cpu_utilization_pct",
            start_utc="2026-09-28T11:59:00Z",
            end_utc="2026-09-28T12:02:00Z",
            bucket_size_minutes=1
        )
        self.assertEqual(len(hist_summaries), 1)
        self.assertEqual(hist_summaries[0].count, 10)

    def test_base_storage_engine_incident_protocol(self):
        inc = Incident(
            incident_id="INC-COMPAT-001",
            domain="NETWORK",
            severity="CRITICAL",
            summary="Gateway failure detected",
            start_time_utc="2026-09-28T12:00:00Z",
            end_time_utc="2026-09-28T12:05:00Z",
            root_cause_analysis="Gateway ICMP timeout"
        )
        self.facade.persist_incident(inc)
        restored_list = self.facade.query_incidents(limit=10)
        self.assertEqual(len(restored_list), 1)
        self.assertEqual(restored_list[0].incident_id, "INC-COMPAT-001")
        self.assertEqual(restored_list[0].severity, "CRITICAL")

    def test_facade_stats_reporting(self):
        stats = self.facade.get_stats()
        self.assertGreater(stats.db_size_bytes, 0)
        self.assertEqual(stats.max_size_bytes, 25 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
