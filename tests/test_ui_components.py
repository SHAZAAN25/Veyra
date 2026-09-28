"""
Stage 4 Tests: UI Components and Screen Rendering.
Verifies StatusBadge, MetricCard, HistoricalCanvasChart, ReplayViewer,
DashboardScreen, NetworkScreen, SystemScreen, IncidentsScreen, HistoryScreen,
and SettingsScreen instantiate and update properly in headless Tkinter.
"""
import unittest
import tkinter as tk
from pathlib import Path
import tempfile
import time

from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager
from app.ui.components.status_badge import StatusBadge
from app.ui.components.metric_card import MetricCard
from app.ui.components.chart import HistoricalCanvasChart
from app.ui.components.replay_viewer import ReplayViewer
from app.ui.screens.dashboard import DashboardScreen
from app.ui.screens.network import NetworkScreen
from app.ui.screens.system import SystemScreen
from app.ui.screens.incidents import IncidentsScreen
from app.ui.screens.history import HistoryScreen
from app.ui.screens.what_changed import WhatChangedScreen
from app.ui.screens.diagnostics import DiagnosticsScreen
from app.ui.screens.gaming import GamingScreen
from app.ui.screens.optimization import OptimizationScreen
from app.ui.screens.ask_veyra import AskVeyraScreen
from app.ui.screens.settings import SettingsScreen

from app.ui.navigation import NavigationSidebar
from app.core.contracts import Observation, Assessment, Measurement, MetricState, MetricUnit
from storage.engine import StorageEngine


class TestUiComponentsAndScreens(unittest.TestCase):
    """Instantiates and tests Tkinter widgets headlessly."""

    @classmethod
    def setUpClass(cls):
        # Create root window hidden
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_ui.sqlite")
        self.storage = StorageEngine(self.db_path)
        self.theme_manager = ThemeManager()
        self.state_manager = UiStateManager()

    def tearDown(self):
        self.storage.sqlite.close()
        self.temp_dir.cleanup()

    def test_status_badge_updates(self):
        badge = StatusBadge(self.root, theme_manager=self.theme_manager, status="HEALTHY")
        self.assertEqual(badge._status, "HEALTHY")
        badge.update_status("CRITICAL")
        self.assertEqual(badge._status, "CRITICAL")
        badge.destroy()

    def test_metric_card_updates(self):
        card = MetricCard(self.root, theme_manager=self.theme_manager, title="PING", unit="ms")
        card.update_metric(14.2, freshness="LIVE", secondary_text="Baseline: 15.0 ms")
        self.assertEqual(card.value_label.cget("text"), "14.2")
        self.assertEqual(card.unit_label.cget("text"), " ms")
        card.destroy()

    def test_historical_canvas_chart_rendering(self):
        chart = HistoricalCanvasChart(self.root, theme_manager=self.theme_manager, height=200)
        chart.set_data([], title="Test Metric", unit="ms")
        self.assertIsNotNone(chart.winfo_id())
        chart.destroy()

    def test_replay_viewer_phases(self):
        viewer = ReplayViewer(self.root, theme_manager=self.theme_manager)
        replay_payload = {
            "incident": {
                "incident_id": "inc-test",
                "incident_type": "LATENCY_SPIKE",
                "severity": "WARNING",
                "started_at_utc": "2026-09-28T12:00:00Z",
                "ended_at_utc": "2026-09-28T12:05:00Z",
                "duration_seconds": 300.0,
                "summary": "High Latency Spike",
                "primary_cause": "Bufferbloat",
                "cause_explanation": "Network bufferbloat detected on default gateway.",
                "confidence_score": 0.88,
                "affected_layers": ["LAYER_3"],
                "status": "RECOVERED"
            },
            "answers": {
                "what_was_normal": {"ping_ms": {"mean": 12.0, "min": 10.0, "max": 15.0}},
                "what_changed": {"trigger_metric": "ping_ms", "trigger_value": 115.0},
                "what_failed": {
                    "primary_cause": "Bufferbloat",
                    "cause_explanation": "Network bufferbloat detected on default gateway.",
                    "confidence_score": 0.88,
                    "affected_layers": ["LAYER_3"],
                    "severity": "WARNING",
                    "duration_seconds": 300.0
                },
                "what_recovered": {
                    "status": "RECOVERED",
                    "recovery_value": 13.0,
                    "ended_at_utc": "2026-09-28T12:05:00Z"
                },
                "what_remained_degraded": []
            }
        }
        viewer.load_replay(replay_payload)
        viewer.select_phase("EVENT")
        self.assertIn("ANOMALY TRIGGER", viewer.details_label.cget("text"))
        viewer.clear()
        viewer.destroy()

    def test_screens_instantiation_and_update(self):
        # 1. DashboardScreen
        dashboard = DashboardScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        dashboard.update_data()
        dashboard.destroy()

        # 2. NetworkScreen
        network = NetworkScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        network.update_data()
        network.destroy()

        # 3. SystemScreen
        system = SystemScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        system.update_data()
        system.destroy()

        # 4. IncidentsScreen
        incidents = IncidentsScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        incidents.update_data()
        incidents.destroy()

        # 5. HistoryScreen
        history = HistoryScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        history.update_data()
        history.destroy()

        # 6. WhatChangedScreen
        what_changed = WhatChangedScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        what_changed.update_data()
        what_changed.destroy()

        # 7. DiagnosticsScreen
        diag = DiagnosticsScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        diag.update_data()
        diag.destroy()

        # 8. GamingScreen
        gaming = GamingScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        gaming.update_data()
        gaming.destroy()

        # 9. OptimizationScreen
        opt = OptimizationScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        opt.update_data()
        opt.destroy()

        # 10. AskVeyraScreen
        ask = AskVeyraScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        ask.update_data()
        ask.destroy()

        # 11. SettingsScreen
        settings = SettingsScreen(self.root, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage)
        settings.update_data()
        settings.destroy()


    def test_navigation_sidebar_routes(self):
        nav_selected = []
        sidebar = NavigationSidebar(
            self.root,
            theme_manager=self.theme_manager,
            on_navigate=lambda r: nav_selected.append(r)
        )
        sidebar._handle_click("network")
        self.assertIn("network", nav_selected)
        self.assertEqual(sidebar.active_route, "network")
        sidebar.destroy()


if __name__ == "__main__":
    unittest.main()
