"""
Stage 5 Unit Tests: Storage Schema Migration & Stage 5 Persistence.
Verifies Migration 2 application, table schema integrity, and roundtrip queries
for diagnostic runs, gaming sessions, gaming profiles, optimization runs, and evidence packages.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from storage.contracts import (
    DiagnosticResultRecord,
    DiagnosticRunRecord,
    EvidencePackageRecord,
    GamingProfileRecord,
    GamingSessionRecord,
    OptimizationResultRecord,
    OptimizationRunRecord,
    OptimizationSnapshotRecord,
)
from storage.engine import StorageEngine
from storage.migrations.migration_manager import MigrationManager


class TestStage5Storage(unittest.TestCase):
    """Verifies SQLite persistence for Stage 5 entities."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_stage5_storage.sqlite")
        self.storage = StorageEngine(self.db_path)

    def tearDown(self):
        self.storage.sqlite.close()
        self.temp_dir.cleanup()

    def test_migration_version_is_2(self):
        conn = sqlite3.connect(self.db_path)
        try:
            version = MigrationManager.get_current_version(conn)
            self.assertEqual(version, 2)
            self.assertTrue(MigrationManager.validate_schema(conn))
        finally:
            conn.close()

    def test_diagnostic_run_and_result_persistence(self):
        run = DiagnosticRunRecord(
            run_id="diag_roundtrip",
            target="1.1.1.1",
            run_type="NETWORK",
            status="COMPLETED",
            started_at_utc="2026-09-28T12:00:00Z",
            ended_at_utc="2026-09-28T12:00:05Z",
            duration_seconds=5.0,
            assessment="All healthy",
            confidence=0.95,
            evidence_json='["test evidence"]',
            affected_layers_json="[]",
            recommendations_json='["no action needed"]',
        )
        self.storage.save_diagnostic_run(run)

        loaded_run = self.storage.get_diagnostic_run("diag_roundtrip")
        self.assertIsNotNone(loaded_run)
        self.assertEqual(loaded_run.run_id, "diag_roundtrip")
        self.assertEqual(loaded_run.assessment, "All healthy")

        res = DiagnosticResultRecord(
            result_id="res_1",
            run_id="diag_roundtrip",
            test_name="DNS Probe",
            target="dns.google",
            status="HEALTHY",
            latency_ms=14.5,
            packet_loss_pct=0.0,
            details_json='{"resolved": "8.8.8.8"}',
        )
        self.storage.save_diagnostic_result(res)

        results = self.storage.get_diagnostic_results_for_run("diag_roundtrip")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].test_name, "DNS Probe")
        self.assertEqual(results[0].latency_ms, 14.5)

    def test_gaming_session_and_profile_persistence(self):
        prof = GamingProfileRecord(
            profile_id="prof_cs2",
            game_name="Counter-Strike 2",
            executable="cs2.exe",
            expected_process="cs2.exe",
            preferred_metrics_json='["cpu", "gpu", "latency"]',
        )
        self.storage.save_gaming_profile(prof)

        loaded_prof = self.storage.get_gaming_profile("Counter-Strike 2")
        self.assertIsNotNone(loaded_prof)
        self.assertEqual(loaded_prof.executable, "cs2.exe")

        session = GamingSessionRecord(
            session_id="gsess_roundtrip",
            game_name="Counter-Strike 2",
            executable="cs2.exe",
            process_id=4567,
            status="COMPLETED",
            started_at_utc="2026-09-28T12:00:00Z",
            ended_at_utc="2026-09-28T12:30:00Z",
            duration_seconds=1800.0,
            fps_available=False,
            avg_cpu_pct=52.0,
            avg_gpu_pct=88.0,
            avg_latency_ms=21.0,
            session_dna_json='{"stability_score": 92.5}',
        )
        self.storage.save_gaming_session(session)

        loaded_sess = self.storage.get_gaming_session("gsess_roundtrip")
        self.assertIsNotNone(loaded_sess)
        self.assertEqual(loaded_sess.game_name, "Counter-Strike 2")
        self.assertFalse(loaded_sess.fps_available)

    def test_optimization_run_snapshot_result_persistence(self):
        run = OptimizationRunRecord(
            run_id="run_opt_1",
            opportunity_id="opp_1",
            category="NETWORK",
            title="Flush DNS",
            state="VERIFIED",
            risk_level="SAFE",
            requires_elevation=False,
            user_approved=True,
            verification_status="VERIFIED_IMPROVEMENT",
            details_json='{"target": "dns"}',
        )
        self.storage.save_optimization_run(run)

        snap = OptimizationSnapshotRecord(
            snapshot_id="snap_1",
            run_id="run_opt_1",
            optimization_id="opp_1",
            timestamp_utc="2026-09-28T12:00:00Z",
            subsystem="DNS",
            pre_state_json='{"cache": "dirty"}',
        )
        self.storage.save_optimization_snapshot(snap)

        res = OptimizationResultRecord(
            result_id="res_opt_1",
            run_id="run_opt_1",
            metric_name="dns_latency_ms",
            baseline_value=120.0,
            post_value=45.0,
            difference=-75.0,
            confidence=0.90,
            outcome="VERIFIED_IMPROVEMENT",
        )
        self.storage.save_optimization_result(res)

        loaded_snap = self.storage.get_optimization_snapshot_for_run("run_opt_1")
        self.assertIsNotNone(loaded_snap)
        self.assertEqual(loaded_snap.subsystem, "DNS")

        loaded_res = self.storage.get_optimization_results_for_run("run_opt_1")
        self.assertEqual(len(loaded_res), 1)
        self.assertEqual(loaded_res[0].difference, -75.0)

    def test_evidence_package_persistence(self):
        pkg = EvidencePackageRecord(
            package_id="pkg_test_1",
            timestamp_utc="2026-09-28T12:00:00Z",
            query="What is latency?",
            summary="Latency is 18ms",
            evidence_json='{"latency": 18.0}',
            confidence=0.95,
        )
        self.storage.save_evidence_package(pkg)

        loaded_pkg = self.storage.get_evidence_package("pkg_test_1")
        self.assertIsNotNone(loaded_pkg)
        self.assertEqual(loaded_pkg.summary, "Latency is 18ms")


if __name__ == "__main__":
    unittest.main()
