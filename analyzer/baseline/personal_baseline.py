"""
VEYRA Personal PC Baseline Foundation.
Maintains deterministic running statistical profiles for host telemetry metrics.
Computes sample count, mean, median, min, max, p95, standard deviation, and baseline quality.
Never fabricates baseline training data; runs entirely local-first without cloud dependence.
"""
from collections import deque
import math
import statistics
import time
from typing import Dict, List, Optional, Tuple

from app.core.contracts import Observation, MetricState
from analyzer.contracts import BaselineMetricSummary, BaselineQuality


class PersonalBaselineEngine:
    """
    Learns statistical normals for this specific PC from genuine operational telemetry.
    """
    def __init__(self, max_samples_per_metric: int = 500, min_samples_for_baseline: int = 15):
        self._max_samples = max_samples_per_metric
        self._min_samples = min_samples_for_baseline
        self._samples: Dict[str, deque[float]] = {}
        self._last_update_monotonic: Dict[str, float] = {}

    def record_observation(self, observation: Observation) -> None:
        """Extracts valid numeric measurements into the baseline sample pool."""
        now = time.monotonic()
        for name, m in observation.measurements.items():
            if m.state == MetricState.AVAILABLE and isinstance(m.value, (int, float)):
                if name not in self._samples:
                    self._samples[name] = deque(maxlen=self._max_samples)
                self._samples[name].append(float(m.value))
                self._last_update_monotonic[name] = now

    def get_baseline(self, metric_name: str) -> BaselineMetricSummary:
        """Calculates statistical summary and baseline quality for a metric."""
        samples = list(self._samples.get(metric_name, []))
        count = len(samples)

        if count < self._min_samples:
            return BaselineMetricSummary(
                metric_name=metric_name,
                sample_count=count,
                mean=round(sum(samples) / count, 2) if count > 0 else 0.0,
                median=round(statistics.median(samples), 2) if count > 0 else 0.0,
                p95=round(max(samples), 2) if count > 0 else 0.0,
                min_value=round(min(samples), 2) if count > 0 else 0.0,
                max_value=round(max(samples), 2) if count > 0 else 0.0,
                std_dev=0.0,
                quality=BaselineQuality.INSUFFICIENT_DATA
            )

        sorted_samples = sorted(samples)
        mean_val = statistics.mean(samples)
        median_val = statistics.median(samples)
        min_val = min(samples)
        max_val = max(samples)
        std_dev = statistics.stdev(samples) if count > 1 else 0.0

        # Percentile 95 calculation
        p95_idx = int(math.ceil(0.95 * count)) - 1
        p95_val = sorted_samples[min(max(p95_idx, 0), count - 1)]

        # Determine quality
        quality = BaselineQuality.ESTABLISHED if count >= 30 else BaselineQuality.LOW_CONFIDENCE
        last_update = self._last_update_monotonic.get(metric_name, 0.0)
        if (time.monotonic() - last_update) > 86400.0:  # 24 hours stale
            quality = BaselineQuality.STALE

        return BaselineMetricSummary(
            metric_name=metric_name,
            sample_count=count,
            mean=round(mean_val, 2),
            median=round(median_val, 2),
            p95=round(p95_val, 2),
            min_value=round(min_val, 2),
            max_value=round(max_val, 2),
            std_dev=round(std_dev, 2),
            quality=quality
        )

    def evaluate_deviation(self, metric_name: str, current_value: float) -> Tuple[float, bool]:
        """
        Calculates ratio of current value to baseline mean.
        Returns (deviation_ratio, is_abnormal).
        """
        baseline = self.get_baseline(metric_name)
        if baseline.quality == BaselineQuality.INSUFFICIENT_DATA or baseline.mean == 0.0:
            return 1.0, False

        ratio = current_value / baseline.mean
        is_abnormal = (ratio > 1.5 or ratio < 0.5)
        return round(ratio, 2), is_abnormal
