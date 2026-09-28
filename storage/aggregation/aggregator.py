"""
VEYRA Metric Aggregation Engine.
Performs deterministic, metric-type-aware statistical aggregation over raw observations
for compact historical storage without fabricating measurements.
"""
from typing import Dict, List, Optional, Any
import statistics
import math

from app.core.contracts import Observation, Measurement, MetricState
from storage.contracts import MeasurementSummaryRecord, DataQuality, SummaryResolution


class MetricAggregator:
    """Aggregates raw telemetry observations into statistical historical summaries."""

    @staticmethod
    def _calculate_percentile(data: List[float], percentile: float) -> Optional[float]:
        """Calculates exact or interpolated percentile from sorted data."""
        if not data:
            return None
        k = (len(data) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return round(data[int(k)], 3)
        d0 = data[int(f)] * (c - k)
        d1 = data[int(c)] * (k - f)
        return round(d0 + d1, 3)

    @classmethod
    def aggregate_observations(
        cls,
        observations: List[Observation],
        bucket_start_utc: str,
        bucket_end_utc: str,
        resolution_seconds: int = SummaryResolution.MINUTE_1.value
    ) -> List[MeasurementSummaryRecord]:
        """
        Aggregates a batch of observations belonging to a fixed time window.
        Distinguishes missing/unavailable measurements from 0.0.
        """
        if not observations:
            return []

        # Group measurements by metric_name
        grouped_measurements: Dict[str, List[Measurement]] = {}
        for obs in observations:
            for name, meas in obs.measurements.items():
                if name not in grouped_measurements:
                    grouped_measurements[name] = []
                grouped_measurements[name].append(meas)

        summaries: List[MeasurementSummaryRecord] = []

        for metric_name, meas_list in grouped_measurements.items():
            sample_count = len(meas_list)
            valid_values: List[float] = []
            unavailable_count = 0
            degraded_count = 0
            unit = ""

            for m in meas_list:
                if not unit and m.unit:
                    unit = m.unit.value

                if m.state == MetricState.AVAILABLE and m.value is not None:
                    # Valid reading
                    if isinstance(m.value, (int, float)):
                        valid_values.append(float(m.value))
                    elif isinstance(m.value, bool):
                        valid_values.append(1.0 if m.value else 0.0)
                else:
                    unavailable_count += 1
                    if m.state in (MetricState.MEASUREMENT_FAILED, MetricState.STALE):
                        degraded_count += 1

            valid_count = len(valid_values)

            # Determine Data Quality
            if valid_count == 0:
                data_quality = DataQuality.UNAVAILABLE
            elif valid_count < 3 and sample_count >= 5:
                data_quality = DataQuality.INSUFFICIENT_DATA
            elif degraded_count > 0:
                data_quality = DataQuality.DEGRADED
            elif unavailable_count > 0:
                data_quality = DataQuality.PARTIAL
            else:
                data_quality = DataQuality.VALID

            # Calculate statistics only if valid samples exist
            if valid_count > 0:
                sorted_vals = sorted(valid_values)
                min_val = round(min(valid_values), 3)
                max_val = round(max(valid_values), 3)
                mean_val = round(sum(valid_values) / valid_count, 3)
                median_val = round(statistics.median(valid_values), 3)
                p95_val = cls._calculate_percentile(sorted_vals, 95.0)
                std_dev_val = round(statistics.stdev(valid_values), 3) if valid_count >= 2 else 0.0
            else:
                min_val = None
                max_val = None
                mean_val = None
                median_val = None
                p95_val = None
                std_dev_val = None

            record = MeasurementSummaryRecord(
                metric_name=metric_name,
                bucket_start_utc=bucket_start_utc,
                bucket_end_utc=bucket_end_utc,
                resolution_seconds=resolution_seconds,
                sample_count=sample_count,
                min_value=min_val,
                max_value=max_val,
                mean_value=mean_val,
                median_value=median_val,
                p95_value=p95_val,
                std_dev=std_dev_val,
                unavailable_count=unavailable_count,
                degraded_count=degraded_count,
                data_quality=data_quality,
                unit=unit,
            )
            summaries.append(record)

        return summaries

    @classmethod
    def rollup_summaries(
        cls,
        lower_tier_summaries: List[MeasurementSummaryRecord],
        bucket_start_utc: str,
        bucket_end_utc: str,
        target_resolution_seconds: int
    ) -> List[MeasurementSummaryRecord]:
        """
        Rolls up lower-tier summaries (e.g. twelve 1-min summaries) into a higher-tier summary (e.g. one 5-min summary).
        Preserves statistical bounds and non-fabrication guarantees.
        """
        if not lower_tier_summaries:
            return []

        # Group by metric_name
        grouped: Dict[str, List[MeasurementSummaryRecord]] = {}
        for s in lower_tier_summaries:
            if s.metric_name not in grouped:
                grouped[s.metric_name] = []
            grouped[s.metric_name].append(s)

        rolled_up: List[MeasurementSummaryRecord] = []

        for metric_name, records in grouped.items():
            total_samples = sum(r.sample_count for r in records)
            total_unavailable = sum(r.unavailable_count for r in records)
            total_degraded = sum(r.degraded_count for r in records)
            unit = records[0].unit

            valid_mins = [r.min_value for r in records if r.min_value is not None]
            valid_maxs = [r.max_value for r in records if r.max_value is not None]
            valid_means = [r.mean_value for r in records if r.mean_value is not None]
            valid_medians = [r.median_value for r in records if r.median_value is not None]
            valid_p95s = [r.p95_value for r in records if r.p95_value is not None]

            if valid_means:
                min_val = round(min(valid_mins), 3)
                max_val = round(max(valid_maxs), 3)
                mean_val = round(sum(valid_means) / len(valid_means), 3)
                median_val = round(statistics.median(valid_medians), 3)
                p95_val = round(max(valid_p95s), 3)
                std_dev_val = round(statistics.stdev(valid_means), 3) if len(valid_means) >= 2 else 0.0

                if total_degraded > 0:
                    quality = DataQuality.DEGRADED
                elif total_unavailable > 0:
                    quality = DataQuality.PARTIAL
                else:
                    quality = DataQuality.VALID
            else:
                min_val = None
                max_val = None
                mean_val = None
                median_val = None
                p95_val = None
                std_dev_val = None
                quality = DataQuality.UNAVAILABLE

            rolled = MeasurementSummaryRecord(
                metric_name=metric_name,
                bucket_start_utc=bucket_start_utc,
                bucket_end_utc=bucket_end_utc,
                resolution_seconds=target_resolution_seconds,
                sample_count=total_samples,
                min_value=min_val,
                max_value=max_val,
                mean_value=mean_val,
                median_value=median_val,
                p95_value=p95_val,
                std_dev=std_dev_val,
                unavailable_count=total_unavailable,
                degraded_count=total_degraded,
                data_quality=quality,
                unit=unit,
            )
            rolled_up.append(rolled)

        return rolled_up
