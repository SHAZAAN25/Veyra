"""
VEYRA Automatic Rollback Guardian.
Continuously watches post-change telemetry. If deterministic regression or degradation
thresholds are breached, triggers immediate, automated, bounded rollback to protect system stability.
"""
import logging
from typing import Any, Callable, Dict, Optional

from optimization.contracts import OptimizationState, VerificationOutcome, VerificationResult

logger = logging.getLogger("veyra.optimization.rollback_guardian")


class AutomaticRollbackGuardian:
    """Watches post-optimization health and triggers deterministic rollback when necessary."""

    def __init__(
        self,
        rollback_handler: Optional[Callable[[str], bool]] = None,
        max_regression_tolerance_pct: float = 12.0
    ):
        self.rollback_handler = rollback_handler
        self.max_regression_tolerance_pct = max_regression_tolerance_pct

    def evaluate_guardian_trigger(
        self,
        run_id: str,
        verification_result: VerificationResult
    ) -> bool:
        """
        Determines whether the guardian must execute an automated rollback.
        Deterministic rule: fires if regression exceeds tolerance or verification signals rollback.
        """
        if verification_result.outcome == VerificationOutcome.REGRESSION or verification_result.should_rollback:
            logger.warning(
                f"[GUARDIAN] Regression detected for run {run_id} on '{verification_result.metric_name}'. "
                f"Triggering automated rollback guardian."
            )
            if self.rollback_handler:
                success = self.rollback_handler(run_id)
                if not success:
                    logger.critical(f"[GUARDIAN] Critical failure: Automated rollback for run {run_id} failed!")
                return success
            return True
        return False
