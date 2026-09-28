"""
Stage 5 Unit Tests: Advanced Diagnostics Subsystem.
Verifies probes, cancellation, timeouts, failure isolation, deterministic root-cause mapping,
and cross-layer graph assembly.
"""
from pathlib import Path
import tempfile
import threading
import time
import unittest

from diagnostics.contracts import (
    DiagnosticLayer,
    DiagnosticReport,
    DiagnosticStatus,
    LayerStatus,
    TestItemResult,
)
from diagnostics.investigator import CrossLayerInvestigator
from diagnostics.probes import (
    AdapterProbe,
    DnsProbe,
    GatewayProbe,
    InternetProbe,
    SystemResourceProbe,
    WifiProbe,
)
from diagnostics.runner import DiagnosticRunner
from storage.engine import StorageEngine


class MockProbe:
    """Configurable probe stub for deterministic testing."""

    def __init__(self, test_name: str, target: str, status: LayerStatus, latency_ms=None, loss_pct=None, error=None):
        self.test_name = test_name
        self.target = target
        self.status = status
        self.latency_ms = latency_ms
        self.loss_pct = loss_pct
        self.error = error

    def execute(self, *args, **kwargs) -> TestItemResult:
        return TestItemResult(
            test_name=self.test_name,
            target=self.target,
            status=self.status,
            latency_ms=self.latency_ms,
            packet_loss_pct=self.loss_pct,
            details={"mock": True},
            duration_ms=5.0,
            error_message=self.error,
        )


