"""
Tests for VEYRA Historical Comparison Engine and Regression Analysis.
Verifies 'What Changed?' comparisons and regression detection against persistent baselines.
"""
from datetime import datetime, timezone, timedelta
import os
import tempfile
import unittest

from analyzer.contracts import BaselineMetricSummary, BaselineQuality
from storage.contracts import MeasurementSummaryRecord, DataQuality
from storage.history.baseline_store import PersistentBaselineStore
from storage.history.comparison_engine import HistoricalComparisonEngine
from storage.sqlite_engine import SqliteStorageEngine


class TestStorageComparisonAndRegression(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_comparison.sqlite")
        self.engine = SqliteStorageEngine(db_path=self.db_path)
        self.baseline_store = PersistentBaselineStore(self.engine)
        self.comparison_engine = HistoricalComparisonEngine(self.engine, self.baseline_store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_compare_current_vs_yesterday(self):
        now = datetime.now(timezone.utc)
        current_time = (now - timedelta(minutes=15)).isoformat()
        yesterday_time = (now - timedelta(hours=24)).isoformat()

        # Yesterday summary (rtt: 20ms)
        s_yest = MeasurementSummaryRecord(
            metric_name="latency_ms",
            bucket_start_utc=yesterday_time,
            bucket_end_utc=(now - timedelta(hours=23, minutes=59)).isoformat(),
            resolution_seconds=60,
            sample_count=30,
            min_value=18.0,
            max_value=22.0,
            mean_value=20.0,
            median_value=20.0,
            p95_value=21.0,
            std_dev=1.0,
            unit="ms"
        )

        # Current summary (rtt: 30ms)
        s_curr = MeasurementSummaryRecord(
            metric_name="latency_ms",
            bucket_start_utc=current_time,
            bucket_end_utc=(now - timedelta(minutes=14)).isoformat(),
            resolution_seconds=60,
            sample_count=30,
            min_value=28.0,
            max_value=35.0,
            mean_value=30.0,
            median_value=30.0,
            p95_value=33.0,
            std_dev=2.0,
            unit="ms"
        )
        self.engine.save_measurement_summary_records([s_yest, s_curr])

        res = self.comparison_engine.compare_current_vs_yesterday("latency_ms")
        self.assertEqual(res["status"], "COMPARED")
        self.assertEqual(res["current_mean"], 30.0)
        self.assertEqual(res["yesterday_mean"], 20.0)
        self.assertEqual(res["difference"], 10.0)
        self.assertEqual(res["percentage_change"], 50.0)

    def test_historical_regression_detection(self):
        # 1. Establish baseline at 20.0ms (std_dev = 2.0)
        baseline = BaselineMetricSummary(
            metric_name="ping_rtt",
            sample_count=100,
            mean=20.0,
            median=20.0,
            p95=23.0,
            min_value=15.0,
            max_value=25.0,
            std_dev=2.0,
            quality=BaselineQuality.ESTABLISHED
        )
        self.baseline_store.save_baseline(baseline)

        # 2. Add recent historical summaries showing severe degradation (e.g. 40.0ms, +100%)
        now = datetime.now(timezone.utc)
        summaries = []
        for i in range(20):
            t_start = (now - timedelta(minutes=i + 1)).isoformat()
            t_end = (now - timedelta(minutes=i)).isoformat()
            s = MeasurementSummaryRecord(
                metric_name="ping_rtt",
                bucket_start_utc=t_start,
                bucket_end_utc=t_end,
                resolution_seconds=60,
                sample_count=30,
                min_value=35.0,
                max_value=45.0,
                mean_value=40.0,
                median_value=40.0,
                p95_value=43.0,
                std_dev=2.5,
                unit="ms"
            )
            summaries.append(s)

        self.engine.save_measurement_summary_records(summaries)

        reg = self.comparison_engine.evaluate_historical_regression("ping_rtt")
        self.assertIsNotNone(reg)
        self.assertTrue(reg.is_significant)
        self.assertEqual(reg.baseline_mean, 20.0)
        self.assertEqual(reg.observed_mean, 40.0)
        self.assertEqual(reg.percentage_degradation, 100.0)

    def test_regression_does_not_fire_with_insufficient_baseline(self):
        """Verifies regression is rejected if baseline quality is INSUFFICIENT_DATA."""
        baseline = BaselineMetricSummary(
            metric_name="rtt",
            sample_count=5,
            mean=20.0,
            median=20.0,
            p95=20.0,
            min_value=20.0,
            max_value=20.0,
            std_dev=0.0,
            quality=BaselineQuality.INSUFFICIENT_DATA
        )
        self.baseline_store.save_baseline(baseline)

        reg = self.comparison_engine.evaluate_historical_regression("rtt")
        self.assertIsNone(reg)


if __name__ == "__main__":
    unittest.main()
