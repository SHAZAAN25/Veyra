"""
Tests for VEYRA Configuration Foundation.
"""
import unittest

from app.core.config import VeyraConfig, load_default_config, AppConfig
from app.core.exceptions import ConfigurationError, SecurityViolationError


class TestConfig(unittest.TestCase):
    def test_default_config_valid(self):
        config = load_default_config()
        self.assertEqual(config.app.product_name, "VEYRA")
        self.assertEqual(config.app.api_host, "127.0.0.1")
        self.assertEqual(config.ui.theme, "dark")
        self.assertEqual(config.ui.mode, "normal")

    def test_reject_insecure_host_binding(self):
        """Verifies that 0.0.0.0 and external IPs are strictly rejected."""
        config = VeyraConfig(app=AppConfig(api_host="0.0.0.0"))
        with self.assertRaises(SecurityViolationError):
            config.validate()

        config_ext = VeyraConfig(app=AppConfig(api_host="192.168.1.100"))
        with self.assertRaises(SecurityViolationError):
            config_ext.validate()

    def test_reject_invalid_port(self):
        config = VeyraConfig(app=AppConfig(api_port=80))  # privileged port
        with self.assertRaises(ConfigurationError):
            config.validate()

    def test_serialization_roundtrip(self):
        config = load_default_config()
        data = config.to_dict()
        restored = VeyraConfig.from_dict(data)
        restored.validate()
        self.assertEqual(restored.app.product_name, "VEYRA")
        self.assertEqual(restored.monitoring.poll_interval_seconds, 2.0)


if __name__ == "__main__":
    unittest.main()
