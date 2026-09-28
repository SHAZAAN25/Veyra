"""
Stage 5 Unit Tests: Gaming Intelligence, Session Engine & Gaming Session DNA.
Verifies reliable game identification, session state machines, session DNA calculation,
session comparison, game profile management, and strict zero fabricated FPS.
"""
from pathlib import Path
import tempfile
import unittest

from analyzer.gaming.contracts import (
    GameDetectionSource,
    GameIdentity,
    GamingSessionDNA,
    GamingSessionState,
    NetworkStabilityRating,
    SessionPerformanceCharacteristic,
    SystemPressureRating,
)
from analyzer.gaming.detector import GameDetector
from analyzer.gaming.profile_manager import GameProfileManager
from analyzer.gaming.session_engine import GamingSessionEngine
from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from storage.engine import StorageEngine


def make_obs(metrics: dict) -> Observation:
    measurements = {}
    for k, v in metrics.items():
        measurements[k] = Measurement(
            metric_name=k,
            state=MetricState.AVAILABLE if v is not None else MetricState.UNAVAILABLE,
            value=v,
            unit=MetricUnit.PERCENTAGE,
            source_collector="test_collector",
            provenance="test",
        )
    return Observation(
        observation_id="obs_game_test",
        timestamp_utc="2026-09-28T12:00:00Z",
        collector_name="test_collector",
        measurements=measurements,
        collector_healthy=True,
    )


