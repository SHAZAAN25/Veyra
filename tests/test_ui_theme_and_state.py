"""
Stage 4 Tests: UI Theme, Mode, Freshness & State Management.
Verifies ThemeManager (Dark, Light, System, Normal Cyan, Gaming Crimson),
reduced motion preferences, UiStateManager freshness calculations,
and deterministic overall health calculation.
"""
import unittest
import time
from pathlib import Path
import tempfile

from app.ui.theme import ThemeManager, PALETTE_NORMAL_DARK, PALETTE_NORMAL_LIGHT, PALETTE_GAMING
from app.ui.state import UiStateManager
from app.core.contracts import Observation, Assessment, Measurement, MetricState, MetricUnit
from analyzer.contracts import DetailedIncident, IncidentType, IncidentSeverity, IncidentStatus
from storage.engine import StorageEngine


class TestUiThemeAndState(unittest.TestCase):
    """Verifies theme engine and state calculation without Tkinter window rendering."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_state.sqlite")
        self.storage = StorageEngine(self.db_path)
        self.theme_manager = ThemeManager()
        self.state_manager = UiStateManager()

    def tearDown(self):
        self.storage.sqlite.close()
        self.temp_dir.cleanup()

    def test_default_theme_is_dark(self):
        palette = self.theme_manager.get_palette()
        self.assertEqual(palette.bg, "#0B0D10")
        self.assertEqual(palette.accent, "#27D3E6")
        self.assertEqual(self.theme_manager.current_mode, "NORMAL")
        self.assertFalse(self.theme_manager.reduced_motion)

    def test_theme_switching_light_dark(self):
        self.theme_manager.set_theme("light")
        light_pal = self.theme_manager.get_palette()
        self.assertEqual(light_pal.bg, "#F8F9FA")
        self.assertEqual(light_pal.accent, "#0099AA")

        self.theme_manager.set_theme("dark")
        dark_pal = self.theme_manager.get_palette()
        self.assertEqual(dark_pal.bg, "#0B0D10")

    def test_gaming_mode_palette_switch(self):
        self.theme_manager.set_mode("GAMING")
        gaming_pal = self.theme_manager.get_palette()
        self.assertEqual(gaming_pal.bg, "#080A0C")
        self.assertEqual(gaming_pal.accent, "#FF3045")
        self.assertEqual(gaming_pal.critical, "#FF4655")

        self.theme_manager.set_mode("NORMAL")
        normal_pal = self.theme_manager.get_palette()
        self.assertEqual(normal_pal.accent, "#27D3E6")

    def test_theme_listener_notification(self):
        events = []
        self.theme_manager.register_listener(lambda: events.append("THEME_CHANGED"))
        self.theme_manager.set_theme("light")
        self.assertEqual(len(events), 1)

    def test_reduced_motion_toggle(self):
        self.assertFalse(self.theme_manager.reduced_motion)
        self.theme_manager.set_reduced_motion(True)
        self.assertTrue(self.theme_manager.reduced_motion)

    def test_freshness_calculation(self):
        now_mono = time.monotonic()
        # 1. No observation -> UNAVAILABLE
        self.assertEqual(self.state_manager.calculate_freshness(now_mono), "UNAVAILABLE")

        obs = Observation(
            observation_id="obs-1",
            timestamp_utc="2026-09-28T12:00:00Z",
            collector_name="coordinator",
            measurements={},
            collector_healthy=True
        )

        # 2. LIVE snapshot (<= 3.0s)
        self.state_manager.update_telemetry(obs)
        self.assertEqual(self.state_manager.calculate_freshness(self.state_manager.last_update_monotonic + 1.0), "LIVE")

        # 3. RECENT snapshot (<= 10.0s)
        self.assertEqual(self.state_manager.calculate_freshness(self.state_manager.last_update_monotonic + 6.0), "RECENT")

        # 4. STALE snapshot (<= 30.0s)
        self.assertEqual(self.state_manager.calculate_freshness(self.state_manager.last_update_monotonic + 20.0), "STALE")

        # 5. UNAVAILABLE (> 30.0s)
        self.assertEqual(self.state_manager.calculate_freshness(self.state_manager.last_update_monotonic + 45.0), "UNAVAILABLE")

    def test_deterministic_overall_health_calculation(self):
        # 1. No observation -> UNKNOWN
        self.assertEqual(self.state_manager.calculate_overall_health(), "UNKNOWN")

        # 2. Healthy observation
        obs = Observation(
            observation_id="obs-1",
            timestamp_utc="2026-09-28T12:00:00Z",
            collector_name="coordinator",
            measurements={},
            collector_healthy=True
        )
        self.state_manager.update_telemetry(obs)
        self.assertEqual(self.state_manager.calculate_overall_health(), "HEALTHY")

        # 3. Collector degraded
        obs_degraded = Observation(
            observation_id="obs-2",
            timestamp_utc="2026-09-28T12:00:00Z",
            collector_name="coordinator",
            measurements={},
            collector_healthy=False
        )
        self.state_manager.update_telemetry(obs_degraded)
        self.assertEqual(self.state_manager.calculate_overall_health(), "DEGRADED")

        # 4. Warning incident
        warn_incident = DetailedIncident(
            incident_id="inc-1",
            incident_type=IncidentType.LATENCY_SPIKE,
            severity=IncidentSeverity.WARNING,
            status=IncidentStatus.ACTIVE,
            started_at_utc="2026-09-28T12:00:00Z",
            ended_at_utc=None,
            duration_seconds=10.0,
            summary="High Latency Detected",
            root_cause=None,
            affected_layers=["LAYER_4"],
            correlation_id="corr-1",
            evidence_window=None
        )
        self.state_manager.update_telemetry(obs, active_incidents=[warn_incident])
        self.assertEqual(self.state_manager.calculate_overall_health(), "WARNING")

        # 5. Critical incident overrides warning
        crit_incident = DetailedIncident(
            incident_id="inc-2",
            incident_type=IncidentType.GATEWAY_UNREACHABLE,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.ACTIVE,
            started_at_utc="2026-09-28T12:00:00Z",
            ended_at_utc=None,
            duration_seconds=10.0,
            summary="Gateway Down",
            root_cause=None,
            affected_layers=["LAYER_3"],
            correlation_id="corr-2",
            evidence_window=None
        )
        self.state_manager.update_telemetry(obs, active_incidents=[warn_incident, crit_incident])
        self.assertEqual(self.state_manager.calculate_overall_health(), "CRITICAL")


if __name__ == "__main__":
    unittest.main()
