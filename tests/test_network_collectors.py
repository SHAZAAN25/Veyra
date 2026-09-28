"""
Tests for VEYRA Network & Wi-Fi Collectors.
"""
import subprocess
import unittest
from unittest.mock import patch

from app.core.contracts import MetricState, MetricUnit
from collectors.network.adapter import AdapterCollector
from collectors.network.throughput import ThroughputCollector
from collectors.wifi.wifi_collector import WifiCollector


class TestNetworkCollectors(unittest.TestCase):
    def test_adapter_collector_live(self):
        collector = AdapterCollector()
        obs = collector.collect()
        self.assertIn("adapter_is_up", obs.measurements)
        self.assertIsInstance(obs.measurements["adapter_is_up"].value, bool)

    def test_throughput_collector_two_cycles(self):
        collector = ThroughputCollector()
        # First cycle establishes baseline
        obs1 = collector.collect()
        self.assertEqual(obs1.measurements["network_rx_mbps"].state, MetricState.UNAVAILABLE)

        # Small delay and second cycle calculates real throughput
        import time
        time.sleep(0.15)
        obs2 = collector.collect()
        self.assertEqual(obs2.measurements["network_rx_mbps"].state, MetricState.AVAILABLE)
        self.assertGreaterEqual(obs2.measurements["network_rx_mbps"].value, 0.0)

    def test_wifi_collector_mock_connected(self):
        collector = WifiCollector()
        mock_output = """
There is 1 interface on the system: 
    Name                   : Wi-Fi
    Description            : Intel Wi-Fi 6 AX201
    State                  : connected
    SSID                   : Office_Net_5G
    AP BSSID               : 11:22:33:44:55:66
    Network type           : Infrastructure
    Radio type             : 802.11ax
    Band                   : 5 GHz
    Channel                : 44
    Receive rate (Mbps)    : 866
    Transmit rate (Mbps)   : 866
    Signal                 : 92% 
    Rssi                   : -54
"""
        with patch("collectors.wifi.wifi_collector.run_safe_subprocess") as mock_sub:
            mock_sub.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=mock_output, stderr=""
            )
            obs = collector.collect()
            self.assertTrue(obs.collector_healthy)
            self.assertEqual(obs.measurements["wifi_connected"].value, True)
            self.assertEqual(obs.measurements["wifi_ssid"].value, "Office_Net_5G")
            self.assertEqual(obs.measurements["wifi_signal_pct"].value, 92.0)
            self.assertEqual(obs.measurements["wifi_rssi_dbm"].value, -54.0)
            self.assertEqual(obs.measurements["wifi_channel"].value, 44)

    def test_wifi_collector_mock_disconnected(self):
        collector = WifiCollector()
        mock_output = """
There is 1 interface on the system: 
    Name                   : Wi-Fi
    Description            : Intel Wi-Fi 6 AX201
    State                  : disconnected
"""
        with patch("collectors.wifi.wifi_collector.run_safe_subprocess") as mock_sub:
            mock_sub.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=mock_output, stderr=""
            )
            obs = collector.collect()
            self.assertEqual(obs.measurements["wifi_connected"].value, False)
            self.assertEqual(obs.measurements["wifi_signal_pct"].state, MetricState.UNAVAILABLE)
            self.assertIsNone(obs.measurements["wifi_signal_pct"].value)

    def test_wifi_collector_mock_ethernet_only(self):
        collector = WifiCollector()
        mock_output = "There is no wireless interface on the system.\n"
        with patch("collectors.wifi.wifi_collector.run_safe_subprocess") as mock_sub:
            mock_sub.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=mock_output, stderr=""
            )
            obs = collector.collect()
            self.assertFalse(obs.collector_healthy)
            self.assertEqual(obs.status_summary, "NOT_SUPPORTED")
            self.assertEqual(obs.measurements["wifi_connected"].state, MetricState.NOT_SUPPORTED)


if __name__ == "__main__":
    unittest.main()
