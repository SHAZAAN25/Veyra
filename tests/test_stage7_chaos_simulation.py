"""
VEYRA Automated Tests — Stage 7 Chaos Simulation Engine
Tests the core orchestration, lifecycle, and reporting of the chaos simulation framework.
"""

import unittest
import time
import uuid

from simulation.contracts import (
    ChaosExperiment,
    ChaosReport,
    ChaosStatus,
    FaultScenario,
    FaultType,
    SimulationTarget,
)
from simulation.chaos_engine import ChaosEngine


class TestStage7ChaosSimulation(unittest.TestCase):
    """Verifies the chaos orchestration engine, lifecycle transitions, and reports."""

    def setUp(self) -> None:
        self.engine = ChaosEngine()

    def test_chaos_experiment_registration_and_execution(self) -> None:
        """Register and execute a valid chaos experiment."""
        exp_id = "test_exp_001"
        scenario = FaultScenario(
            target=SimulationTarget.PROCESS_COORDINATOR,
            fault_type=FaultType.SUBPROCESS_CRASH,
            description="Test process crash fault scenario"
        )
        experiment = ChaosExperiment(
            experiment_id=exp_id,
            name="Process Crash Verification",
            description="Simulates unexpected coordinator thread failure",
            scenario=scenario
        )
        self.engine.register_experiment(experiment)

        def mock_injection() -> ChaosReport:
            return ChaosReport(
                experiment_id=exp_id,
                target=SimulationTarget.PROCESS_COORDINATOR,
                fault_type=FaultType.SUBPROCESS_CRASH,
                status=ChaosStatus.PASSED,
                system_degraded_gracefully=True,
                recovered_cleanly=True,
                duration_ms=12.5,
                assertions_evaluated=2,
                assertions_passed=2,
                telemetry_isolated=True,
                details={"verified": True}
            )

        report = self.engine.run_experiment(exp_id, mock_injection)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.passed)
        self.assertTrue(report.telemetry_isolated)
        self.assertTrue(report.system_degraded_gracefully)
        self.assertTrue(report.recovered_cleanly)
        self.assertEqual(experiment.status, ChaosStatus.PASSED)

    def test_chaos_experiment_failure_handling(self) -> None:
        """Ensure exceptions inside injection functions are caught and reported cleanly."""
        exp_id = "test_exp_fail_002"
        scenario = FaultScenario(
            target=SimulationTarget.GPU_COLLECTOR,
            fault_type=FaultType.SUBPROCESS_CRASH,
            description="Simulates crashing GPU collector"
        )
        experiment = ChaosExperiment(
            experiment_id=exp_id,
            name="Crashing Collector",
            description="Expects exception handling",
            scenario=scenario
        )
        self.engine.register_experiment(experiment)

        def exploding_injection() -> ChaosReport:
            raise RuntimeError("Fatal simulated crash inside injector")

        report = self.engine.run_experiment(exp_id, exploding_injection)
        self.assertEqual(report.status, ChaosStatus.ERROR)
        self.assertFalse(report.passed)
        self.assertIn("Fatal simulated crash", str(report.error_message))
        self.assertEqual(experiment.status, ChaosStatus.ERROR)

    def test_summary_report_aggregation(self) -> None:
        """Ensure aggregate summary accurately counts total, passed, failed, and isolated metrics."""
        for i in range(3):
            exp_id = f"exp_batch_{i}"
            exp = ChaosExperiment(
                experiment_id=exp_id,
                name=f"Batch {i}",
                description="Testing",
                scenario=FaultScenario(
                    target=SimulationTarget.API_SERVER,
                    fault_type=FaultType.RATE_LIMIT_FLOOD,
                    description="Flood"
                )
            )
            self.engine.register_experiment(exp)

            passed = (i != 1)  # 2 pass, 1 fails
            def make_fn(is_pass: bool):
                return lambda: ChaosReport(
                    experiment_id=exp_id,
                    target=SimulationTarget.API_SERVER,
                    fault_type=FaultType.RATE_LIMIT_FLOOD,
                    status=ChaosStatus.PASSED if is_pass else ChaosStatus.FAILED,
                    system_degraded_gracefully=True,
                    recovered_cleanly=True,
                    duration_ms=5.0,
                    assertions_evaluated=1,
                    assertions_passed=1 if is_pass else 0,
                    telemetry_isolated=True
                )

            self.engine.run_experiment(exp_id, make_fn(passed))

        summary = self.engine.get_summary_report()
        self.assertEqual(summary["total_experiments"], 3)
        self.assertEqual(summary["passed"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["telemetry_isolated_count"], 3)
        self.assertFalse(summary["all_passed"])

    def test_chaos_experiment_timeout_enforcement(self) -> None:
        """Ensure long-running or hanging scenarios transition to TIMED_OUT."""
        exp_id = "test_exp_timeout_003"
        exp = ChaosExperiment(
            experiment_id=exp_id,
            name="Hanging Experiment",
            description="Simulates scenario timeout",
            scenario=FaultScenario(
                target=SimulationTarget.GPU_COLLECTOR,
                fault_type=FaultType.SUBPROCESS_TIMEOUT,
                description="Timeout"
            )
        )
        self.engine.register_experiment(exp)

        def hanging_injection() -> ChaosReport:
            time.sleep(0.05)
            return ChaosReport(
                experiment_id=exp_id,
                target=SimulationTarget.GPU_COLLECTOR,
                fault_type=FaultType.SUBPROCESS_TIMEOUT,
                status=ChaosStatus.PASSED,
                system_degraded_gracefully=True,
                recovered_cleanly=True,
                duration_ms=50.0,
                assertions_evaluated=1,
                assertions_passed=1,
                telemetry_isolated=True
            )

        report = self.engine.run_experiment(exp_id, hanging_injection, timeout_seconds=0.01)
        self.assertEqual(report.status, ChaosStatus.TIMED_OUT)
        self.assertEqual(exp.status, ChaosStatus.TIMED_OUT)

    def test_chaos_experiment_abort(self) -> None:
        """Ensure scenarios can be safely aborted on demand."""
        exp_id = "test_exp_abort_004"
        exp = ChaosExperiment(
            experiment_id=exp_id,
            name="Aborted Experiment",
            description="Simulates scenario abort",
            scenario=FaultScenario(
                target=SimulationTarget.STORAGE_ENGINE,
                fault_type=FaultType.DISK_IO_ERROR,
                description="Abort"
            )
        )
        self.engine.register_experiment(exp)
        report = self.engine.abort_experiment(exp_id, reason="Emergency safety stop")
        self.assertEqual(report.status, ChaosStatus.ABORTED)
        self.assertEqual(exp.status, ChaosStatus.ABORTED)
        self.assertIn("Emergency safety stop", str(report.error_message))

    def test_simulation_data_isolation_enforcement(self) -> None:
        """Phase 19: Prove simulation measurements cannot masquerade as production data."""
        from simulation.contracts import SimulatedMeasurement, SimulatedObservation, is_simulation_payload
        sim_meas = SimulatedMeasurement(metric_name="gpu_temp_c", value=999.0, unit="C")
        self.assertTrue(sim_meas.is_simulation)
        self.assertEqual(sim_meas.provenance, "synthetic:chaos")
        self.assertTrue(is_simulation_payload(sim_meas))

        sim_obs = SimulatedObservation(observation_id="sim_obs_01", collector_name="chaos_gpu", measurements={"gpu_temp": sim_meas})
        self.assertTrue(sim_obs.is_simulation)
        self.assertTrue(is_simulation_payload(sim_obs))


if __name__ == "__main__":
    unittest.main()

