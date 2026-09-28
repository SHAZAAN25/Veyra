"""
Tests for VEYRA Data Contract and Absolute Telemetry Integrity.
"""
import unittest

from app.core.contracts import (
    Measurement,
    MetricState,
    MetricUnit,
    Observation,
    Assessment,
    Incident,
    HistoricalSummary
)
from app.core.exceptions import DataContractViolationError


class TestContracts(unittest.TestCase):
    def test_valid_measurement_creation(self):
        m = Measurement(
            metric_name="ping_latency",
            state=MetricState.AVAILABLE,
            value=14.5,
            unit=MetricUnit.MILLISECONDS,
            source_collector="network_ping",
            provenance="icmp:1.1.1.1"
        )
        self.assertTrue(m.is_valid)
        self.assertEqual(m.value, 14.5)
        self.assertEqual(m.unit, MetricUnit.MILLISECONDS)

    def test_explicit_unavailable_state(self):
        m = Measurement(
            metric_name="gpu_temperature",
            state=MetricState.NOT_SUPPORTED,
            value=None,
            unit=MetricUnit.CELSIUS,
            source_collector="hardware_gpu",
            provenance="wmi:gpu",
            error_message="Host GPU vendor telemetry not supported"
        )
        self.assertFalse(m.is_valid)
        self.assertIsNone(m.value)
        self.assertEqual(m.state, MetricState.NOT_SUPPORTED)

    def test_forbid_fake_telemetry_when_state_is_not_available(self):
        """CRITICAL: Enforces the permanent rule: NEVER FABRICATE A MEASUREMENT."""
        with self.assertRaises(DataContractViolationError):
            Measurement(
                metric_name="wifi_signal_pct",
                state=MetricState.UNAVAILABLE,
                value=75.0,  # Fabricated sample value!
                unit=MetricUnit.PERCENTAGE,
                source_collector="wifi_netsh",
                provenance="wlan"
            )

    def test_available_measurement_requires_value(self):
        with self.assertRaises(DataContractViolationError):
            Measurement(
                metric_name="cpu_usage",
                state=MetricState.AVAILABLE,
                value=None,  # Missing value in AVAILABLE state!
                unit=MetricUnit.PERCENTAGE,
                source_collector="sys_psutil",
                provenance="os"
            )

    def test_observation_and_assessment_structure(self):
        m = Measurement(
            metric_name="dns_latency",
            state=MetricState.AVAILABLE,
            value=12.2,
            unit=MetricUnit.MILLISECONDS,
            source_collector="dns_resolver",
            provenance="dns:google.com"
        )
        obs = Observation(
            observation_id="obs_001",
            timestamp_utc=m.timestamp_utc,
            collector_name="network_dns",
            measurements={"dns_latency": m},
            collector_healthy=True
        )
        self.assertEqual(obs.get_metric("dns_latency").value, 12.2)

        assessment = Assessment(
            assessment_id="ass_001",
            timestamp_utc=obs.timestamp_utc,
            target_domain="network",
            overall_health="HEALTHY",
            score=98.5,
            observations_evaluated=1
        )
        self.assertEqual(assessment.overall_health, "HEALTHY")


if __name__ == "__main__":
    unittest.main()
