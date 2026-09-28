"""
VEYRA Optimization A/B Testing Engine.
Manages Baseline A vs Observation B experiments.
Detects confounding variables (workload shifts, external network changes, thermal throttling)
and flags tests as INCONCLUSIVE when causality cannot be cleanly proven.
"""
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.time import now_utc_iso
from optimization.contracts import VerificationOutcome, VerificationResult

logger = logging.getLogger("veyra.optimization.ab_testing")


@dataclass
class ConfounderEvaluation:
    """Detection of environmental variables that invalidate direct causality."""
    confounder_detected: bool
    confounder_names: List[str]
    explanation: str


@dataclass
class ABExperimentReport:
    """Complete report of an A/B verification experiment."""
    experiment_id: str
    opportunity_id: str
    baseline_window_samples: int
    test_window_samples: int
    metric_name: str
    baseline_mean: Optional[float]
    test_mean: Optional[float]
    difference: Optional[float]
    percentage_change: Optional[float]
    confounders: ConfounderEvaluation
    final_verdict: str  # "VERIFIED_IMPROVEMENT", "NO_CHANGE", "REGRESSION", "INCONCLUSIVE"
    confidence: float
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "opportunity_id": self.opportunity_id,
            "baseline_window_samples": self.baseline_window_samples,
            "test_window_samples": self.test_window_samples,
            "metric_name": self.metric_name,
            "baseline_mean": self.baseline_mean,
            "test_mean": self.test_mean,
            "difference": self.difference,
            "percentage_change": self.percentage_change,
            "confounders": {
                "confounder_detected": self.confounders.confounder_detected,
                "names": self.confounders.confounder_names,
                "explanation": self.confounders.explanation,
            },
            "final_verdict": self.final_verdict,
            "confidence": self.confidence,
            "summary": self.summary,
        }


class OptimizationABTestingEngine:
    """Executes controlled A/B evaluations between pre-change baseline and post-change test windows."""

    def evaluate_experiment(
        self,
        opportunity_id: str,
        metric_name: str,
        baseline_samples: List[float],
        test_samples: List[float],
        external_context_pre: Dict[str, Any],
        external_context_post: Dict[str, Any],
        lower_is_better: bool = True,
    ) -> ABExperimentReport:
        """
        Conducts A/B evaluation with strict confounder filtering.
        """
        experiment_id = f"ab_{uuid.uuid4().hex[:12]}"

        # Check for Confounding Variables
        confounders = self._detect_confounders(external_context_pre, external_context_post)

        if not baseline_samples or not test_samples:
            return ABExperimentReport(
                experiment_id=experiment_id,
                opportunity_id=opportunity_id,
                baseline_window_samples=len(baseline_samples),
                test_window_samples=len(test_samples),
                metric_name=metric_name,
                baseline_mean=None,
                test_mean=None,
                difference=None,
                percentage_change=None,
                confounders=confounders,
                final_verdict="INCONCLUSIVE",
                confidence=0.0,
                summary="Insufficient telemetry samples captured during A/B windows.",
            )

        baseline_mean = round(sum(baseline_samples) / len(baseline_samples), 2)
        test_mean = round(sum(test_samples) / len(test_samples), 2)
        diff = round(test_mean - baseline_mean, 2)
        pct_change = round((diff / baseline_mean) * 100.0, 1) if baseline_mean != 0.0 else 0.0

        if confounders.confounder_detected:
            return ABExperimentReport(
                experiment_id=experiment_id,
                opportunity_id=opportunity_id,
                baseline_window_samples=len(baseline_samples),
                test_window_samples=len(test_samples),
                metric_name=metric_name,
                baseline_mean=baseline_mean,
                test_mean=test_mean,
                difference=diff,
                percentage_change=pct_change,
                confounders=confounders,
                final_verdict="INCONCLUSIVE",
                confidence=0.40,
                summary=f"A/B test inconclusive due to confounders: {confounders.explanation}",
            )

        # Statistical classification
        if lower_is_better:
            if pct_change <= -8.0:
                verdict = "VERIFIED_IMPROVEMENT"
                summary = f"Verified improvement: {metric_name} decreased by {abs(pct_change)}% ({baseline_mean} -> {test_mean}) without confounding variables."
            elif pct_change >= 12.0:
                verdict = "REGRESSION"
                summary = f"Verified regression: {metric_name} increased by {pct_change}% ({baseline_mean} -> {test_mean})."
            else:
                verdict = "NO_CHANGE"
                summary = f"No meaningful change: {metric_name} shifted by {pct_change:+.1f}% within expected variance bounds."
        else:
            if pct_change >= 8.0:
                verdict = "VERIFIED_IMPROVEMENT"
                summary = f"Verified improvement: {metric_name} increased by {pct_change}% ({baseline_mean} -> {test_mean})."
            elif pct_change <= -12.0:
                verdict = "REGRESSION"
                summary = f"Verified regression: {metric_name} degraded by {abs(pct_change)}% ({baseline_mean} -> {test_mean})."
            else:
                verdict = "NO_CHANGE"
                summary = f"No meaningful change: {metric_name} shifted by {pct_change:+.1f}%."

        return ABExperimentReport(
            experiment_id=experiment_id,
            opportunity_id=opportunity_id,
            baseline_window_samples=len(baseline_samples),
            test_window_samples=len(test_samples),
            metric_name=metric_name,
            baseline_mean=baseline_mean,
            test_mean=test_mean,
            difference=diff,
            percentage_change=pct_change,
            confounders=confounders,
            final_verdict=verdict,
            confidence=0.92,
            summary=summary,
        )

    def _detect_confounders(
        self,
        pre_ctx: Dict[str, Any],
        post_ctx: Dict[str, Any]
    ) -> ConfounderEvaluation:
        """Identifies environmental shifts that confound optimization causality."""
        detected = []
        explanations = []

        # 1. Unrelated Background Workload Shift
        pre_cpu_bg = pre_ctx.get("background_cpu_pct", 0)
        post_cpu_bg = post_ctx.get("background_cpu_pct", 0)
        if abs(post_cpu_bg - pre_cpu_bg) > 25.0:
            detected.append("BACKGROUND_WORKLOAD_SHIFT")
            explanations.append(f"Unrelated background task CPU shifted by {post_cpu_bg - pre_cpu_bg:+.1f}%.")

        # 2. Network Gateway State Shift
        pre_gw_loss = pre_ctx.get("gateway_packet_loss_pct", 0)
        post_gw_loss = post_ctx.get("gateway_packet_loss_pct", 0)
        if abs(post_gw_loss - pre_gw_loss) > 5.0:
            detected.append("EXTERNAL_GATEWAY_SHIFT")
            explanations.append("Local router gateway packet loss fluctuated independently.")

        # 3. Game State Shift
        if pre_ctx.get("game_name") != post_ctx.get("game_name"):
            detected.append("DIFFERENT_GAME_WORKLOAD")
            explanations.append("Active game title changed during test window.")

        # 4. Thermal Throttling Shift
        if not pre_ctx.get("thermal_throttling") and post_ctx.get("thermal_throttling"):
            detected.append("THERMAL_THROTTLING_EMERGED")
            explanations.append("Hardware thermal limit triggered independently during test window.")

        return ConfounderEvaluation(
            confounder_detected=len(detected) > 0,
            confounder_names=detected,
            explanation="; ".join(explanations) if explanations else "No environmental confounders detected.",
        )
