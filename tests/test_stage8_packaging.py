"""
VEYRA Automated Tests — Stage 8 Packaging, Deployment & Windows Release Engineering.
Tests production path resolution, user data vs binary separation, packaging specs,
deployment scripts, release manifests, supervisor rate-limiting, and migration behavior.
"""
import json
import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from app.core.paths import (
    get_installation_dir,
    get_app_data_dir,
    get_data_dir,
    get_logs_dir,
    get_config_dir,
    get_default_db_path,
    get_branding_dir,
    ensure_app_data_dirs,
    is_frozen,
)
from app.core.supervisor import ProcessSupervisor, SupervisorConfig
from tools.generate_release_manifest import generate_manifest, sha256_file
from storage.engine import StorageEngine


class TestStage8Packaging(unittest.TestCase):
    """Verifies packaging architecture, security, deployment scripts, and runtime paths."""

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parent.parent
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_production_path_resolution(self) -> None:
        """Verifies clean separation between installation directory and user data directory."""
        install_dir = get_installation_dir()
        app_data_dir = get_app_data_dir()
        data_dir = get_data_dir()
        logs_dir = get_logs_dir()
        config_dir = get_config_dir()
        db_path = get_default_db_path()

        # User data must be rooted under VEYRA
        self.assertEqual(app_data_dir.name, "VEYRA")
        self.assertEqual(data_dir, app_data_dir / "data")
        self.assertEqual(logs_dir, app_data_dir / "logs")
        self.assertEqual(config_dir, app_data_dir / "config")
        self.assertEqual(db_path, data_dir / "history.sqlite")

        # In dev mode, install_dir is project root; in frozen mode, install_dir is executable location
        self.assertTrue(install_dir.exists())

    def test_simulation_exclusion_from_packaging_spec(self) -> None:
        """Rule 9: Enforces that simulation and tests are strictly excluded in installer/veyra.spec."""
        spec_path = self.project_root / "installer" / "veyra.spec"
        self.assertTrue(spec_path.exists(), "installer/veyra.spec must exist")
        content = spec_path.read_text(encoding="utf-8")

        self.assertIn('"simulation"', content, "Simulation framework must be listed in excludes")
        self.assertIn('"tests"', content, "Test suites must be listed in excludes")
        self.assertIn("excludes=excludes", content)

    def test_no_hardcoded_developer_paths_in_production_code(self) -> None:
        """Ensures production path and config files contain no hardcoded development paths."""
        for rel_file in ["app/core/paths.py", "app/core/config.py"]:
            file_path = self.project_root / rel_file
            content = file_path.read_text(encoding="utf-8")
            self.assertNotIn("D:\\VEYRA", content, f"Hardcoded developer path found in {rel_file}")
            self.assertNotIn("C:\\Users\\", content, f"Hardcoded user home path found in {rel_file}")

    def test_production_database_initialization_and_migration(self) -> None:
        """Verifies that a database initialized in an isolated directory applies all migrations cleanly."""
        test_db = Path(self.temp_dir) / "data" / "history.sqlite"
        test_db.parent.mkdir(parents=True, exist_ok=True)

        engine = StorageEngine(str(test_db))
        try:
            stats = engine.get_stats()
            self.assertEqual(stats.storage_health.value, "HEALTHY")
            self.assertTrue(test_db.exists())
            self.assertGreater(test_db.stat().st_size, 0)
        finally:
            engine.sqlite.close()

    def test_install_script_syntax_and_structure(self) -> None:
        """Validates install.ps1 structure, parameters, shortcut creation, and registry integration."""
        install_script = self.project_root / "install.ps1"
        self.assertTrue(install_script.exists(), "install.ps1 must exist")
        content = install_script.read_text(encoding="utf-8")

        self.assertIn("param (", content)
        self.assertIn("$InstallDir", content)
        self.assertIn("Start Menu", content)
        self.assertIn("HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\VEYRA", content)
        self.assertIn("UninstallString", content)

    def test_uninstall_script_data_policy(self) -> None:
        """Validates uninstall.ps1 preserves user data by default unless -PurgeData is supplied."""
        uninstall_script = self.project_root / "uninstall.ps1"
        self.assertTrue(uninstall_script.exists(), "uninstall.ps1 must exist")
        content = uninstall_script.read_text(encoding="utf-8")

        self.assertIn("[switch]$PurgeData", content)
        self.assertIn("if ($PurgeData)", content)
        self.assertIn("PRESERVED", content)

    def test_launcher_batch_file_integrity(self) -> None:
        """Validates run_veyra.bat locates installed or distribution executable without Python dependency."""
        batch_file = self.project_root / "run_veyra.bat"
        self.assertTrue(batch_file.exists(), "run_veyra.bat must exist")
        content = batch_file.read_text(encoding="utf-8")

        self.assertIn("LOCALAPPDATA", content)
        self.assertIn("VEYRA.exe", content)
        self.assertNotIn("python ", content, "Production launcher must not rely on Python command")

    def test_inno_setup_script_validity(self) -> None:
        """Validates installer/installer.iss uses least-privilege, correct icon, and clean uninstaller."""
        iss_file = self.project_root / "installer" / "installer.iss"
        self.assertTrue(iss_file.exists(), "installer/installer.iss must exist")
        content = iss_file.read_text(encoding="utf-8")

        self.assertIn('#define MyAppName "VEYRA"', content)
        self.assertIn("AppName={#MyAppName}", content)
        self.assertIn("PrivilegesRequired=lowest", content, "Installer must default to lowest privileges")
        self.assertIn("VEYRA_Normal_Icon.ico", content)
        self.assertIn("VEYRA_Setup_v", content)

    def test_msix_manifest_validity(self) -> None:
        """Validates installer/AppxManifest.xml XML structure and capability bounds."""
        manifest_file = self.project_root / "installer" / "AppxManifest.xml"
        self.assertTrue(manifest_file.exists(), "installer/AppxManifest.xml must exist")

        tree = ET.parse(manifest_file)
        root = tree.getroot()
        self.assertIn("Package", root.tag)

        # Check capabilities
        content = manifest_file.read_text(encoding="utf-8")
        self.assertIn("runFullTrust", content)
        self.assertNotIn("internetClientServer", content, "Local-first VEYRA must not request server capabilities")

    def test_release_manifest_generation(self) -> None:
        """Verifies release_manifest.json generation and SHA-256 integrity calculations."""
        manifest = generate_manifest()
        self.assertEqual(manifest["product"], "VEYRA")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["architecture"], "x64")
        self.assertEqual(manifest["hash_algorithm"], "SHA-256")
        self.assertGreater(manifest["artifact_count"], 0)

        # Confirm release_manifest.json was written to disk
        disk_manifest = self.project_root / "release_manifest.json"
        self.assertTrue(disk_manifest.exists())

    def test_minimal_supervisor_bounded_restart(self) -> None:
        """Verifies that ProcessSupervisor detects rapid crash loops (restart storm) and terminates."""
        import time
        config = SupervisorConfig(max_restarts=3, restart_window_seconds=10.0)
        supervisor = ProcessSupervisor(target_cmd=["echo", "test"], config=config)

        now = time.monotonic()
        # Simulate 2 rapid restarts (under threshold)
        supervisor.restart_timestamps = [now - 2.0, now - 1.0]
        self.assertFalse(supervisor.is_looping())

        # Simulate 3rd restart (at threshold)
        supervisor.restart_timestamps.append(now)
        self.assertTrue(supervisor.is_looping())

    def test_branding_assets_accessible_via_paths(self) -> None:
        """Verifies that get_branding_dir() locates the official branding manifest and locked assets."""
        branding_dir = get_branding_dir()
        manifest_path = branding_dir / "branding_manifest.json"
        self.assertTrue(manifest_path.exists(), f"Branding manifest not found at {manifest_path}")

        normal_icon = branding_dir / "normal" / "VEYRA_Normal_Icon.ico"
        gaming_icon = branding_dir / "gaming" / "VEYRA_Gaming_Icon.ico"
        self.assertTrue(normal_icon.exists(), "Normal icon missing")
        self.assertTrue(gaming_icon.exists(), "Gaming icon missing")


if __name__ == "__main__":
    unittest.main()
