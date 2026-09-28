"""
Tests for VEYRA Collection Coordinator, Self-Monitoring, and Optimization Decoupling.
"""
import unittest
from unittest.mock import MagicMock

from app.core.contracts import MetricState
from collectors.coordinator import CollectionCoordinator


class TestCollectionCoordinator(unittest.TestCase):
    def test_coordinator_runs_cycle_live(self):
        coordinator = CollectionCoordinator()
        cycle = coordinator.run_cycle()

        self.assertIn("cpu", cycle)
        self.assertIn("memory", cycle)
        self.assertIn("disk", cycle)
        self.assertIn("self", cycle)

        self_obs = cycle["self"]
        self.assertTrue(self_obs.collector_healthy)
        self.assertIn("veyra_cycle_duration_ms", self_obs.measurements)
        self.assertIn("veyra_healthy_collectors_count", self_obs.measurements)
        self.assertGreaterEqual(self_obs.measurements["veyra_healthy_collectors_count"].value, 5)

    def test_coordinator_failure_isolation(self):
        coordinator = CollectionCoordinator()
        # Mock one collector to raise an unhandled exception
        bad_collector = MagicMock()
        bad_collector.name = "exploding_sensor"
        bad_collector.collect.side_effect = RuntimeError("Hardware bus error!")
        coordinator.collectors["bad_collector"] = bad_collector

        # Cycle must not crash
        cycle = coordinator.run_cycle()
        self.assertIn("bad_collector", cycle)
        self.assertFalse(cycle["bad_collector"].collector_healthy)
        self.assertIn("CRASH", cycle["bad_collector"].status_summary)

        # Other collectors must have succeeded
        self.assertTrue(cycle["cpu"].collector_healthy)
        self.assertTrue(cycle["memory"].collector_healthy)

    def test_hardware_capabilities_decoupled_for_future_optimization(self):
        coordinator = CollectionCoordinator()
        caps = coordinator.get_hardware_capabilities()
        self.assertIn("has_dedicated_gpu", caps)
        self.assertIn("has_wifi_adapter", caps)
        self.assertIn("has_psutil", caps)
        self.assertIsInstance(caps["has_dedicated_gpu"], bool)
        self.assertIsInstance(caps["has_wifi_adapter"], bool)

        # STRICT: Verify NO optimization functions exist on coordinator or collectors
        self.assertFalse(hasattr(coordinator, "optimize_system"))
        self.assertFalse(hasattr(coordinator, "apply_tweaks"))
        self.assertFalse(hasattr(coordinator, "boost_fps"))


if __name__ == "__main__":
    unittest.main()
