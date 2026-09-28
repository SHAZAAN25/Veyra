"""
VEYRA Persistent Baseline Store.
Manages long-term persistence and evolutionary updates of Personal PC Baselines in SQLite.
Ensures anomalous incident periods do not contaminate the baseline normal.
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, List, Optional
import math

from analyzer.contracts import BaselineMetricSummary, BaselineQuality
from app.core.time import now_utc_iso
from storage.contracts import BaselineRecord, TimeContext
from storage.sqlite_engine import SqliteStorageEngine

logger = logging.getLogger("veyra.storage.baseline_store")


class PersistentBaselineStore:
    """Provides durable storage and evolutionary updates for Personal PC Baselines."""

    def __init__(self, engine: SqliteStorageEngine):
        self.engine = engine

    def save_baseline(
        self,
        baseline: BaselineMetricSummary,
        time_context: str = "ALL"
    ) -> None:
        """Persists a baseline summary record to SQLite."""
        existing = self.engine.get_baseline_record(baseline.metric_name, time_context)
        version = (existing.version + 1) if existing else 1
        est_utc = existing.established_at_utc if existing else (baseline.updated_at_utc or now_utc_iso())

        rec = BaselineRecord(
            metric_name=baseline.metric_name,
            time_context=time_context,
            version=version,
            sample_count=baseline.sample_count,
            mean=baseline.mean,
            median=baseline.median,
            min_value=baseline.min_value,
            max_value=baseline.max_value,
            p95=baseline.p95,
            std_dev=baseline.std_dev,
            quality=baseline.quality.value if hasattr(baseline.quality, "value") else str(baseline.quality),
            established_at_utc=est_utc,
            updated_at_utc=baseline.updated_at_utc or now_utc_iso()
        )
        self.engine.save_baseline_record(rec)

    def get_baseline(
        self,
        metric_name: str,
        time_context: str = "ALL"
    ) -> Optional[BaselineMetricSummary]:
        """Retrieves and reconstructs a BaselineMetricSummary from SQLite."""
        rec = self.engine.get_baseline_record(metric_name, time_context)
        if not rec:
            return None

        # Check for staleness (>24 hours since last update)
        quality_str = rec.quality
        try:
            dt = datetime.fromisoformat(rec.updated_at_utc.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - dt > timedelta(hours=24):
                quality_str = BaselineQuality.STALE.value
        except Exception:
            pass

        quality = BaselineQuality(quality_str) if quality_str in BaselineQuality._value2member_map_ else BaselineQuality.INSUFFICIENT_DATA

        return BaselineMetricSummary(
            metric_name=rec.metric_name,
            sample_count=rec.sample_count,
            mean=rec.mean,
            median=rec.median,
            p95=rec.p95,
            min_value=rec.min_value,
            max_value=rec.max_value,
            std_dev=rec.std_dev,
            quality=quality,
            updated_at_utc=rec.updated_at_utc
        )

    def update_baseline_sample(
        self,
        metric_name: str,
        new_value: float,
        is_incident_active: bool = False,
        time_context: str = "ALL"
    ) -> Optional[BaselineMetricSummary]:
        """
        Evolutionary update: incorporates a new valid measurement into the persistent baseline.
        CRITICAL GUARD: If is_incident_active is True, sample is rejected to prevent baseline contamination.
        """
        if is_incident_active:
            logger.debug(f"Skipping baseline update for {metric_name}: incident is currently active.")
            return self.get_baseline(metric_name, time_context)

        rec = self.engine.get_baseline_record(metric_name, time_context)
        if not rec:
            # First sample for this metric
            new_summary = BaselineMetricSummary(
                metric_name=metric_name,
                sample_count=1,
                mean=round(new_value, 2),
                median=round(new_value, 2),
                p95=round(new_value, 2),
                min_value=round(new_value, 2),
                max_value=round(new_value, 2),
                std_dev=0.0,
                quality=BaselineQuality.INSUFFICIENT_DATA,
                updated_at_utc=now_utc_iso()
            )
            self.save_baseline(new_summary, time_context)
            return new_summary

        # Evolutionary running statistics update
        n = rec.sample_count + 1
        delta = new_value - rec.mean
        new_mean = round(rec.mean + (delta / n), 2)
        new_min = round(min(rec.min_value, new_value), 2)
        new_max = round(max(rec.max_value, new_value), 2)
        
        # Approximate variance update
        variance = (rec.std_dev ** 2) if rec.sample_count > 1 else 0.0
        new_variance = variance + ((delta * (new_value - new_mean) - variance) / n)
        new_std_dev = round(math.sqrt(max(0.0, new_variance)), 2)

        # Approximate median and p95 adjustment toward new value
        new_median = round(rec.median + (0.01 if new_value > rec.median else -0.01), 2)
        new_p95 = round(max(rec.p95, new_value if new_value > rec.p95 else rec.p95 * 0.999), 2)

        # Determine Quality Gate
        if n < 15:
            quality = BaselineQuality.INSUFFICIENT_DATA
        elif n < 50:
            quality = BaselineQuality.LOW_CONFIDENCE
        else:
            quality = BaselineQuality.ESTABLISHED

        updated_summary = BaselineMetricSummary(
            metric_name=metric_name,
            sample_count=n,
            mean=new_mean,
            median=new_median,
            p95=new_p95,
            min_value=new_min,
            max_value=new_max,
            std_dev=new_std_dev,
            quality=quality,
            updated_at_utc=now_utc_iso()
        )
        self.save_baseline(updated_summary, time_context)
        return updated_summary

    def reset_baseline(self, metric_name: Optional[str] = None) -> int:
        """Resets baseline data."""
        return self.engine.reset_baselines(metric_name)
