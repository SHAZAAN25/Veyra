"""
Tests for VEYRA Central Intelligence Engine, Failure Isolation, AI Evidence, and Optimization Safety.
"""
import unittest
from unittest.mock import MagicMock

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from analyzer.contracts import IncidentType, IncidentSeverity, IncidentStatus, OptimizationCandidate
from analyzer.optimization.contracts import FutureOptimizationContract, OptimizationRiskLevel, OptimizationPrivilegeLevel
from analyzer.engine import IntelligenceEngine


class TestAnalyzerEngine(unittest.TestCase):
    def setUp(self):
        self.engine = IntelligenceEngine()

    def test_engine_process_cycle_healthy(self):
        # Empty or healthy observations
        report = self.engine.process_cycle({})
        self.assertEqual(report.overall_health, "HEALTHY")
        self.assertEqual(report.health_score, 100.0)
        self.assertEqual(len(report.active_incidents), 0)

    def test_engine_failure_isolation_on_subcomponent_error(self):
        # Break one subcomponent deliberately
        self.engine.incident_detector.evaluate_observations = MagicMock(side_effect=RuntimeError("Anomaly engine memory fault"))

        # Engine must NOT crash
        report = self.engine.process_cycle({})
        self.assertIsNotNone(report)
        self.assertEqual(report.overall_health, "HEALTHY")

    def test_sleep_gap_does_not_trigger_false_outage(self):
        # Simulate an observation cycle containing a sleep gap
        sleep_obs = {
            "self": Observation(
                "obs_self",
                "2026-09-28T00:00:00Z",
                "self",
                {"veyra_sleep_detected": Measurement("veyra_sleep_detected", MetricState.AVAILABLE, True, MetricUnit.BOOLEAN, "self", "test")},
                True
            )
        }
        report = self.engine.process_cycle(sleep_obs)
        # Sleep gap is flagged as INFO, never CRITICAL outage
        incident_types = [inc.incident_type for inc in report.active_incidents]
        if incident_types:
            self.assertIn(IncidentType.OBSERVATION_GAP_SLEEP_RESUME, incident_types)
            self.assertNotIn(IncidentType.INTERNET_UNREACHABLE, incident_types)
            self.assertNotIn(IncidentType.GATEWAY_UNREACHABLE, incident_types)

    def test_ai_evidence_package_strictly_grounded(self):
        report = self.engine.process_cycle({})
        self.assertIsNotNone(report.ai_evidence_package)
        pkg = report.ai_evidence_package
        self.assertIn("operating within established baseline", pkg.summary)
        self.assertEqual(len(pkg.active_incidents), 0)

    def test_future_optimization_safety_contracts(self):
        contract = FutureOptimizationContract(
            risk_level=OptimizationRiskLevel.SAFE,
            privilege_level=OptimizationPrivilegeLevel.STANDARD_USER,
            requires_user_approval=True,
            rollback_supported=True
        )
        self.assertTrue(contract.validate_safety_rules())

        # STRICT: Forbidden to bypass user approval or rollback support
        with self.assertRaises(ValueError):
            bad_contract = FutureOptimizationContract(
                risk_level=OptimizationRiskLevel.SAFE,
                privilege_level=OptimizationPrivilegeLevel.STANDARD_USER,
                requires_user_approval=False  # FORBIDDEN!
            )
            bad_contract.validate_safety_rules()

        # STRICT: Confirm NO execution methods exist on engine
        self.assertFalse(hasattr(self.engine, "apply_optimization"))
        self.assertFalse(hasattr(self.engine, "modify_registry"))
        self.assertFalse(hasattr(self.engine, "kill_process"))


if __name__ == "__main__":
    unittest.main()