class TestGamingIntelligence(unittest.TestCase):
    """Tests gaming mode, session state machines, and Session DNA."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_gaming.sqlite")
        self.storage = StorageEngine(self.db_path)
        self.detector = GameDetector()
        self.session_engine = GamingSessionEngine(storage=self.storage, detector=self.detector)
        self.profile_manager = GameProfileManager(storage=self.storage)

    def tearDown(self):
        self.storage.sqlite.close()
        self.temp_dir.cleanup()

    def test_game_detector_registered_signature(self):
        self.detector.register_profile("custom_rpg.exe", "Custom RPG 2026")
        # Direct signature check
        self.assertIn("custom_rpg.exe", self.detector._signatures)
        self.assertEqual(self.detector._signatures["custom_rpg.exe"], "Custom RPG 2026")

        self.detector.unregister_profile("custom_rpg.exe")
        self.assertNotIn("custom_rpg.exe", self.detector._signatures)

    def test_unknown_game_handling(self):
        # When no game is active, detector returns Unknown
        identity = self.detector.detect_active_game()
        if not identity.is_validated:
            self.assertEqual(identity.name, "Unknown")
            self.assertEqual(identity.detection_source, GameDetectionSource.UNKNOWN)
            self.assertFalse(identity.is_validated)

    def test_session_lifecycle_and_zero_fabricated_fps(self):
        game = GameIdentity(name="VALORANT", executable="VALORANT.exe", process_id=1234, is_validated=True)
        session = self.session_engine.start_session(game=game)

        self.assertEqual(session.state, GamingSessionState.ACTIVE)
        self.assertEqual(session.game.name, "VALORANT")
        # CRITICAL: FPS must be None (zero metric fabrication)
        self.assertIsNone(session.fps_telemetry)

        # Buffer observations
        for i in range(10):
            obs = make_obs({
                "cpu_utilization_pct": 45.0,
                "gpu_utilization_pct": 85.0,
                "ram_utilization_pct": 55.0,
                "internet_latency_ms": 22.0,
                "internet_packet_loss_pct": 0.0,
            })
            self.session_engine.record_observation(obs)

        completed = self.session_engine.end_session(GamingSessionState.COMPLETED)
        self.assertIsNotNone(completed)
        self.assertEqual(completed.state, GamingSessionState.COMPLETED)
        self.assertIsNotNone(completed.session_dna)
        self.assertGreaterEqual(completed.session_dna.stability_score, 90.0)
        self.assertEqual(completed.session_dna.network_stability, NetworkStabilityRating.EXCELLENT)
        self.assertIsNone(completed.fps_telemetry)

        # Verify persisted in storage
        persisted = self.storage.get_gaming_session(completed.session_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.game_name, "VALORANT")
        self.assertFalse(persisted.fps_available)

    def test_interrupted_session_handling(self):
        game = GameIdentity(name="Apex Legends", executable="r5apex.exe", process_id=5678, is_validated=True)
        self.session_engine.start_session(game=game)
        interrupted = self.session_engine.interrupt_session()

        self.assertEqual(interrupted.state, GamingSessionState.INTERRUPTED)
        persisted = self.storage.get_gaming_session(interrupted.session_id)
        self.assertEqual(persisted.status, GamingSessionState.INTERRUPTED.value)

    def test_dna_stability_penalty_on_packet_loss(self):
        game = GameIdentity(name="Counter-Strike 2", executable="cs2.exe", process_id=9999, is_validated=True)
        self.session_engine.start_session(game=game)

        for _ in range(10):
            obs = make_obs({
                "cpu_utilization_pct": 80.0,
                "gpu_utilization_pct": 95.0,
                "ram_utilization_pct": 70.0,
                "internet_latency_ms": 90.0,
                "internet_packet_loss_pct": 8.0,  # Heavy packet loss
            })
            self.session_engine.record_observation(obs)

        completed = self.session_engine.end_session()
        self.assertLess(completed.session_dna.stability_score, 80.0)
        self.assertEqual(completed.session_dna.network_stability, NetworkStabilityRating.DEGRADED)

    def test_session_comparison_same_game(self):
        game = GameIdentity(name="Dota 2", executable="dota2.exe", is_validated=True)

        # Session A: Healthy
        self.session_engine.start_session(game=game)
        for _ in range(5):
            self.session_engine.record_observation(make_obs({
                "cpu_utilization_pct": 35.0, "gpu_utilization_pct": 60.0, "ram_utilization_pct": 50.0,
                "internet_latency_ms": 20.0, "internet_packet_loss_pct": 0.0
            }))
        session_a = self.session_engine.end_session()

        # Session B: Degraded
        self.session_engine.start_session(game=game)
        for _ in range(5):
            self.session_engine.record_observation(make_obs({
                "cpu_utilization_pct": 85.0, "gpu_utilization_pct": 60.0, "ram_utilization_pct": 50.0,
                "internet_latency_ms": 80.0, "internet_packet_loss_pct": 5.0
            }))
        session_b = self.session_engine.end_session()

        res = self.session_engine.compare_sessions(session_a, session_b)
        self.assertTrue(res.compatible)
        self.assertIn("avg_cpu_pct", res.metric_comparisons)
        self.assertLess(res.stability_change, 0.0)

    def test_session_comparison_different_games_incompatible(self):
        game_a = GameIdentity(name="VALORANT", executable="VALORANT.exe", is_validated=True)
        game_b = GameIdentity(name="Cyberpunk 2077", executable="Cyberpunk2077.exe", is_validated=True)

        self.session_engine.start_session(game=game_a)
        session_a = self.session_engine.end_session()

        self.session_engine.start_session(game=game_b)
        session_b = self.session_engine.end_session()

        res = self.session_engine.compare_sessions(session_a, session_b)
        self.assertFalse(res.compatible)
        self.assertIn("Incompatible", res.summary)

    def test_profile_creation_and_deletion_preserves_history(self):
        prof = self.profile_manager.create_or_update_profile(
            game_name="Starfield",
            executable="Starfield.exe",
            preferred_metrics=["cpu", "gpu", "vram"],
        )
        self.assertEqual(prof.game_name, "Starfield")

        profiles = self.profile_manager.list_profiles()
        self.assertTrue(any(p.game_name == "Starfield" for p in profiles))

        # Start and save a session for this game
        self.session_engine.start_session(GameIdentity(name="Starfield", executable="Starfield.exe", is_validated=True))
        session = self.session_engine.end_session()

        # Delete profile
        self.profile_manager.delete_profile(prof.profile_id)
        profiles_after = self.profile_manager.list_profiles()
        self.assertFalse(any(p.game_name == "Starfield" for p in profiles_after))

        # Historical session must remain strictly preserved!
        saved_session = self.storage.get_gaming_session(session.session_id)
        self.assertIsNotNone(saved_session)
        self.assertEqual(saved_session.game_name, "Starfield")


if __name__ == "__main__":
    unittest.main()
