"""
Stage 5 Unit Tests: Safe Optimization Engine, Rollback Guardian & A/B Testing.
Verifies explicit user approval, pre-change snapshot privacy, state machine integrity,
verification analysis, automatic rollback guardian, A/B confounder filtering, and crash recovery.
"""
from pathlib import Path
import tempfile
import unittest

from analyzer.contracts import DetailedIncident, IncidentSeverity, IncidentStatus, IncidentType
from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from optimization.ab_testing import OptimizationABTestingEngine
from optimization.actions import BaseOptimizationAction
from optimization.contracts import (
    OptimizationCategory,
    OptimizationOpportunity,
    OptimizationRiskLevel,
    OptimizationState,
    VerificationOutcome,
)
from optimization.executor import OptimizationExecutor
from optimization.opportunities import OptimizationOpportunityEngine
from optimization.snapshots import SnapshotManager
from optimization.verification import VerificationEngine
from storage.engine import StorageEngine


class MockOptimizationAction(BaseOptimizationAction):
    """Configurable mock action for deterministic testing."""

    def __init__(self, action_id: str = "mock_action", fail_apply: bool = False, fail_rollback: bool = False):
        self._action_id = action_id
        self.fail_apply = fail_apply
        self.fail_rollback = fail_rollback
        self.applied = False
        self.rolled_back = False

    @property
    def action_id(self) -> str:
        return self._action_id

    def get_current_state(self):
        return {"setting_x": "value_original", "metric_y": 100}

    def apply(self, dry_run: bool = False):
        if self.fail_apply:
            raise RuntimeError("Simulated action failure")
        self.applied = True
        return {"setting_x": "value_optimized", "metric_y": 80}

    def rollback(self, snapshot_pre_state, dry_run: bool = False):
        if self.fail_rollback:
            return False
        self.rolled_back = True
        return True


