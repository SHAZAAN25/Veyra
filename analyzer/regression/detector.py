"""
VEYRA Performance Regression Detector Foundation.
Detects when current operational performance has degraded significantly compared to the
established personal PC baseline. Never claims regression from insufficient samples.
"""
from typing import List, Optional

from app.core.contracts import Observation, MetricState
from analyzer.contracts import RegressionAssessment, BaselineQuality
from analyzer.baseline.personal_baseline import PersonalBaselineEngine


class RegressionDetector:
    """
    Evaluates current observation sets against established Personal PC Baselines.
    """
    def __init__(self, baseline_engine: PersonalBaselineEngine, regression_threshold_pct: float = 40.0):
        self.baseline_engine = baseline_engine
        self.threshold_pct = regression_threshold_pct

    def evaluate_regression(self, observations: List[Observation], metric_name: str) -> RegressionAssessment:
        baseline = self.baseline_engine.get_baseline(metric_name)

        # Check for insufficient baseline data
        if baseline.quality == BaselineQuality.INSUFFICIENT_DATA or baseline.mean == 0.0:
            return RegressionAssessment(
                metric_name=metric_name,
                baseline_mean=baseline.mean,
                observed_mean=0.0,
                percentage_degradation=0.0,
                is_significant=False,
                confidence=0.1,
                sample_count=len(observations),
                explanation="Insufficient baseline samples to evaluate regression reliably."
            )

        # Extract current observation values
        current_vals: List[float] = []
        for obs in observations:
            m = obs.get_metric(metric_name)
            if m and m.state == MetricState.AVAILABLE and isinstance(m.value, (int, float)):
                current_vals.append(float(m.value))

        if not current_vals:
            return RegressionAssessment(
                metric_name=metric_name,
                baseline_mean=baseline.mean,
                observed_mean=0.0,
                percentage_degradation=0.0,
                is_significant=False,
                confidence=0.0,
                sample_count=0,
                explanation="No current observations available for metric."
            )

        observed_mean = sum(current_vals) / len(current_vals)
        # Determine degradation direction (higher latency is worse; higher throughput is better)
        is_higher_worse = metric_name in {
            "internet_latency_rtt_ms", "internet_packet_loss_pct", "internet_jitter_ms",
            "cpu_utilization_pct", "ram_utilization_pct", "dns_response_ms"
        }

        if is_higher_worse:
            pct_change = ((observed_mean - baseline.mean) / baseline.mean) * 100.0
        else:
            pct_change = ((baseline.mean - observed_mean) / baseline.mean) * 100.0

        is_significant = (pct_change >= self.threshold_pct)
        # Confidence derived from sample counts
        confidence = min(0.95, round(0.4 + (len(current_vals) * 0.05) + (baseline.sample_count * 0.01), 2))

        explanation = (
            f"Observed mean ({round(observed_mean, 2)}) has degraded by {round(pct_change, 1)}% "
            f"relative to established baseline ({round(baseline.mean, 2)})."
            if is_significant else "Observed metrics are within expected baseline variation."
        )

        return RegressionAssessment(
            metric_name=metric_name,
            baseline_mean=baseline.mean,
            observed_mean=round(observed_mean, 2),
            percentage_degradation=round(pct_change, 2),
            is_significant=is_significant,
            confidence=confidence,
            sample_count=len(current_vals),
            explanation=explanation
        )
