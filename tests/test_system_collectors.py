"""
Tests for VEYRA System Telemetry Collectors (CPU, Memory, Disk).
"""
import unittest
from unittest.mock import patch, MagicMock

from app.core.contracts import MetricState, MetricUnit
from collectors.system.cpu import CpuCollector
from collectors.system.memory import MemoryCollector
from collectors.system.disk import DiskCollector


class TestSystemCollectors(unittest.TestCase):
    def test_real_cpu_collector(self):
        collector = CpuCollector()
        obs = collector.collect()
        self.assertTrue(obs.collector_healthy)
        self.assertIn("cpu_utilization_pct", obs.measurements)
        m = obs.measurements["cpu_utilization_pct"]
        self.assertEqual(m.state, MetricState.AVAILABLE)
        self.assertIsInstance(m.value, float)
        self.assertGreaterEqual(m.value, 0.0)
        self.assertLessEqual(m.value, 100.0)
        self.assertEqual(m.unit, MetricUnit.PERCENTAGE)

    def test_cpu_collector_when_psutil_missing(self):
        collector = CpuCollector()
        collector._psutil_available = False
        collector._psutil = None
        obs = collector.collect()
        self.assertFalse(obs.collector_healthy)
        m = obs.measurements["cpu_utilization_pct"]
        self.assertEqual(m.state, MetricState.COLLECTOR_UNAVAILABLE)
        self.assertIsNone(m.value)

    def test_real_memory_collector(self):
        collector = MemoryCollector()
        obs = collector.collect()
        self.assertTrue(obs.collector_healthy)
        self.assertIn("ram_utilization_pct", obs.measurements)
        self.assertIn("ram_total_mb", obs.measurements)
        self.assertIn("ram_used_mb", obs.measurements)

        util = obs.measurements["ram_utilization_pct"]
        total = obs.measurements["ram_total_mb"]
        self.assertEqual(util.state, MetricState.AVAILABLE)
        self.assertGreater(total.value, 1000.0)

    def test_real_disk_collector(self):
        collector = DiskCollector()
        obs = collector.collect()
        self.assertTrue(obs.collector_healthy)
        self.assertIn("disk_total_gb", obs.measurements)
        self.assertIn("disk_utilization_pct", obs.measurements)

        total_gb = obs.measurements["disk_total_gb"]
        self.assertEqual(total_gb.state, MetricState.AVAILABLE)
        self.assertGreater(total_gb.value, 1.0)


if __name__ == "__main__":
    unittest.main()
