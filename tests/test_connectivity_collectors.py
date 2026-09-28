"""
Tests for VEYRA Connectivity Telemetry Collectors (Gateway, Internet, DNS).
"""
import socket
import subprocess
import unittest
from unittest.mock import patch

from app.core.contracts import MetricState, MetricUnit
from collectors.connectivity.gateway import GatewayCollector
from collectors.connectivity.internet import InternetCollector, calculate_rfc3550_jitter
from collectors.connectivity.dns import DnsCollector


class TestConnectivityCollectors(unittest.TestCase):
    def test_rfc3550_jitter_calculation(self):
        # 4 consecutive samples: 20ms, 25ms, 22ms, 28ms
        # Diffs: |25-20|=5, |22-25|=3, |28-22|=6
        # Mean diff = (5 + 3 + 6) / 3 = 14 / 3 = 4.67 ms
        samples = [20.0, 25.0, 22.0, 28.0]
        jitter = calculate_rfc3550_jitter(samples)
        self.assertEqual(jitter, 4.67)

        # Single sample cannot yield jitter
        single = [25.0]
        self.assertIsNone(calculate_rfc3550_jitter(single))

    def test_internet_collector_single_packet_jitter_unavailable(self):
        """CRITICAL: Enforces that jitter is NEVER fabricated from a single ping."""
        collector = InternetCollector(probe_count=4)
        mock_output = "Reply from 1.1.1.1: bytes=32 time=15ms TTL=57\nRequest timed out.\nRequest timed out.\nRequest timed out.\n"
        with patch("collectors.connectivity.internet.run_safe_subprocess") as mock_sub:
            mock_sub.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=mock_output, stderr=""
            )
            obs = collector.collect()
            self.assertTrue(obs.collector_healthy)
            self.assertEqual(obs.measurements["internet_packet_loss_pct"].value, 75.0)
            self.assertEqual(obs.measurements["internet_latency_rtt_ms"].value, 15.0)
            # Only 1 reply received -> Jitter MUST be UNAVAILABLE!
            jitter_m = obs.measurements["internet_jitter_ms"]
            self.assertEqual(jitter_m.state, MetricState.UNAVAILABLE)
            self.assertIsNone(jitter_m.value)

    def test_internet_collector_all_packets_timeout(self):
        collector = InternetCollector(probe_count=4)
        mock_output = "Request timed out.\nRequest timed out.\nRequest timed out.\nRequest timed out.\n"
        with patch("collectors.connectivity.internet.run_safe_subprocess") as mock_sub:
            mock_sub.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=mock_output, stderr=""
            )
            obs = collector.collect()
            self.assertFalse(obs.collector_healthy)
            self.assertEqual(obs.measurements["internet_reachable"].value, False)
            self.assertEqual(obs.measurements["internet_packet_loss_pct"].value, 100.0)
            self.assertEqual(obs.measurements["internet_latency_rtt_ms"].state, MetricState.UNAVAILABLE)

    def test_gateway_collector_success(self):
        collector = GatewayCollector(override_gateway="192.168.1.1")
        mock_output = "Reply from 192.168.1.1: bytes=32 time=2ms TTL=64\nReply from 192.168.1.1: bytes=32 time=3ms TTL=64\n"
        with patch("collectors.connectivity.gateway.run_safe_subprocess") as mock_sub:
            mock_sub.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=mock_output, stderr=""
            )
            obs = collector.collect()
            self.assertTrue(obs.collector_healthy)
            self.assertEqual(obs.measurements["gateway_reachable"].value, True)
            self.assertEqual(obs.measurements["gateway_rtt_ms"].value, 2.5)

    def test_dns_collector_live(self):
        collector = DnsCollector(target_host="google.com")
        obs = collector.collect()
        self.assertTrue(obs.collector_healthy)
        self.assertEqual(obs.measurements["dns_success"].value, True)
        self.assertGreater(obs.measurements["dns_response_ms"].value, 0.0)

    def test_dns_collector_failure_mock(self):
        collector = DnsCollector(target_host="nonexistent.invalid.domain")
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.side_effect = socket.gaierror(-2, "Name or service not known")
            obs = collector.collect()
            self.assertFalse(obs.collector_healthy)
            self.assertEqual(obs.measurements["dns_success"].value, False)
            self.assertEqual(obs.measurements["dns_response_ms"].state, MetricState.UNAVAILABLE)
            self.assertIsNone(obs.measurements["dns_response_ms"].value)


if __name__ == "__main__":
    unittest.main()
