"""
VEYRA Optimization Verification Engine.
Monitors post-optimization telemetry across stabilization windows and compares
against pre-optimization baselines to verify genuine improvement, regression, or no change.
Never claims improvement based on completed exit codes alone.
"""
import logging
from typing import List, Optional

from optimization.contracts import VerificationOutcome, VerificationResult

logger = logging.getLogger("veyra.optimization.verification")


class VerificationEngine:
    """Evaluates whether an applied optimization produced genuine improvement."""

    def evaluate_verification(
        self,
        metric_name: str,
        baseline_samples: List[float],
        post_change_samples: List[float],
        lower_is_better: bool = True,
        improvement_threshold_pct: float = 8.0,
        regression_threshold_pct: float = 12.0,
    ) -> VerificationResult:
        """
        Calculates pre vs post statistical means and determines the verified outcome.
        """
        if not baseline_samples or not post_change_samples:
            return VerificationResult(
                outcome=VerificationOutcome.VERIFICATION_INCONCLUSIVE,
                metric_name=metric_name,
                baseline_value=None,
                post_value=None,
                difference=None,
                percentage_change=None,
                confidence=0.0,
                explanation="Insufficient metric samples captured during verification window.",
                should_rollback=False,
            )

        baseline_mean = sum(baseline_samples) / len(baseline_samples)
        post_mean = sum(post_change_samples) / len(post_change_samples)
        diff = post_mean - baseline_mean

        if baseline_mean > 0.0:
            pct_change = (diff / baseline_mean) * 100.0
        else:
            pct_change = 0.0

        confidence = min(0.95, round(len(post_change_samples) / 10.0, 2))

        # Determine outcome
        if lower_is_better:
            # Improvement is negative diff (e.g. lower latency, lower CPU)
            if pct_change <= -improvement_threshold_pct:
                outcome = VerificationOutcome.VERIFIED_IMPROVEMENT
                explanation = f"Metric '{metric_name}' improved by {abs(pct_change):.1f}% ({baseline_mean:.1f} -> {post_mean:.1f})."
                should_rollback = False
            elif pct_change >= regression_threshold_pct:
                outcome = VerificationOutcome.REGRESSION
                explanation = f"Regression detected: '{metric_name}' degraded by {pct_change:.1f}% ({baseline_mean:.1f} -> {post_mean:.1f})."
                should_rollback = True
            else:
                outcome = VerificationOutcome.NO_MEANINGFUL_CHANGE
                explanation = f"No meaningful change: '{metric_name}' changed by {pct_change:+.1f}% within normal variance bounds."
                should_rollback = False
        else:
            # Higher is better
            if pct_change >= improvement_threshold_pct:
                outcome = VerificationOutcome.VERIFIED_IMPROVEMENT
                explanation = f"Metric '{metric_name}' improved by {pct_change:.1f}% ({baseline_mean:.1f} -> {post_mean:.1f})."
                should_rollback = False
            elif pct_change <= -regression_threshold_pct:
                outcome = VerificationOutcome.REGRESSION
                explanation = f"Regression detected: '{metric_name}' degraded by {abs(pct_change):.1f}%."
                should_rollback = True
            else:
                outcome = VerificationOutcome.NO_MEANINGFUL_CHANGE
                explanation = f"No meaningful change: '{metric_name}' shifted by {pct_change:+.1f}%."
                should_rollback = False

        return VerificationResult(
            outcome=outcome,
            metric_name=metric_name,
            baseline_value=round(baseline_mean, 2),
            post_value=round(post_mean, 2),
            difference=round(diff, 2),
            percentage_change=round(pct_change, 1),
            confidence=confidence,
            explanation=explanation,
            should_rollback=should_rollback,
        )
