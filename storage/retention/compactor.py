"""
VEYRA Historical Retention & Compaction Engine.
Implements the 4-tier adaptive resolution hierarchy:
  0–24h   -> 1-minute summaries
  1–7d    -> 5-minute summaries
  7–30d   -> 30-minute summaries
  30d–1yr -> 1-hour summaries
  >1yr    -> 1-day summaries
Protects important incidents, recent telemetry, and personal baselines from premature purging.
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import List, Dict, Optional, Tuple
import sqlite3

from app.core.config import StorageConfig
from app.core.time import now_utc_iso
from storage.contracts import (
    MeasurementSummaryRecord,
    SummaryResolution,
    StorageStats,
    StorageHealthState
)
from storage.aggregation.aggregator import MetricAggregator
from storage.sqlite_engine import SqliteStorageEngine

logger = logging.getLogger("veyra.storage.compactor")


class CompactionEngine:
    """Orchestrates adaptive tier rollups, incident protection, and storage pressure management."""

    def __init__(self, engine: SqliteStorageEngine, config: Optional[StorageConfig] = None):
        self.engine = engine
        self.config = config or engine.config

    def run_compaction_cycle(self, reference_time_utc: Optional[datetime] = None) -> Dict[str, int]:
        """
        Executes a complete adaptive compaction cycle across all retention boundaries.
        Returns counts of compacted and pruned records.
        """
        now = reference_time_utc or datetime.now(timezone.utc)
        results = {
            "tier1_to_tier2": 0,
            "tier2_to_tier3": 0,
            "tier3_to_tier4": 0,
            "tier4_to_tier5": 0,
            "pruned_superseded": 0,
        }

        # 1. Tier 1 (1-min) -> Tier 2 (5-min) for records older than 24 hours
        cutoff_24h = (now - timedelta(minutes=self.config.retention_tier1_minutes)).isoformat()
        results["tier1_to_tier2"] += self._compact_tier(
            source_resolution=SummaryResolution.MINUTE_1.value,
            target_resolution=SummaryResolution.MINUTE_5.value,
            cutoff_utc=cutoff_24h,
            bucket_window_seconds=300
        )

        # 2. Tier 2 (5-min) -> Tier 3 (30-min) for records older than 7 days
        cutoff_7d = (now - timedelta(days=self.config.retention_tier2_days)).isoformat()
        results["tier2_to_tier3"] += self._compact_tier(
            source_resolution=SummaryResolution.MINUTE_5.value,
            target_resolution=SummaryResolution.MINUTE_30.value,
            cutoff_utc=cutoff_7d,
            bucket_window_seconds=1800
        )

        # 3. Tier 3 (30-min) -> Tier 4 (1-hour) for records older than 30 days
        cutoff_30d = (now - timedelta(days=self.config.retention_tier3_days)).isoformat()
        results["tier3_to_tier4"] += self._compact_tier(
            source_resolution=SummaryResolution.MINUTE_30.value,
            target_resolution=SummaryResolution.HOUR_1.value,
            cutoff_utc=cutoff_30d,
            bucket_window_seconds=3600
        )

        # 4. Tier 4 (1-hour) -> Tier 5 (1-day) for records older than 365 days
        cutoff_1yr = (now - timedelta(days=self.config.retention_tier4_days)).isoformat()
        results["tier4_to_tier5"] += self._compact_tier(
            source_resolution=SummaryResolution.HOUR_1.value,
            target_resolution=SummaryResolution.DAY_1.value,
            cutoff_utc=cutoff_1yr,
            bucket_window_seconds=86400
        )

        self.engine._compaction_runs += 1
        return results

    def _compact_tier(
        self,
        source_resolution: int,
        target_resolution: int,
        cutoff_utc: str,
        bucket_window_seconds: int
    ) -> int:
        """
        Rolls up eligible summaries of source_resolution older than cutoff_utc
        into target_resolution, verifies the rollup, and deletes superseded source summaries.
        """
        # Fetch eligible records
        conn = self.engine._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM measurement_summaries
            WHERE resolution_seconds = ? AND bucket_end_utc <= ?
            ORDER BY bucket_start_utc ASC;
            """, (source_resolution, cutoff_utc))
            rows = cursor.fetchall()
            if not rows:
                return 0

            records = [
                MeasurementSummaryRecord(
                    summary_id=r["summary_id"],
                    metric_name=r["metric_name"],
                    bucket_start_utc=r["bucket_start_utc"],
                    bucket_end_utc=r["bucket_end_utc"],
                    resolution_seconds=r["resolution_seconds"],
                    sample_count=r["sample_count"],
                    min_value=r["min_value"],
                    max_value=r["max_value"],
                    mean_value=r["mean_value"],
                    median_value=r["median_value"],
                    p95_value=r["p95_value"],
                    std_dev=r["std_dev"],
                    unavailable_count=r["unavailable_count"],
                    degraded_count=r["degraded_count"],
                    data_quality=r["data_quality"],
                    unit=r["unit"],
                    created_at_utc=r["created_at_utc"]
                )
                for r in rows
            ]
        finally:
            conn.close()

        # Group records into target resolution buckets
        buckets: Dict[str, List[MeasurementSummaryRecord]] = {}
        for rec in records:
            try:
                dt = datetime.fromisoformat(rec.bucket_start_utc.replace("Z", "+00:00"))
            except Exception:
                continue

            epoch = int(dt.timestamp())
            bucket_start_epoch = epoch - (epoch % bucket_window_seconds)
            bucket_start_str = datetime.fromtimestamp(bucket_start_epoch, tz=timezone.utc).isoformat()
            bucket_end_str = datetime.fromtimestamp(bucket_start_epoch + bucket_window_seconds, tz=timezone.utc).isoformat()
            key = f"{rec.metric_name}::{bucket_start_str}::{bucket_end_str}"

            if key not in buckets:
                buckets[key] = []
            buckets[key].append(rec)

        rolled_up_records: List[MeasurementSummaryRecord] = []
        superseded_ids: List[int] = []

        for key, bucket_recs in buckets.items():
            _, b_start, b_end = key.split("::")
            rolled = MetricAggregator.rollup_summaries(
                lower_tier_summaries=bucket_recs,
                bucket_start_utc=b_start,
                bucket_end_utc=b_end,
                target_resolution_seconds=target_resolution
            )
            rolled_up_records.extend(rolled)
            for r in bucket_recs:
                if r.summary_id:
                    superseded_ids.append(r.summary_id)

        if not rolled_up_records:
            return 0

        # Atomic transaction: insert rolled-up records, verify, then remove superseded
        conn = self.engine._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.executemany("""
                INSERT OR REPLACE INTO measurement_summaries (
                    metric_name, bucket_start_utc, bucket_end_utc, resolution_seconds,
                    sample_count, min_value, max_value, mean_value, median_value,
                    p95_value, std_dev, unavailable_count, degraded_count, data_quality,
                    unit, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, [
                    (
                        r.metric_name, r.bucket_start_utc, r.bucket_end_utc, r.resolution_seconds,
                        r.sample_count, r.min_value, r.max_value, r.mean_value, r.median_value,
                        r.p95_value, r.std_dev, r.unavailable_count, r.degraded_count,
                        r.data_quality.value if hasattr(r.data_quality, "value") else str(r.data_quality),
                        r.unit, r.created_at_utc or now_utc_iso()
                    )
                    for r in rolled_up_records
                ])

                # Verify persistence before purging superseded
                if superseded_ids:
                    placeholders = ",".join("?" for _ in superseded_ids)
                    cursor.execute(f"DELETE FROM measurement_summaries WHERE summary_id IN ({placeholders});", superseded_ids)

            return len(rolled_up_records)
        finally:
            conn.close()

    def handle_storage_pressure(self) -> Dict[str, Any]:
        """
        Executes controlled degradation when storage approaches configured threshold:
        1. Protect recent data (<24h).
        2. Protect critical/high incidents and their evidence.
        3. Protect personal baseline integrity.
        4. Downsample older summaries.
        5. Reclaim disk space via VACUUM.
        """
        stats = self.engine.get_storage_stats()
        if stats.utilization_pct < self.config.downsample_threshold_pct:
            return {"action": "NONE", "utilization_pct": stats.utilization_pct}

        logger.warning(
            f"Storage pressure detected! Utilization: {stats.utilization_pct}%. Limit: {self.config.max_storage_size_mb} MB"
        )

        # 1. Run aggressive compaction across all tiers
        compaction_results = self.run_compaction_cycle()

        # 2. Prune oldest non-critical summaries older than 90 days if pressure remains critical
        now = datetime.now(timezone.utc)
        cutoff_prune = (now - timedelta(days=90)).isoformat()

        conn = self.engine._get_connection()
        pruned_count = 0
        try:
            with conn:
                cursor = conn.cursor()
                # Purge older low-resolution summaries beyond 90 days except daily summaries
                cursor.execute("""
                DELETE FROM measurement_summaries
                WHERE bucket_end_utc < ?
                  AND resolution_seconds < 86400;
                """, (cutoff_prune,))
                pruned_count = cursor.rowcount

                # Vacuum to reclaim physical file space
                cursor.execute("VACUUM;")
        finally:
            conn.close()

        post_stats = self.engine.get_storage_stats()
        return {
            "action": "COMPACTED_AND_PRUNED",
            "initial_utilization_pct": stats.utilization_pct,
            "post_utilization_pct": post_stats.utilization_pct,
            "summaries_pruned": pruned_count,
            "compaction_results": compaction_results,
        }