class TestOptimizationEngine(unittest.TestCase):
    """Tests optimization safety, verification, rollback guardian, and A/B testing."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_opt.sqlite")
        self.storage = StorageEngine(self.db_path)
        self.snapshot_manager = SnapshotManager(storage=self.storage)
        self.verification_engine = VerificationEngine()
        self.executor = OptimizationExecutor(
            storage=self.storage,
            snapshot_manager=self.snapshot_manager,
            verification_engine=self.verification_engine,
            dry_run=True,
        )
        self.opp_engine = OptimizationOpportunityEngine()
        self.ab_engine = OptimizationABTestingEngine()

    def tearDown(self):
        self.storage.sqlite.close()
        self.temp_dir.cleanup()

    def test_opportunity_generation_requires_evidence(self):
        # Empty observation produces 0 opportunities
        opps = self.opp_engine.evaluate_opportunities({})
        self.assertEqual(len(opps), 0)

        # High DNS latency produces DNS cache flush opportunity
        obs = Observation(
            observation_id="obs_dns",
            timestamp_utc="2026-09-28T12:00:00Z",
            collector_name="net",
            measurements={
                "dns_latency_ms": Measurement("dns_latency_ms", MetricState.AVAILABLE, 140.0, MetricUnit.MILLISECONDS, "c", "p")
            },
            collector_healthy=True,
        )
        opps = self.opp_engine.evaluate_opportunities({"internet": obs})
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps[0].id, "opp_dns_flush")
        self.assertEqual(opps[0].risk, OptimizationRiskLevel.SAFE)
        self.assertTrue(opps[0].reversible)
        self.assertGreater(len(opps[0].evidence), 0)

    def test_snapshot_privacy_rejection(self):
        # Must reject sensitive keys
        with self.assertRaises(ValueError):
            self.snapshot_manager.create_snapshot(
                opportunity_id="test",
                run_id="run1",
                subsystem="network",
                pre_state={"user_token": "secret_abc123"},
            )

        with self.assertRaises(ValueError):
            self.snapshot_manager.create_snapshot(
                opportunity_id="test",
                run_id="run1",
                subsystem="network",
                pre_state={"password": "mypassword"},
            )

    def test_unapproved_optimization_strictly_prohibited(self):
        opp = OptimizationOpportunity(
            id="opp_test",
            title="Test Opp",
            description="desc",
            category=OptimizationCategory.SYSTEM,
            evidence=["high cpu"],
            affected_subsystem="cpu",
            risk=OptimizationRiskLevel.SAFE,
            expected_effect="boost",
            confidence=0.9,
            current_state={},
            proposed_state={},
            reversible=True,
            user_approved=False,  # Unapproved!
        )
        run_rec = self.executor.prepare_opportunity(opp)
        mock_action = MockOptimizationAction("opp_test")

        with self.assertRaises(PermissionError):
            self.executor.apply_optimization(run_rec.run_id, opp, action=mock_action, user_confirmed=False)

    def test_happy_path_approval_snapshot_apply_verify(self):
        opp = OptimizationOpportunity(
            id="opp_happy",
            title="Safe Network Tuning",
            description="desc",
            category=OptimizationCategory.NETWORK,
            evidence=["latency 120ms"],
            affected_subsystem="network",
            risk=OptimizationRiskLevel.SAFE,
            expected_effect="lower latency",
            confidence=0.88,
            current_state={"latency": 120},
            proposed_state={"latency": 60},
            reversible=True,
            target_metric="latency",
            user_approved=True,
        )
        mock_action = MockOptimizationAction("opp_happy")
        self.executor.register_action("opp_happy", mock_action)

        run = self.executor.apply_optimization("run_happy", opp, action=mock_action, user_confirmed=True)
        self.assertEqual(run.state, OptimizationState.VERIFYING.value)
        self.assertTrue(mock_action.applied)

        # Verify pre-change snapshot was persisted
        snap = self.snapshot_manager.get_snapshot_for_run(run.run_id)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.pre_state["setting_x"], "value_original")

        # Run verification with improvement
        v_res = self.executor.complete_verification(
            run_id=run.run_id,
            baseline_samples=[120.0, 122.0, 118.0],
            post_change_samples=[75.0, 72.0, 74.0],
            metric_name="latency",
            action=mock_action,
        )
        self.assertEqual(v_res.outcome, VerificationOutcome.VERIFIED_IMPROVEMENT)
        self.assertFalse(v_res.should_rollback)

        updated_run = self.storage.get_optimization_run(run.run_id)
        self.assertEqual(updated_run.state, OptimizationState.VERIFIED.value)

    def test_regression_triggers_automatic_rollback_guardian(self):
        opp = OptimizationOpportunity(
            id="opp_regress",
            title="Aggressive Tuning",
            description="desc",
            category=OptimizationCategory.SYSTEM,
            evidence=["cpu test"],
            affected_subsystem="cpu",
            risk=OptimizationRiskLevel.RECOMMENDED,
            expected_effect="boost",
            confidence=0.8,
            current_state={},
            proposed_state={},
            reversible=True,
            target_metric="latency",
            user_approved=True,
        )
        mock_action = MockOptimizationAction("opp_regress")
        self.executor.register_action("opp_regress", mock_action)

        run = self.executor.apply_optimization("run_regress", opp, action=mock_action, user_confirmed=True)

        # Post-change measurements show severe regression: latency jumped from 40 to 80 (+100%)
        v_res = self.executor.complete_verification(
            run_id=run.run_id,
            baseline_samples=[40.0, 42.0, 39.0],
            post_change_samples=[82.0, 85.0, 80.0],
            metric_name="latency",
            action=mock_action,
        )
        self.assertEqual(v_res.outcome, VerificationOutcome.REGRESSION)
        self.assertTrue(v_res.should_rollback)
        # Rollback action must have been invoked automatically by Guardian
        self.assertTrue(mock_action.rolled_back)

        updated_run = self.storage.get_optimization_run(run.run_id)
        self.assertEqual(updated_run.state, OptimizationState.ROLLED_BACK.value)

    def test_ab_testing_confounder_detection(self):
        # Experiment with identical game and workload
        res_clean = self.ab_engine.evaluate_experiment(
            opportunity_id="opp_1",
            metric_name="latency",
            baseline_samples=[50.0, 52.0],
            test_samples=[40.0, 38.0],
            external_context_pre={"game_name": "CS2", "background_cpu_pct": 5.0},
            external_context_post={"game_name": "CS2", "background_cpu_pct": 6.0},
        )
        self.assertEqual(res_clean.final_verdict, "VERIFIED_IMPROVEMENT")
        self.assertFalse(res_clean.confounders.confounder_detected)

        # Experiment with Confounder: Background workload jumped by 40%
        res_confounded = self.ab_engine.evaluate_experiment(
            opportunity_id="opp_1",
            metric_name="latency",
            baseline_samples=[50.0, 52.0],
            test_samples=[75.0, 78.0],
            external_context_pre={"game_name": "CS2", "background_cpu_pct": 5.0},
            external_context_post={"game_name": "CS2", "background_cpu_pct": 45.0},
        )
        self.assertEqual(res_confounded.final_verdict, "INCONCLUSIVE")
        self.assertTrue(res_confounded.confounders.confounder_detected)
        self.assertIn("BACKGROUND_WORKLOAD_SHIFT", res_confounded.confounders.confounder_names)

    def test_crash_recovery_cleans_transient_states(self):
        # Insert a run stuck in APPLYING state (as if power cut happened)
        from storage.contracts import OptimizationRunRecord
        stuck_run = OptimizationRunRecord(
            run_id="stuck_1",
            opportunity_id="opp_stuck",
            category="SYSTEM",
            title="Stuck Run",
            state=OptimizationState.APPLYING.value,
            risk_level="SAFE",
            requires_elevation=False,
            user_approved=True,
            verification_status="PENDING",
            details_json="{}",
        )
        self.storage.save_optimization_run(stuck_run)

        recovered_count = self.executor.recover_interrupted_runs()
        self.assertGreaterEqual(recovered_count, 1)

        run_after = self.storage.get_optimization_run("stuck_1")
        self.assertEqual(run_after.state, OptimizationState.INCONCLUSIVE.value)


if __name__ == "__main__":
    unittest.main()
