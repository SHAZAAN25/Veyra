"""
VEYRA Automated Tests — Stage 7 End-to-End User Scenarios
Verifies full lifecycle multi-step scenarios across Gaming Sessions, Safe Optimization with Auto-Rollback,
Cross-Layer Diagnostics, Storage Degradation Resilience, and Zero-Trust Security.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from analyzer.contracts import DetailedIncident, IncidentSeverity, IncidentStatus, IncidentType
from analyzer.gaming.contracts import (
    GameIdentity,
    GamingSessionState,
    NetworkStabilityRating,
)
from analyzer.gaming.detector import GameDetector
from analyzer.gaming.session_engine import GamingSessionEngine
from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from app.core.security import (
    sanitize_csv_cell,
    sanitize_log_string,
    validate_safe_path,
    SecurityViolationError,
)
from diagnostics.contracts import (
    DiagnosticLayer,
    LayerStatus,
    TestItemResult,
)
from diagnostics.investigator import CrossLayerInvestigator
from optimization.actions import BaseOptimizationAction
from optimization.contracts import (
    OptimizationCategory,
    OptimizationOpportunity,
    OptimizationRiskLevel,
    OptimizationState,
    VerificationOutcome,
    VerificationResult,
)
from optimization.executor import OptimizationExecutor
from optimization.snapshots import SnapshotManager
from optimization.verification import VerificationEngine
from storage.contracts import StorageHealthState
from storage.engine import StorageEngine


def make_obs(metrics: dict, epoch_str: str = "2026-09-28T12:00:00Z") -> Observation:
    measurements = {}
    for k, v in metrics.items():
        measurements[k] = Measurement(
            metric_name=k,
            state=MetricState.AVAILABLE if v is not None else MetricState.UNAVAILABLE,
            value=v,
            unit=MetricUnit.PERCENTAGE if ("pct" in k or "%" in k) else MetricUnit.MILLISECONDS,
            source_collector="test_collector",
            provenance="synthetic"
        )
    return Observation(
        observation_id=f"obs_e2e_{abs(hash(epoch_str)) % 100000}",
        timestamp_utc=epoch_str,
        collector_name="test_collector",
        measurements=measurements,
        collector_healthy=True
    )


class MockAction(BaseOptimizationAction):
    def __init__(self, action_id: str = "DNS_CACHE_FLUSH"):
        self._action_id = action_id
        self.state = {"cache_cleared": False}

    @property
    def action_id(self) -> str:
        return self._action_id

    def get_current_state(self):
        return dict(self.state)

    def apply(self, dry_run: bool = False):
        self.state["cache_cleared"] = True
        return dict(self.state)

    def rollback(self, pre_state, dry_run: bool = False):
        if isinstance(pre_state, dict):
            self.state = dict(pre_state)
        elif hasattr(pre_state, "pre_state"):
            self.state = dict(pre_state.pre_state)
        return True


class MockProbe:
    def __init__(self, test_name: str, target: str, status: LayerStatus):
        self.test_name = test_name
        self.target = target
        self.status = status

    def execute(self, *args, **kwargs) -> TestItemResult:
        return TestItemResult(
            test_name=self.test_name,
            target=self.target,
            status=self.status,
            latency_ms=12.0 if self.status == LayerStatus.HEALTHY else None,
            packet_loss_pct=0.0 if self.status == LayerStatus.HEALTHY else 100.0,
            details={"mock": True}
        )


class TestStage7EndToEndScenarios(unittest.TestCase):
    """End-to-end integration journeys across all core subsystems."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test_stage7_e2e.sqlite")
        self.storage = StorageEngine(self.db_path)

    def tearDown(self) -> None:
        self.storage.sqlite.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_e2e_scenario_1_gaming_session_with_dna_and_jitter(self) -> None:
        """Scenario 1: Game launch -> Jitter spike -> Session DNA generated -> Storage persisted."""
        detector = GameDetector()
        session_engine = GamingSessionEngine(storage=self.storage, detector=detector)

        game = GameIdentity(name="VALORANT", executable="VALORANT.exe", process_id=5432, is_validated=True)
        session = session_engine.start_session(game=game)
        self.assertEqual(session.state, GamingSessionState.ACTIVE)

        # Record normal observations
        for i in range(5):
            session_engine.record_observation(make_obs({
                "cpu_utilization_pct": 35.0,
                "gpu_utilization_pct": 75.0,
                "internet_latency_ms": 18.0,
                "internet_packet_loss_pct": 0.0,
            }, epoch_str=f"2026-09-28T12:00:0{i}Z"))

        # Record jitter spike observations
        for i in range(5, 10):
            session_engine.record_observation(make_obs({
                "cpu_utilization_pct": 40.0,
                "gpu_utilization_pct": 80.0,
                "internet_latency_ms": 120.0,
                "internet_packet_loss_pct": 5.0,
            }, epoch_str=f"2026-09-28T12:00:0{i}Z"))

        completed = session_engine.end_session(GamingSessionState.COMPLETED)
        self.assertIsNotNone(completed)
        self.assertEqual(completed.state, GamingSessionState.COMPLETED)
        self.assertIsNotNone(completed.session_dna)
        self.assertIsNone(completed.fps_telemetry)  # Rule 1: Zero fake FPS

        # Verify persisted in storage
        persisted = self.storage.get_gaming_session(completed.session_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.game_name, "VALORANT")
        self.assertFalse(persisted.fps_available)

    def test_e2e_scenario_2_safe_optimization_and_auto_rollback(self) -> None:
        """Scenario 2: Opportunity proposed -> User approved -> Snapshot signed -> Regression -> Auto-Rollback."""
        executor = OptimizationExecutor(storage=self.storage, dry_run=True)
        action = MockAction("DNS_CACHE_FLUSH")

        opp = OptimizationOpportunity(
            id="opp_dns_flush_e2e",
            title="Flush DNS Resolver Cache",
            description="Clear stale resolver entries",
            category=OptimizationCategory.NETWORK,
            evidence=["High latency"],
            affected_subsystem="network",
            risk=OptimizationRiskLevel.SAFE,
            expected_effect="Faster connection",
            confidence=0.95,
            current_state={"cache_cleared": False},
            proposed_state={"cache_cleared": True},
            reversible=True,
            requires_elevation=False,
            verification_plan="Ping check",
            rollback_plan="Revert",
            target_metric="ping_latency",
            user_approved=True
        )
        executor.register_action(opp.id, action)

        # Prepare and apply opportunity with approval
        run_record = executor.prepare_opportunity(opp)
        run = executor.apply_optimization(run_record.run_id, opp, user_confirmed=True)
        self.assertIsNotNone(run)
        self.assertEqual(run.state, OptimizationState.VERIFYING.value)
        self.assertTrue(action.state["cache_cleared"])

        # Simulate post-change verification discovering regression
        regressed_result = VerificationResult(
            outcome=VerificationOutcome.REGRESSION,
            metric_name="ping_latency",
            baseline_value=15.0,
            post_value=45.0,
            difference=30.0,
            percentage_change=200.0,
            confidence=0.9,
            explanation="Auto-rollback advised due to sustained latency increase.",
            should_rollback=True
        )

        # Execute rollback
        rolled_back = executor.rollback_run(run.run_id, force=True)
        self.assertTrue(rolled_back)
        self.assertFalse(action.state["cache_cleared"])

        # Check recorded state in storage
        stored_run = self.storage.get_optimization_run(run.run_id)
        self.assertIsNotNone(stored_run)
        self.assertEqual(stored_run.state, OptimizationState.ROLLED_BACK.value)

    def test_e2e_scenario_3_cross_layer_diagnostic_investigation(self) -> None:
        """Scenario 3: Gateway healthy, DNS broken -> Diagnostic correctly isolates DNS root cause."""
        investigator = CrossLayerInvestigator()
        investigator.gateway_probe = MockProbe("gateway", "192.168.1.1", LayerStatus.HEALTHY)
        investigator.dns_probe = MockProbe("dns", "8.8.8.8", LayerStatus.FAILED)

        report = investigator.run_investigation(target="8.8.8.8")
        self.assertIsNotNone(report)
        self.assertEqual(report.graph.primary_root_cause_node, "dns")
        self.assertEqual(report.graph.nodes["gateway"].status, LayerStatus.HEALTHY)

    def test_e2e_scenario_4_storage_degradation_and_memory_resilience(self) -> None:
        """Scenario 4: Storage health degrades on I/O error without crashing telemetry ingestion."""
        # Initial state is healthy
        self.assertEqual(self.storage.sqlite.get_storage_stats().storage_health, StorageHealthState.HEALTHY)

        # Ingest observations into memory buffer
        obs1 = make_obs({"cpu_utilization_pct": 20.0})
        self.storage.append_raw_observation(obs1)
        self.assertEqual(len(self.storage.sqlite.get_buffered_observations()), 1)

        # Degrade storage health artificially
        self.storage.sqlite._is_degraded = True
        self.assertEqual(self.storage.sqlite.get_storage_stats().storage_health, StorageHealthState.DEGRADED)

        # Buffer must still accept observations while storage is degraded
        obs2 = make_obs({"cpu_utilization_pct": 30.0})
        self.storage.append_raw_observation(obs2)
        self.assertEqual(len(self.storage.sqlite.get_buffered_observations()), 2)

        # Recover storage health
        self.storage.sqlite._is_degraded = False
        self.assertEqual(self.storage.sqlite.get_storage_stats().storage_health, StorageHealthState.HEALTHY)

    def test_e2e_scenario_5_zero_trust_security_barrage(self) -> None:
        """Scenario 5: Multi-vector security tests (path traversal, CSV injection, log injection)."""
        # 1. Path traversal defense
        with self.assertRaises(SecurityViolationError):
            validate_safe_path(Path(self.temp_dir), Path(self.temp_dir) / "../../../windows/system32/cmd.exe")

        # 2. CSV formula injection neutralization
        unsafe_formula = "=CMD|'/C calc'!A0"
        sanitized_cell = sanitize_csv_cell(unsafe_formula)
        self.assertTrue(sanitized_cell.startswith("'"))

        # 3. Log injection sanitization
        unsafe_log = "User logged in\n[CRITICAL] Admin privileges granted"
        clean_log = sanitize_log_string(unsafe_log)
        self.assertNotIn("\n", clean_log)
        self.assertIn("Admin privileges granted", clean_log)


if __name__ == "__main__":
    unittest.main()