class TestDiagnosticsSubsystem(unittest.TestCase):
    """Tests deterministic diagnostics, root-cause assessment, and cancellation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_diag.sqlite")
        self.storage = StorageEngine(self.db_path)

    def tearDown(self):
        self.storage.sqlite.close()
        self.temp_dir.cleanup()

    def test_all_layers_healthy(self):
        investigator = CrossLayerInvestigator(
            system_probe=MockProbe("Sys", "pc", LayerStatus.HEALTHY),
            adapter_probe=MockProbe("Adapter", "eth0", LayerStatus.HEALTHY),
            wifi_probe=MockProbe("WiFi", "wlan", LayerStatus.HEALTHY),
            gateway_probe=MockProbe("GW", "192.168.1.1", LayerStatus.HEALTHY, latency_ms=1.5, loss_pct=0.0),
            dns_probe=MockProbe("DNS", "dns", LayerStatus.HEALTHY, latency_ms=15.0),
            internet_probe=MockProbe("Net", "1.1.1.1", LayerStatus.HEALTHY, latency_ms=18.0, loss_pct=0.0),
        )
        report = investigator.run_investigation()
        self.assertEqual(report.status, DiagnosticStatus.COMPLETED)
        self.assertIsNone(report.graph.primary_root_cause_node)
        self.assertIn("All Diagnostic Layers Healthy", report.assessment)
        self.assertGreaterEqual(report.confidence, 0.90)

    def test_gateway_failure_root_cause(self):
        investigator = CrossLayerInvestigator(
            system_probe=MockProbe("Sys", "pc", LayerStatus.HEALTHY),
            adapter_probe=MockProbe("Adapter", "eth0", LayerStatus.HEALTHY),
            wifi_probe=MockProbe("WiFi", "wlan", LayerStatus.HEALTHY),
            gateway_probe=MockProbe("GW", "192.168.1.1", LayerStatus.FAILED, loss_pct=100.0),
            dns_probe=MockProbe("DNS", "dns", LayerStatus.FAILED),
            internet_probe=MockProbe("Net", "1.1.1.1", LayerStatus.FAILED, loss_pct=100.0),
        )
        report = investigator.run_investigation()
        self.assertEqual(report.graph.primary_root_cause_node, "gateway")
        self.assertIn("Default Gateway Issue", report.assessment)
        self.assertIn("gateway", report.graph.nodes)
        self.assertEqual(report.graph.nodes["gateway"].status, LayerStatus.FAILED)

    def test_dns_failure_when_gateway_healthy(self):
        investigator = CrossLayerInvestigator(
            system_probe=MockProbe("Sys", "pc", LayerStatus.HEALTHY),
            adapter_probe=MockProbe("Adapter", "eth0", LayerStatus.HEALTHY),
            wifi_probe=MockProbe("WiFi", "wlan", LayerStatus.HEALTHY),
            gateway_probe=MockProbe("GW", "192.168.1.1", LayerStatus.HEALTHY, latency_ms=2.0),
            dns_probe=MockProbe("DNS", "dns", LayerStatus.FAILED),
            internet_probe=MockProbe("Net", "1.1.1.1", LayerStatus.HEALTHY, latency_ms=15.0),
        )
        report = investigator.run_investigation()
        self.assertEqual(report.graph.primary_root_cause_node, "dns")
        self.assertIn("DNS Subsystem Issue", report.assessment)

    def test_upstream_internet_failure(self):
        investigator = CrossLayerInvestigator(
            system_probe=MockProbe("Sys", "pc", LayerStatus.HEALTHY),
            adapter_probe=MockProbe("Adapter", "eth0", LayerStatus.HEALTHY),
            wifi_probe=MockProbe("WiFi", "wlan", LayerStatus.HEALTHY),
            gateway_probe=MockProbe("GW", "192.168.1.1", LayerStatus.HEALTHY, latency_ms=2.0),
            dns_probe=MockProbe("DNS", "dns", LayerStatus.HEALTHY, latency_ms=12.0),
            internet_probe=MockProbe("Net", "1.1.1.1", LayerStatus.FAILED, loss_pct=100.0),
        )
        report = investigator.run_investigation()
        self.assertEqual(report.graph.primary_root_cause_node, "internet")
        self.assertIn("Upstream Internet Outage", report.assessment)

    def test_wifi_degradation_detected(self):
        investigator = CrossLayerInvestigator(
            system_probe=MockProbe("Sys", "pc", LayerStatus.HEALTHY),
            adapter_probe=MockProbe("Adapter", "eth0", LayerStatus.HEALTHY),
            wifi_probe=MockProbe("WiFi", "wlan", LayerStatus.DEGRADED),
            gateway_probe=MockProbe("GW", "192.168.1.1", LayerStatus.HEALTHY),
            dns_probe=MockProbe("DNS", "dns", LayerStatus.HEALTHY),
            internet_probe=MockProbe("Net", "1.1.1.1", LayerStatus.HEALTHY),
        )
        report = investigator.run_investigation()
        self.assertEqual(report.graph.primary_root_cause_node, "wifi")
        self.assertIn("Wi-Fi", report.assessment)

    def test_cancellation_terminates_early(self):
        cancel_evt = threading.Event()
        cancel_evt.set()  # Cancelled immediately

        investigator = CrossLayerInvestigator()
        report = investigator.run_investigation(cancel_event=cancel_evt)
        self.assertEqual(report.status, DiagnosticStatus.CANCELLED)
        self.assertEqual(report.confidence, 0.0)
        self.assertIn("cancelled", report.assessment.lower())

    def test_runner_persistence(self):
        investigator = CrossLayerInvestigator(
            system_probe=MockProbe("Sys", "pc", LayerStatus.HEALTHY),
            adapter_probe=MockProbe("Adapter", "eth0", LayerStatus.HEALTHY),
            wifi_probe=MockProbe("WiFi", "wlan", LayerStatus.HEALTHY),
            gateway_probe=MockProbe("GW", "192.168.1.1", LayerStatus.HEALTHY),
            dns_probe=MockProbe("DNS", "dns", LayerStatus.HEALTHY),
            internet_probe=MockProbe("Net", "1.1.1.1", LayerStatus.HEALTHY),
        )
        runner = DiagnosticRunner(storage=self.storage, investigator=investigator)
        report = runner.run_sync()

        self.assertEqual(report.status, DiagnosticStatus.COMPLETED)
        saved_run = self.storage.get_diagnostic_run(report.run_id)
        self.assertIsNotNone(saved_run)
        self.assertEqual(saved_run.run_id, report.run_id)

        results = self.storage.get_diagnostic_results_for_run(report.run_id)
        self.assertEqual(len(results), len(report.test_results))


if __name__ == "__main__":
    unittest.main()
