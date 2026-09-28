"""
Tests for VEYRA Branding Asset Integrity Lock and SHA-256 Verification.
"""
import unittest
from pathlib import Path
import tempfile
import json
import shutil

from app.core.branding import verify_branding_manifest, calculate_sha256, VerificationReport
from app.core.exceptions import BrandingIntegrityError


class TestBrandingIntegrity(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent

    def test_all_official_branding_assets_pass_verification(self):
        """Ensures that all 22 official locked branding assets pass SHA-256 verification."""
        report = verify_branding_manifest(self.project_root, raise_on_error=False)
        self.assertTrue(report.is_valid, f"Branding verification failed: {report.print_summary()}")
        self.assertEqual(report.verified_count, 22)
        self.assertEqual(len(report.failures), 0)

    def test_normal_and_gaming_masters_present(self):
        """Verifies master EXACT assets exist with expected file sizes and cryptographic SHA-256."""
        normal_master = self.project_root / "assets" / "branding" / "normal" / "VEYRA_Normal_Logo_EXACT.png"
        gaming_master = self.project_root / "assets" / "branding" / "gaming" / "VEYRA_Gaming_Logo_EXACT.png"

        self.assertTrue(normal_master.exists(), "Normal mode master artwork missing")
        self.assertTrue(gaming_master.exists(), "Gaming mode master artwork missing")

        # Confirm non-empty
        self.assertGreater(normal_master.stat().st_size, 1000000)
        self.assertGreater(gaming_master.stat().st_size, 1000000)

        # Cryptographic SHA-256 lock verification against authoritative manifest
        report = verify_branding_manifest(self.project_root, raise_on_error=False)
        self.assertTrue(report.is_valid)
        self.assertEqual(calculate_sha256(normal_master), "d8de9387ae1d62c7b6f3665b7d684339d6a6dc0b32129aedd7f9d7a4e7218d96")
        self.assertEqual(calculate_sha256(gaming_master), "8d764ce5c3a55a1f1dc1369796d7f798cc3db3782ca6f61a93a18f97690e288b")

    def test_verification_detects_corrupted_hash(self):
        """Verifies that an altered asset fails verification with detailed mismatch info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            tmp_branding = tmp_root / "assets" / "branding" / "normal"
            tmp_branding.mkdir(parents=True)

            dummy_file = tmp_branding / "test_logo.png"
            dummy_file.write_text("original-content")

            manifest_path = tmp_root / "assets" / "branding" / "branding_manifest.json"
            manifest_content = {
                "manifest_version": "1.0.0",
                "assets": [
                    {
                        "asset_path": "assets/branding/normal/test_logo.png",
                        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                        "dimensions": None
                    }
                ]
            }
            manifest_path.write_text(json.dumps(manifest_content))

            report = verify_branding_manifest(tmp_root, raise_on_error=False)
            self.assertFalse(report.is_valid)
            self.assertEqual(len(report.failures), 1)
            self.assertEqual(report.failures[0].failure_type, "HASH_MISMATCH")

    def test_verification_raises_exception_when_requested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            # No manifest exists
            with self.assertRaises(BrandingIntegrityError):
                verify_branding_manifest(tmp_root, raise_on_error=True)


if __name__ == "__main__":
    unittest.main()
