"""
Tests for VEYRA Security and Privacy Foundation.
"""
import unittest
from pathlib import Path

from app.core.security import validate_local_binding, validate_safe_path, run_safe_subprocess
from app.core.exceptions import SecurityViolationError
from app.core.logging import redact_sensitive_data


class TestSecurity(unittest.TestCase):
    def test_local_binding_enforcement(self):
        validate_local_binding("127.0.0.1")
        validate_local_binding("localhost")
        with self.assertRaises(SecurityViolationError):
            validate_local_binding("0.0.0.0")
        with self.assertRaises(SecurityViolationError):
            validate_local_binding("10.0.0.5")

    def test_path_traversal_prevention(self):
        base_dir = Path("D:/VEYRA/assets")
        safe_target = Path("D:/VEYRA/assets/branding/normal")
        unsafe_target = Path("D:/VEYRA/assets/../../Windows/System32")

        self.assertEqual(validate_safe_path(safe_target, base_dir), safe_target.resolve())
        with self.assertRaises(SecurityViolationError):
            validate_safe_path(unsafe_target, base_dir)

    def test_safe_subprocess_execution(self):
        # Safe command execution with argument list
        res = run_safe_subprocess(["python", "--version"], timeout_seconds=5.0)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Python", res.stdout + res.stderr)

    def test_safe_subprocess_timeout(self):
        # Long running command that times out
        with self.assertRaises(SecurityViolationError):
            run_safe_subprocess(["python", "-c", "import time; time.sleep(2)"], timeout_seconds=0.2)

    def test_sensitive_data_redaction(self):
        raw = "User requested auth token Bearer secret_token_12345 with password=MySuperSecretPassword!"
        redacted = redact_sensitive_data(raw)
        self.assertNotIn("secret_token_12345", redacted)
        self.assertNotIn("MySuperSecretPassword!", redacted)
        self.assertIn("***REDACTED***", redacted)


if __name__ == "__main__":
    unittest.main()
