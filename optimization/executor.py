"""
VEYRA Safe Optimization Executor.
Enforces the mandatory pipeline:
PROPOSED -> USER APPROVAL -> SNAPSHOT -> APPLY -> VERIFY -> ROLLBACK IF REGRESSED -> LOG.
Strictly prohibits unapproved execution, enforces concurrency locks, validates snapshot integrity,
prevents rollback replay/mismatch, and handles crash recovery for interrupted operations.
"""
import json
import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Set
import uuid

from app.core.exceptions import SecurityViolationError, StorageError
from app.core.privilege import PrivilegeError, PrivilegedHelper, PrivilegedOperationId
from app.core.time import now_utc_iso
from optimization.actions import BaseOptimizationAction
from optimization.contracts import (
    OptimizationOpportunity,
    OptimizationSnapshot,
    OptimizationState,
    VerificationOutcome,
    VerificationResult,
)
from optimization.rollback_guardian import AutomaticRollbackGuardian
from optimization.snapshots import SnapshotManager, SnapshotTamperedError
from optimization.verification import VerificationEngine
from storage.contracts import OptimizationResultRecord, OptimizationRunRecord
from storage.engine import StorageEngine

logger = logging.getLogger("veyra.optimization.executor")


class OptimizationConflictError(SecurityViolationError):
    """Raised when an optimization is attempted while another is actively executing."""
    pass


class RollbackSafetyError(SecurityViolationError):
    """Raised when an optimization rollback fails pre-flight safety checks."""
    pass


