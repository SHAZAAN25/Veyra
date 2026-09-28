"""
VEYRA Automated Tests — Stage 7 Fault Injection & Resilience
Tests simulated failures in GPU, storage, process concurrency, system clock, and network layers.
"""

import unittest
import tempfile
import os
import shutil
import sqlite3
from unittest.mock import MagicMock

from simulation.fault_injectors import (
    GpuFaultInjector,
    StorageFaultInjector,
    ProcessFaultInjector,
    TimeChaosInjector,
)
from simulation.network_chaos import NetworkChaosSimulator
from simulation.contracts import ChaosStatus, SimulationTarget, FaultType
from collectors.gpu import GpuCollector
from storage.engine import StorageEngine
from storage.sqlite_engine import SqliteStorageEngine
from optimization.executor import OptimizationExecutor
from optimization.contracts import OptimizationOpportunity, OptimizationRiskLevel, OptimizationCategory
from app.core.time import TimeTracker


class TestStage7FaultInjection(unittest.TestCase):
    """Verifies that all fault injectors trigger graceful degradation and clean recovery."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_faults.db")
        self.storage = SqliteStorageEngine(db_path=self.db_path)

    def tearDown(self) -> None:
        self.storage.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_gpu_fault_injection_subprocess_timeout(self) -> None:
        """Simulate GPU subprocess timeout; asserts graceful degradation to UNAVAILABLE."""
        collector = GpuCollector()
        report = GpuFaultInjector.inject_subprocess_timeout(collector)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)
        self.assertTrue(report.telemetry_isolated)
        self.assertEqual(report.target, SimulationTarget.GPU_COLLECTOR)

    def test_gpu_fault_injection_corrupted_output(self) -> None:
        """Simulate corrupted nvidia-smi output; asserts zero fabricated metrics."""
        collector = GpuCollector()
        report = GpuFaultInjector.inject_corrupted_output(collector)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)
        self.assertTrue(report.telemetry_isolated)

    def test_storage_fault_injection_disk_full(self) -> None:
        """Simulate disk I/O error; asserts degradation and health recovery."""
        report = StorageFaultInjector.inject_disk_full_error(self.storage)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)
        self.assertTrue(report.recovered_cleanly)
        self.assertTrue(report.telemetry_isolated)

    def test_storage_fault_injection_database_corruption(self) -> None:
        """Simulate SQLite corruption; asserts integrity check flags error."""
        report = StorageFaultInjector.inject_database_corruption(self.storage)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)
        self.assertTrue(report.telemetry_isolated)

    def test_process_fault_injection_crash_recovery(self) -> None:
        """Simulate process termination during APPLYING; asserts startup crash recovery to INCONCLUSIVE."""
        executor = OptimizationExecutor(storage=self.storage, dry_run=True)
        report = ProcessFaultInjector.inject_interrupted_optimization_run(executor, self.storage)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)
        self.assertTrue(report.recovered_cleanly)

    def test_process_fault_injection_concurrency_race(self) -> None:
        """Simulate rapid concurrent optimization invocations; asserts race condition prevention."""
        executor = OptimizationExecutor(storage=self.storage, dry_run=True)
        opportunity = OptimizationOpportunity(
            id="opp_sim_race",
            title="Concurrent Race Opportunity",
            description="Testing concurrency",
            category=OptimizationCategory.NETWORK,
            evidence=["High latency"],
            affected_subsystem="network",
            risk=OptimizationRiskLevel.SAFE,
            expected_effect="Faster connection",
            confidence=0.9,
            current_state={"cache_cleared": False},
            proposed_state={"cache_cleared": True},
            reversible=True,
            requires_elevation=False,
            verification_plan="Ping check",
            rollback_plan="Revert",
            target_metric="ping_latency",
            user_approved=True
        )
        report = ProcessFaultInjector.inject_concurrent_optimization_race(executor, opportunity)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)
        self.assertTrue(report.recovered_cleanly)

    def test_time_chaos_sleep_gap(self) -> None:
        """Simulate sleep/wake cycle; asserts sleep gap detection >15s."""
        tracker = TimeTracker()
        report = TimeChaosInjector.inject_sleep_gap(tracker, gap_seconds=45.0)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)

    def test_time_chaos_ntp_skew(self) -> None:
        """Simulate wall-clock jumping backwards 1 hour; asserts monotonic duration stability."""
        tracker = TimeTracker()
        report = TimeChaosInjector.inject_ntp_clock_skew(tracker, skew_offset=-3600.0)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)

    def test_network_chaos_bufferbloat(self) -> None:
        """Simulate bufferbloat surge; asserts incident detection and clean resolution."""
        report = NetworkChaosSimulator.simulate_bufferbloat_spike(tracker=None, peak_latency_ms=650.0)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)
        self.assertTrue(report.recovered_cleanly)

    def test_network_chaos_packet_loss(self) -> None:
        """Simulate 75% packet loss burst; asserts truthful non-fabrication and resolution."""
        report = NetworkChaosSimulator.simulate_packet_loss_burst(loss_rate=75.0)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)
        self.assertTrue(report.recovered_cleanly)

    def test_network_chaos_dns_blackhole(self) -> None:
        """Simulate DNS blackhole; asserts distinct DNS layer attribution vs gateway."""
        investigator = MagicMock()
        report = NetworkChaosSimulator.simulate_dns_blackhole_investigation(investigator)
        self.assertEqual(report.status, ChaosStatus.PASSED)
        self.assertTrue(report.system_degraded_gracefully)

    def test_simulation_data_contamination_rejected(self) -> None:
        """Phase 19: Assert that simulated observations are strictly blocked from production persistence."""
        from simulation.contracts import SimulatedObservation, SimulatedMeasurement
        sim_meas = SimulatedMeasurement(metric_name="latency_ms", value=500.0, unit="ms")
        sim_obs = SimulatedObservation(
            observation_id="sim_attempt_01",
            collector_name="network_chaos",
            measurements={"latency": sim_meas}
        )
        with self.assertRaises(ValueError) as ctx:
            self.storage.append_raw_observation(sim_obs)
        self.assertIn("Rule 9 Violation", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
