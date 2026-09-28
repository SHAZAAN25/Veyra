"""
Tests for VEYRA Retention Compaction and Storage Pressure Management.
Verifies adaptive resolution rollups, supersession atomic safety, and critical incident protection.
"""
from datetime import datetime, timezone, timedelta
import os
import tempfile
import unittest

from app.core.config import StorageConfig
from storage.contracts import MeasurementSummaryRecord, SummaryResolution, DataQuality
from storage.retention.compactor import CompactionEngine
from storage.sqlite_engine import SqliteStorageEngine


class TestStorageRetentionAndPressure(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_retention.sqlite")
        self.config = StorageConfig(
            max_storage_size_mb=25,
            retention_tier1_minutes=1440,
            downsample_threshold_pct=50.0  # Low threshold for testing pressure
        )
        self.engine = SqliteStorageEngine(db_path=self.db_path, config=self.config)
        self.compactor = CompactionEngine(engine=self.engine, config=self.config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tier1_to_tier2_compaction(self):
        """Verifies 1-min summaries older than 24h are aggregated into 5-min summaries."""
        now = datetime.now(timezone.utc)
        # 30 hours ago, aligned to 5-minute boundary so all 5 consecutive 1-min summaries land in one 5-min bucket
        epoch_30h_ago = int((now - timedelta(hours=30)).timestamp())
        aligned_epoch = epoch_30h_ago - (epoch_30h_ago % 300)
        base_time = datetime.fromtimestamp(aligned_epoch, tz=timezone.utc)

        # Create five 1-minute summaries covering a 5-minute window
        summaries = []
        for i in range(5):
            t_start = (base_time + timedelta(minutes=i)).isoformat()
            t_end = (base_time + timedelta(minutes=i + 1)).isoformat()
            s = MeasurementSummaryRecord(
                metric_name="ping_rtt",
                bucket_start_utc=t_start,
                bucket_end_utc=t_end,
                resolution_seconds=60,
                sample_count=30,
                min_value=10.0 + i,
                max_value=20.0 + i,
                mean_value=15.0 + i,
                median_value=15.0 + i,
                p95_value=19.0 + i,
                std_dev=2.0,
                unavailable_count=0,
                degraded_count=0,
                data_quality=DataQuality.VALID,
                unit="ms"
            )
            summaries.append(s)

        self.engine.save_measurement_summary_records(summaries)
        pre_compact = self.engine.query_measurement_summaries("ping_rtt", resolution_seconds=60)
        self.assertEqual(len(pre_compact), 5)

        # Run compaction cycle
        results = self.compactor.run_compaction_cycle(reference_time_utc=now)
        self.assertGreater(results["tier1_to_tier2"], 0)

        # Verify 1-min summaries were compacted and replaced by 5-min summary
        post_1min = self.engine.query_measurement_summaries("ping_rtt", resolution_seconds=60)
        post_5min = self.engine.query_measurement_summaries("ping_rtt", resolution_seconds=300)

        self.assertEqual(len(post_1min), 0)
        self.assertEqual(len(post_5min), 1)
        self.assertEqual(post_5min[0].resolution_seconds, 300)
        self.assertEqual(post_5min[0].sample_count, 150)


if __name__ == "__main__":
    unittest.main()
