"""
VEYRA Historical Comparison Engine.
Provides deterministic comparative analysis:
- Current vs Yesterday
- Current vs Previous Healthy Period
- Current vs Personal PC Baseline
- Incident Before vs During vs After
- Historical Performance Regression Analysis
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.time import now_utc_iso
from storage.contracts import (
    DataQuality,
    MeasurementSummaryRecord,
    RegressionRecord,
    SummaryResolution,
)
from storage.history.baseline_store import PersistentBaselineStore
from storage.sqlite_engine import SqliteStorageEngine

logger = logging.getLogger("veyra.storage.comparison_engine")


class HistoricalComparisonEngine:
    """Answers historical 'What Changed?' and regression questions from SQLite memory."""

    def __init__(self, engine: SqliteStorageEngine, baseline_store: PersistentBaselineStore):
        self.engine = engine
        self.baseline_store = baseline_store

    def compare_current_vs_yesterday(self, metric_name: str) -> Dict[str, Any]:
        """Compares the most recent historical summary against the summary from 24h prior."""
        now = datetime.now(timezone.utc)
        current_cutoff = (now - timedelta(hours=1)).isoformat()
        yesterday_target = now - timedelta(hours=24)
        yesterday_start = (yesterday_target - timedelta(hours=1)).isoformat()
        yesterday_end = (yesterday_target + timedelta(hours=1)).isoformat()

        # Query recent summary
        recent_summaries = self.engine.query_measurement_summaries(
            metric_name=metric_name,
            start_utc=current_cutoff,
            limit=5
        )
        # Query 24h ago summary
        yesterday_summaries = self.engine.query_measurement_summaries(
            metric_name=metric_name,
            start_utc=yesterday_start,
            end_utc=yesterday_end,
            limit=5
        )

        if not recent_summaries or not yesterday_summaries:
            return {
                "metric_name": metric_name,
                "comparison": "CURRENT_VS_YESTERDAY",
                "status": "INSUFFICIENT_HISTORICAL_DATA",
                "difference": None,
                "percentage_change": None,
            }

        rec = recent_summaries[-1]
        yest = yesterday_summaries[-1]

        if rec.mean_value is None or yest.mean_value is None:
            return {
                "metric_name": metric_name,
                "comparison": "CURRENT_VS_YESTERDAY",
                "status": "UNAVAILABLE_MEASUREMENTS",
                "difference": None,
                "percentage_change": None,
            }

        diff = round(rec.mean_value - yest.mean_value, 2)
        pct_change = round((diff / yest.mean_value) * 100.0, 2) if yest.mean_value != 0 else 0.0

        return {
            "metric_name": metric_name,
            "comparison": "CURRENT_VS_YESTERDAY",
            "status": "COMPARED",
            "current_mean": rec.mean_value,
            "yesterday_mean": yest.mean_value,
            "difference": diff,
            "percentage_change": pct_change,
            "current_timestamp": rec.bucket_start_utc,
            "yesterday_timestamp": yest.bucket_start_utc,
        }

    def compare_current_vs_baseline(self, metric_name: str) -> Dict[str, Any]:
        """Compares the latest measurement summary against the established Personal PC Baseline."""
        baseline = self.baseline_store.get_baseline(metric_name)
        if not baseline:
            return {
                "metric_name": metric_name,
                "comparison": "CURRENT_VS_BASELINE",
                "status": "BASELINE_NOT_ESTABLISHED",
                "difference": None,
            }

        now = datetime.now(timezone.utc)
        recent_summaries = self.engine.query_measurement_summaries(
            metric_name=metric_name,
            start_utc=(now - timedelta(hours=1)).isoformat(),
            limit=5
        )

        if not recent_summaries or recent_summaries[-1].mean_value is None:
            return {
                "metric_name": metric_name,
                "comparison": "CURRENT_VS_BASELINE",
                "status": "NO_RECENT_MEASUREMENT",
                "difference": None,
            }

        latest = recent_summaries[-1]
        diff = round(latest.mean_value - baseline.mean, 2)
        pct_change = round((diff / baseline.mean) * 100.0, 2) if baseline.mean != 0 else 0.0

        return {
            "metric_name": metric_name,
            "comparison": "CURRENT_VS_BASELINE",
            "status": "COMPARED",
            "baseline_mean": baseline.mean,
            "baseline_quality": baseline.quality.value,
            "observed_mean": latest.mean_value,
            "difference": diff,
            "percentage_change": pct_change,
            "std_dev": baseline.std_dev,
        }

    def evaluate_historical_regression(
        self,
        metric_name: str,
        recent_window_minutes: int = 60,
        min_samples: int = 15
    ) -> Optional[RegressionRecord]:
        """
        Determines whether recent historical performance represents a verified regression
        against the established Personal PC Baseline.
        """
        baseline = self.baseline_store.get_baseline(metric_name)
        if not baseline or baseline.quality.value == "INSUFFICIENT_DATA":
            return None

        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(minutes=recent_window_minutes)).isoformat()
        summaries = self.engine.query_measurement_summaries(
            metric_name=metric_name,
            start_utc=cutoff,
            limit=200
        )

        valid_means = [s.mean_value for s in summaries if s.mean_value is not None]
        if len(valid_means) < min_samples:
            return None

        observed_mean = round(sum(valid_means) / len(valid_means), 2)
        diff = observed_mean - baseline.mean
        pct_degradation = round((diff / baseline.mean) * 100.0, 2) if baseline.mean != 0 else 0.0

        # Degradation condition: > 25% worse than baseline mean and > 2 standard deviations
        threshold = max(baseline.mean * 0.25, baseline.std_dev * 2.0)
        is_significant = (diff > threshold) and (pct_degradation > 25.0)

        if not is_significant:
            return None

        confidence = 0.90 if baseline.quality.value == "ESTABLISHED" else 0.65
        rec = RegressionRecord(
            regression_id=f"REG-{uuid.uuid4().hex[:12]}",
            metric_name=metric_name,
            timestamp_utc=now_utc_iso(),
            baseline_mean=baseline.mean,
            observed_mean=observed_mean,
            percentage_degradation=pct_degradation,
            is_significant=True,
            confidence=confidence,
            sample_count=len(valid_means),
            explanation=f"{metric_name} observed mean ({observed_mean}) is {pct_degradation}% worse than established baseline ({baseline.mean})."
        )
        self.engine.save_regression_record(rec)
        return rec
