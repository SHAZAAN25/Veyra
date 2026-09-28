"""
Tests for VEYRA 'What Changed?' Change Detection Engine.
"""
import unittest

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from analyzer.changes.what_changed import ChangeDetector


class TestChangeDetection(unittest.TestCase):
    def test_change_detection_flow(self):
        detector = ChangeDetector()

        def make_cycle(ssid: str, ip: str, gw: str) -> dict:
            return {
                "adapter": Observation(
                    observation_id="obs_ad",
                    timestamp_utc="2026-09-28T00:00:00Z",
                    collector_name="adapter",
                    measurements={
                        "adapter_name": Measurement("adapter_name", MetricState.AVAILABLE, "Wi-Fi", MetricUnit.STRING, "test", "test"),
                        "adapter_ipv4_address": Measurement("adapter_ipv4_address", MetricState.AVAILABLE, ip, MetricUnit.STRING, "test", "test")
                    },
                    collector_healthy=True
                ),
                "wifi": Observation(
                    observation_id="obs_wf",
                    timestamp_utc="2026-09-28T00:00:00Z",
                    collector_name="wifi",
                    measurements={
                        "wifi_ssid": Measurement("wifi_ssid", MetricState.AVAILABLE, ssid, MetricUnit.STRING, "test", "test"),
                        "wifi_connected": Measurement("wifi_connected", MetricState.AVAILABLE, True, MetricUnit.BOOLEAN, "test", "test")
                    },
                    collector_healthy=True
                ),
                "gateway": Observation(
                    observation_id="obs_gw",
                    timestamp_utc="2026-09-28T00:00:00Z",
                    collector_name="gateway",
                    measurements={
                        "gateway_ip": Measurement("gateway_ip", MetricState.AVAILABLE, gw, MetricUnit.STRING, "test", "test")
                    },
                    collector_healthy=True
                )
            }

        # 1. First cycle: establishes initial state
        initial_changes = detector.detect_changes(make_cycle("Home_WiFi", "192.168.1.50", "192.168.1.1"))
        self.assertEqual(len(initial_changes), 0)

        # 2. Second cycle with same parameters: zero changes
        second_changes = detector.detect_changes(make_cycle("Home_WiFi", "192.168.1.50", "192.168.1.1"))
        self.assertEqual(len(second_changes), 0)

        # 3. Third cycle: Wi-Fi SSID switches to "Cafe_Guest" and IP changes
        third_changes = detector.detect_changes(make_cycle("Cafe_Guest", "10.0.0.12", "192.168.1.1"))
        self.assertGreaterEqual(len(third_changes), 2)

        change_attrs = {c.attribute_name: c for c in third_changes}
        self.assertIn("wifi_ssid", change_attrs)
        self.assertEqual(change_attrs["wifi_ssid"].old_value, "Home_WiFi")
        self.assertEqual(change_attrs["wifi_ssid"].new_value, "Cafe_Guest")
        self.assertEqual(change_attrs["wifi_ssid"].significance, "SUSPICIOUS")


if __name__ == "__main__":
    unittest.main()