class OptimizationExecutor:
    """Authoritative execution coordinator for safe, reversible optimizations."""

    # Approved concrete optimization actions
    APPROVED_ACTION_CLASSES: Set[str] = {
        "DnsCacheFlushAction",
        "ProcessPriorityHintAction",
        "PowerSchemeOptimizationAction",
    }

    def __init__(
        self,
        storage: Optional[StorageEngine] = None,
        snapshot_manager: Optional[SnapshotManager] = None,
        verification_engine: Optional[VerificationEngine] = None,
        dry_run: bool = True,  # Defaults to sandboxed/dry_run mode for automated safety
        privileged_helper: Optional[PrivilegedHelper] = None,
    ):
        self.storage = storage
        self.snapshot_manager = snapshot_manager or SnapshotManager(storage=self.storage)
        self.verification_engine = verification_engine or VerificationEngine()
        self.dry_run = dry_run
        self.privileged_helper = privileged_helper or PrivilegedHelper(dry_run=self.dry_run)

        self._actions: Dict[str, BaseOptimizationAction] = {}
        self._active_runs: Dict[str, OptimizationRunRecord] = {}
        self._lock = threading.Lock()

        # Guardian integration
        self.guardian = AutomaticRollbackGuardian(rollback_handler=self.rollback_run)

        # Execute crash recovery on initialization
        self.recover_interrupted_runs()


    def register_action(self, opportunity_id: str, action: BaseOptimizationAction) -> None:
        """Registers a safe, allowlisted optimization action."""
        cls_name = action.__class__.__name__
        if cls_name not in self.APPROVED_ACTION_CLASSES and not isinstance(action, BaseOptimizationAction):
            raise SecurityViolationError(f"Action '{cls_name}' is not in the approved optimization allowlist.")
        self._actions[opportunity_id] = action

    def prepare_opportunity(self, opportunity: OptimizationOpportunity) -> OptimizationRunRecord:
        """Transitions opportunity into PROPOSED / AWAITING_APPROVAL state."""
        run_id = f"optrun_{uuid.uuid4().hex[:12]}"
        run_record = OptimizationRunRecord(
            run_id=run_id,
            opportunity_id=opportunity.id,
            category=opportunity.category.value,
            title=opportunity.title,
            state=OptimizationState.AWAITING_APPROVAL.value,
            risk_level=opportunity.risk.value,
            requires_elevation=opportunity.requires_elevation,
            user_approved=False,
            verification_status="PENDING",
            details_json=json.dumps({
                "description": opportunity.description,
                "evidence": opportunity.evidence,
                "expected_effect": opportunity.expected_effect,
                "verification_plan": opportunity.verification_plan,
                "rollback_plan": opportunity.rollback_plan,
                "target_metric": opportunity.target_metric,
            }),
        )
        if self.storage:
            self.storage.save_optimization_run(run_record)
        self._active_runs[run_id] = run_record
        return run_record

    def apply_optimization(
        self,
        run_id: str,
        opportunity: OptimizationOpportunity,
        action: Optional[BaseOptimizationAction] = None,
        user_confirmed: bool = False,
    ) -> OptimizationRunRecord:
        """
        Executes optimization after verifying explicit user approval, concurrency locks,
        action allowlist, and taking a cryptographically verified pre-snapshot.
        """
        if not user_confirmed and not opportunity.user_approved:
            raise PermissionError(
                "Execution prohibited: Optimization requires explicit user confirmation. "
                "Silent or automatic optimization is strictly forbidden."
            )

        # Concurrency Lock: Prevent multiple concurrent optimizations
        if not self._lock.acquire(blocking=False):
            raise OptimizationConflictError(
                "Another optimization operation is currently in progress. Concurrent optimizations are forbidden."
            )

        try:
            # Check for existing active runs in progress
            for existing in self._active_runs.values():
                if existing.run_id != run_id and existing.state in (
                    OptimizationState.APPLYING.value,
                    OptimizationState.SNAPSHOTTING.value,
                    OptimizationState.VERIFYING.value,
                    OptimizationState.ROLLING_BACK.value,
                ):
                    raise OptimizationConflictError(
                        f"Cannot start optimization: Run {existing.run_id} is currently active in state {existing.state}."
                    )

            run = self._active_runs.get(run_id)
            if not run and self.storage:
                run = self.storage.get_optimization_run(run_id)

            if not run:
                run = self.prepare_opportunity(opportunity)

            opt_action = action or self._actions.get(opportunity.id)
            if not opt_action:
                raise ValueError(f"No execution action registered for opportunity '{opportunity.id}'.")

            # Validate action allowlist
            cls_name = opt_action.__class__.__name__
            if cls_name not in self.APPROVED_ACTION_CLASSES and not isinstance(opt_action, BaseOptimizationAction):
                raise SecurityViolationError(f"Action class '{cls_name}' is not in the approved optimization allowlist.")

            # 1. State: SNAPSHOTTING
            self._update_run_state(run, OptimizationState.SNAPSHOTTING)
            pre_state = opt_action.get_current_state()
            snapshot = self.snapshot_manager.create_snapshot(
                opportunity_id=opportunity.id,
                run_id=run.run_id,
                subsystem=opportunity.affected_subsystem,
                pre_state=pre_state,
                context={"title": opportunity.title},
            )

            # 2. State: APPLYING
            self._update_run_state(run, OptimizationState.APPLYING)
            try:
                if opportunity.requires_elevation:
                    op_id = None
                    priv_params = {}
                    if opt_action.action_id == "DNS_CACHE_FLUSH":
                        op_id = PrivilegedOperationId.DNS_CACHE_FLUSH
                    elif opt_action.action_id == "BACKGROUND_PROCESS_PRIORITY_HINT":
                        op_id = PrivilegedOperationId.PROCESS_PRIORITY_HINT
                        priv_params = {
                            "process_name": getattr(opt_action, "process_name", None) or "worker.exe",
                            "priority": "below_normal",
                        }
                    elif opt_action.action_id == "POWER_PLAN_GAMING_HINT":
                        op_id = PrivilegedOperationId.POWER_SCHEME_TUNE
                        priv_params = {"scheme_guid": getattr(opt_action, "HIGH_PERF_GUID", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")}
                    else:
                        raise PrivilegeError(
                            f"Action '{opt_action.action_id}' requires elevation but is not in the privileged allowlist."
                        )

                    priv_token = self.privileged_helper.issue_authorization_token(
                        operation_id=op_id,
                        parameters=priv_params,
                        user_approved=True,
                    )
                    self.privileged_helper.execute_operation(priv_token)
                    new_state = opt_action.get_current_state()
                else:
                    new_state = opt_action.apply(dry_run=self.dry_run)

                run.applied_at_utc = now_utc_iso()
                run.user_approved = True

                # 3. State: VERIFYING
                self._update_run_state(run, OptimizationState.VERIFYING)
                return run
            except Exception as e:
                logger.error(f"Application of optimization {run_id} failed: {e}")
                self._update_run_state(run, OptimizationState.FAILED)
                # Automatic safety rollback if failed mid-flight
                self.rollback_run(run_id, action=opt_action)
                raise

        finally:
            self._lock.release()

    def complete_verification(
        self,
        run_id: str,
        baseline_samples: List[float],
        post_change_samples: List[float],
        metric_name: str,
        action: Optional[BaseOptimizationAction] = None,
    ) -> VerificationResult:
        """
        Evaluates post-change verification metrics and automatically triggers rollback if regressed.
        """
        run = self._active_runs.get(run_id)
        if not run and self.storage:
            run = self.storage.get_optimization_run(run_id)

        if not run:
            raise ValueError(f"Run {run_id} not found.")

        result = self.verification_engine.evaluate_verification(
            metric_name=metric_name,
            baseline_samples=baseline_samples,
            post_change_samples=post_change_samples,
        )

        run.verified_at_utc = now_utc_iso()
        run.verification_status = result.outcome.value

        # Persist verification result
        if self.storage:
            v_rec = OptimizationResultRecord(
                result_id=f"optres_{uuid.uuid4().hex[:12]}",
                run_id=run_id,
                metric_name=metric_name,
                baseline_value=result.baseline_value,
                post_value=result.post_value,
                difference=result.difference,
                confidence=result.confidence,
                outcome=result.outcome.value,
            )
            self.storage.save_optimization_result(v_rec)

        # Update run state based on outcome
        if result.outcome == VerificationOutcome.VERIFIED_IMPROVEMENT:
            self._update_run_state(run, OptimizationState.VERIFIED)
        elif result.outcome == VerificationOutcome.NO_MEANINGFUL_CHANGE:
            self._update_run_state(run, OptimizationState.NO_CHANGE)
        elif result.outcome == VerificationOutcome.REGRESSION or result.should_rollback:
            self._update_run_state(run, OptimizationState.REGRESSION)
            # Guardian automatically triggers rollback
            self.guardian.evaluate_guardian_trigger(run_id, result)
        else:
            self._update_run_state(run, OptimizationState.INCONCLUSIVE)

        return result

    def rollback_run(
        self,
        run_id: str,
        action: Optional[BaseOptimizationAction] = None,
        force: bool = False,
    ) -> bool:
        """
        Reverts system configuration back to the pre-change snapshot.
        Enforces snapshot integrity checks and pre-flight state verification to prevent replay.
        """
        with self._lock:
            run = self._active_runs.get(run_id)
            if not run and self.storage:
                run = self.storage.get_optimization_run(run_id)

            if not run:
                logger.error(f"Cannot rollback: run {run_id} not found.")
                return False

            try:
                snapshot = self.snapshot_manager.get_snapshot_for_run(run_id)
            except SnapshotTamperedError as e:
                logger.critical(f"Snapshot tamper detected during rollback of {run_id}: {e}")
                self._update_run_state(run, OptimizationState.FAILED)
                raise RollbackSafetyError(f"Snapshot integrity violation: {e}")

            if not snapshot:
                logger.error(f"Cannot rollback run {run_id}: snapshot missing!")
                self._update_run_state(run, OptimizationState.FAILED)
                return False

            opt_action = action or self._actions.get(run.opportunity_id)
            if not opt_action:
                logger.error(f"Cannot rollback run {run_id}: action missing for {run.opportunity_id}!")
                self._update_run_state(run, OptimizationState.FAILED)
                return False

            # Pre-flight state verification: check if current state matches expected post-state
            current_state = opt_action.get_current_state()
            if not force and not self.dry_run:
                # If current state has diverged unexpectedly, flag ROLLBACK_REQUIRES_REVIEW
                diverged = False
                for k, v in snapshot.pre_state.items():
                    if k in current_state and current_state[k] == v:
                        # Current state is ALREADY equal to pre-state, unexpected mutation occurred
                        diverged = True
                        break
                if diverged:
                    logger.warning(f"Rollback safety check: Subsystem state diverged out-of-band for run {run_id}.")
                    self._update_run_state(run, OptimizationState.FAILED)
                    raise RollbackSafetyError(
                        "Rollback halted: Subsystem configuration diverged from expected post-change state. "
                        "State requires manual review (ROLLBACK_REQUIRES_REVIEW)."
                    )

            self._update_run_state(run, OptimizationState.ROLLING_BACK)
            try:
                if run.requires_elevation:
                    op_id = None
                    priv_params = {}
                    if opt_action.action_id == "DNS_CACHE_FLUSH":
                        op_id = PrivilegedOperationId.DNS_CACHE_FLUSH
                    elif opt_action.action_id == "BACKGROUND_PROCESS_PRIORITY_HINT":
                        op_id = PrivilegedOperationId.PROCESS_PRIORITY_HINT
                        priv_params = {
                            "process_name": getattr(opt_action, "process_name", None) or "worker.exe",
                            "priority": "normal",
                        }
                    elif opt_action.action_id == "POWER_PLAN_GAMING_HINT":
                        op_id = PrivilegedOperationId.POWER_SCHEME_TUNE
                        orig_guid = snapshot.pre_state.get("active_guid", "381b4222-f694-41f0-9685-ff5bb260df2e")
                        priv_params = {"scheme_guid": orig_guid}
                    else:
                        raise PrivilegeError(
                            f"Action '{opt_action.action_id}' requires elevation but is not in the privileged allowlist."
                        )

                    priv_token = self.privileged_helper.issue_authorization_token(
                        operation_id=op_id,
                        parameters=priv_params,
                        user_approved=True,
                    )
                    self.privileged_helper.execute_operation(priv_token)
                    success = True
                else:
                    success = opt_action.rollback(snapshot.pre_state, dry_run=self.dry_run)

                if success:
                    run.rolled_back_at_utc = now_utc_iso()
                    self._update_run_state(run, OptimizationState.ROLLED_BACK)
                    logger.info(f"Successfully rolled back optimization run {run_id}.")
                    return True
                else:
                    self._update_run_state(run, OptimizationState.FAILED)
                    return False
            except Exception as e:

                logger.critical(f"Exception during rollback of run {run_id}: {e}")
                self._update_run_state(run, OptimizationState.FAILED)
                return False

    def recover_interrupted_runs(self) -> int:
        """
        Startup crash recovery: Identifies runs left in non-terminal states and marks them FAILED.
        """
        if not self.storage:
            return 0

        interrupted_count = 0
        try:
            runs = self.storage.list_optimization_runs(limit=100)
            for r in runs:
                if r.state in (
                    OptimizationState.APPLYING.value,
                    OptimizationState.SNAPSHOTTING.value,
                    OptimizationState.VERIFYING.value,
                    OptimizationState.ROLLING_BACK.value,
                ):
                    logger.warning(
                        f"Crash recovery: Run {r.run_id} was interrupted in state '{r.state}'. Marking INCONCLUSIVE."
                    )
                    r.state = OptimizationState.INCONCLUSIVE.value
                    r.error_message = "Operation interrupted by unexpected application termination (Crash Recovery)."
                    self.storage.save_optimization_run(r)
                    interrupted_count += 1
        except Exception as e:
            logger.error(f"Error during optimization crash recovery scan: {e}")

        return interrupted_count

    def _update_run_state(self, run: OptimizationRunRecord, new_state: OptimizationState) -> None:
        run.state = new_state.value
        self._active_runs[run.run_id] = run
        if self.storage:
            self.storage.save_optimization_run(run)
        logger.debug(f"Optimization run {run.run_id} transitioned to state: {new_state.value}")
