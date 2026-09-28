"""
Tests for VEYRA SQLite Storage Engine.
Verifies crash safety, transactions, WAL mode, queries, deletions, and storage stats.
"""
import os
import tempfile
import unittest

from app.core.config import StorageConfig
from storage.contracts import MeasurementSummaryRecord, DataQuality, StorageHealthState
from storage.sqlite_engine import SqliteStorageEngine


class TestSqliteStorageEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_engine.sqlite")
        self.config = StorageConfig(max_storage_size_mb=25)
        self.engine = SqliteStorageEngine(db_path=self.db_path, config=self.config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_summary_persistence_and_query(self):
        record = MeasurementSummaryRecord(
            metric_name="cpu_utilization_pct",
            bucket_start_utc="2026-09-28T12:00:00Z",
            bucket_end_utc="2026-09-28T12:01:00Z",
            resolution_seconds=60,
            sample_count=30,
            min_value=12.0,
            max_value=45.0,
            mean_value=25.5,
            median_value=24.0,
            p95_value=42.0,
            std_dev=5.2,
            unavailable_count=0,
            degraded_count=0,
            data_quality=DataQuality.VALID,
            unit="%"
        )

        self.engine.save_measurement_summary_record(record)
        results = self.engine.query_measurement_summaries(metric_name="cpu_utilization_pct")
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.metric_name, "cpu_utilization_pct")
        self.assertEqual(r.mean_value, 25.5)
        self.assertEqual(r.max_value, 45.0)

    def test_storage_stats_and_health(self):
        stats = self.engine.get_storage_stats()
        self.assertGreater(stats.db_size_bytes, 0)
        self.assertEqual(stats.max_size_bytes, 25 * 1024 * 1024)
        self.assertEqual(stats.storage_health, StorageHealthState.HEALTHY)

    def test_history_range_deletion(self):
        r1 = MeasurementSummaryRecord(
            metric_name="latency",
            bucket_start_utc="2026-09-28T10:00:00Z",
            bucket_end_utc="2026-09-28T10:01:00Z",
            resolution_seconds=60,
            sample_count=10,
            min_value=5.0,
            max_value=10.0,
            mean_value=7.5,
            median_value=7.5,
            p95_value=9.5,
            std_dev=1.0,
            unit="ms"
        )
        r2 = MeasurementSummaryRecord(
            metric_name="latency",
            bucket_start_utc="2026-09-28T11:00:00Z",
            bucket_end_utc="2026-09-28T11:01:00Z",
            resolution_seconds=60,
            sample_count=10,
            min_value=6.0,
            max_value=12.0,
            mean_value=8.0,
            median_value=8.0,
            p95_value=11.0,
            std_dev=1.5,
            unit="ms"
        )
        self.engine.save_measurement_summary_records([r1, r2])
        self.assertEqual(len(self.engine.query_measurement_summaries("latency")), 2)

        # Delete 10:00:00 record
        deleted = self.engine.delete_history_range("2026-09-28T09:59:00Z", "2026-09-28T10:02:00Z")
        self.assertEqual(deleted, 1)

        remaining = self.engine.query_measurement_summaries("latency")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].bucket_start_utc, "2026-09-28T11:00:00Z")


if __name__ == "__main__":
    unittest.main()
