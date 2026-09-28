"""
Stage 5 Unit Tests: Hardware Bottleneck Investigator.
Verifies CPU, GPU, RAM, VRAM, storage, network, thermal limitation analysis,
conflicting constraints, and insufficient data handling.
"""
import unittest

from analyzer.bottleneck.investigator import (
    BottleneckConclusion,
    BottleneckInvestigator,
    HardwareBottleneckReport,
)
from app.core.contracts import Measurement, MetricState, MetricUnit, Observation


def make_obs(source: str, metrics: dict) -> Observation:
    measurements = {}
    for k, v in metrics.items():
        if v is None:
            measurements[k] = Measurement(
                metric_name=k,
                state=MetricState.UNAVAILABLE,
                value=None,
                unit=MetricUnit.PERCENTAGE,
                source_collector=source,
                provenance="test",
            )
        else:
            measurements[k] = Measurement(
                metric_name=k,
                state=MetricState.AVAILABLE,
                value=v,
                unit=MetricUnit.PERCENTAGE,
                source_collector=source,
                provenance="test",
            )
    return Observation(
        observation_id=f"obs_{source}",
        timestamp_utc="2026-09-28T12:00:00Z",
        collector_name=source,
        measurements=measurements,
        collector_healthy=True,
    )



class TestBottleneckInvestigator(unittest.TestCase):
    """Verifies evidence-backed bottleneck discovery."""

    def setUp(self):
        self.investigator = BottleneckInvestigator()

    def test_cpu_bottleneck_with_low_gpu(self):
        obs = {
            "cpu": make_obs("cpu", {"cpu_utilization_pct": 94.0}),
            "gpu": make_obs("gpu", {"gpu_utilization_pct": 35.0}),
            "memory": make_obs("memory", {"ram_utilization_pct": 60.0}),
        }
        report = self.investigator.investigate_report(obs)
        self.assertEqual(report.primary_conclusion, BottleneckConclusion.CPU_BOTTLENECK_CANDIDATE)
        self.assertTrue(any(c.component == "CPU" for c in report.candidates))

    def test_gpu_bottleneck(self):
        obs = {
            "cpu": make_obs("cpu", {"cpu_utilization_pct": 50.0}),
            "gpu": make_obs("gpu", {"gpu_utilization_pct": 98.0, "gpu_memory_utilization_pct": 70.0}),
            "memory": make_obs("memory", {"ram_utilization_pct": 55.0}),
        }
        report = self.investigator.investigate_report(obs)
        self.assertEqual(report.primary_conclusion, BottleneckConclusion.GPU_BOTTLENECK_CANDIDATE)
        self.assertTrue(any(c.component == "GPU" for c in report.candidates))

    def test_ram_pressure(self):
        obs = {
            "cpu": make_obs("cpu", {"cpu_utilization_pct": 40.0}),
            "memory": make_obs("memory", {"ram_utilization_pct": 96.0}),
        }
        report = self.investigator.investigate_report(obs)
        self.assertEqual(report.primary_conclusion, BottleneckConclusion.MEMORY_PRESSURE)

    def test_storage_pressure(self):
        obs = {
            "cpu": make_obs("cpu", {"cpu_utilization_pct": 30.0}),
            "memory": make_obs("memory", {"ram_utilization_pct": 50.0}),
            "disk": make_obs("disk", {"disk_utilization_pct": 98.0}),
        }
        report = self.investigator.investigate_report(obs)
        self.assertEqual(report.primary_conclusion, BottleneckConclusion.STORAGE_PRESSURE)

    def test_network_bottleneck(self):
        obs = {
            "cpu": make_obs("cpu", {"cpu_utilization_pct": 30.0}),
            "memory": make_obs("memory", {"ram_utilization_pct": 50.0}),
            "internet": make_obs("internet", {"internet_packet_loss_pct": 15.0}),
        }
        report = self.investigator.investigate_report(obs)
        self.assertEqual(report.primary_conclusion, BottleneckConclusion.NETWORK_BOTTLENECK_CANDIDATE)

    def test_genuine_thermal_limitation(self):
        obs = {
            "cpu": make_obs("cpu", {"cpu_utilization_pct": 50.0, "cpu_temperature_c": 98.0}),
            "memory": make_obs("memory", {"ram_utilization_pct": 50.0}),
        }
        report = self.investigator.investigate_report(obs)
        self.assertEqual(report.thermal_state, "AVAILABLE")
        self.assertEqual(report.primary_conclusion, BottleneckConclusion.THERMAL_LIMITATION_CANDIDATE)

    def test_missing_thermal_sensor_is_unavailable_not_guessed(self):
        obs = {
            "cpu": make_obs("cpu", {"cpu_utilization_pct": 95.0}),  # Heavy CPU load
            "memory": make_obs("memory", {"ram_utilization_pct": 50.0}),
        }
        report = self.investigator.investigate_report(obs)
        # Thermal data must be strictly marked UNAVAILABLE. Must not infer thermal throttling from high CPU!
        self.assertEqual(report.thermal_state, "UNAVAILABLE")
        self.assertIn("unavailable", report.thermal_details["message"].lower())
        self.assertFalse(any("THERMAL" in c.component for c in report.candidates))

    def test_multiple_constraints(self):
        obs = {
            "cpu": make_obs("cpu", {"cpu_utilization_pct": 95.0}),
            "gpu": make_obs("gpu", {"gpu_utilization_pct": 98.0}),
            "memory": make_obs("memory", {"ram_utilization_pct": 95.0}),
        }
        report = self.investigator.investigate_report(obs)
        self.assertEqual(report.primary_conclusion, BottleneckConclusion.MULTIPLE_CONSTRAINTS)
        self.assertGreaterEqual(len(report.candidates), 2)

    def test_no_bottleneck_when_healthy(self):
        obs = {
            "cpu": make_obs("cpu", {"cpu_utilization_pct": 25.0}),
            "gpu": make_obs("gpu", {"gpu_utilization_pct": 30.0}),
            "memory": make_obs("memory", {"ram_utilization_pct": 45.0}),
            "disk": make_obs("disk", {"disk_utilization_pct": 35.0}),
            "internet": make_obs("internet", {"internet_packet_loss_pct": 0.0}),
        }
        report = self.investigator.investigate_report(obs)
        self.assertEqual(report.primary_conclusion, BottleneckConclusion.NO_CLEAR_BOTTLENECK)
        self.assertEqual(len(report.candidates), 0)

    def test_insufficient_data(self):
        report = self.investigator.investigate_report({})
        self.assertEqual(report.primary_conclusion, BottleneckConclusion.INSUFFICIENT_DATA)


if __name__ == "__main__":
    unittest.main()
