"""
Tests for VEYRA GPU Telemetry Collector.
"""
import subprocess
import unittest
from unittest.mock import patch

from app.core.contracts import MetricState, MetricUnit
from app.core.exceptions import SecurityViolationError
from collectors.gpu.gpu_collector import GpuCollector


class TestGpuCollector(unittest.TestCase):
    def test_gpu_collector_available_mock(self):
        collector = GpuCollector()
        mock_output = "NVIDIA GeForce RTX 4080, 550.54, 25.0, 15.0, 16384, 2457, 58.0, 110.5\n"
        with patch("collectors.gpu.gpu_collector.run_safe_subprocess") as mock_sub:
            mock_sub.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=mock_output, stderr=""
            )
            obs = collector.collect()
            self.assertTrue(obs.collector_healthy)
            self.assertEqual(obs.measurements["gpu_name"].value, "NVIDIA GeForce RTX 4080")
            self.assertEqual(obs.measurements["gpu_utilization_pct"].value, 25.0)
            self.assertEqual(obs.measurements["gpu_temperature_c"].value, 58.0)

    def test_gpu_collector_unsupported_when_smi_missing(self):
        collector = GpuCollector()
        with patch("collectors.gpu.gpu_collector.run_safe_subprocess") as mock_sub:
            mock_sub.side_effect = SecurityViolationError("Executable not found")
            obs = collector.collect()
            self.assertFalse(obs.collector_healthy)
            self.assertEqual(obs.status_summary, "UNSUPPORTED")
            m = obs.measurements["gpu_utilization_pct"]
            self.assertEqual(m.state, MetricState.NOT_SUPPORTED)
            self.assertIsNone(m.value)

    def test_gpu_collector_malformed_output_handled(self):
        collector = GpuCollector()
        with patch("collectors.gpu.gpu_collector.run_safe_subprocess") as mock_sub:
            mock_sub.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="corrupted,format\n", stderr=""
            )
            obs = collector.collect()
            self.assertFalse(obs.collector_healthy)
            self.assertEqual(obs.measurements["gpu_utilization_pct"].state, MetricState.NOT_SUPPORTED)
            self.assertIsNone(obs.measurements["gpu_utilization_pct"].value)


if __name__ == "__main__":
    unittest.main()
