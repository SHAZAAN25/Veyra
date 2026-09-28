"""
VEYRA Desktop Application Shell.
Integrates navigation, screen container, asynchronous background telemetry polling,
dynamic theme management, and non-blocking monitoring execution.
"""
import tkinter as tk
from typing import Dict, Optional

from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager
from app.ui.navigation import NavigationSidebar
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
from storage.engine import StorageEngine
from collectors.coordinator import CollectionCoordinator
from analyzer.engine import IntelligenceEngine



class VeyraDesktopApp:
    """Primary Stage 4 Windows Desktop Application."""

    def __init__(
        self,
        root: tk.Tk,
        storage: StorageEngine,
        coordinator: Optional[CollectionCoordinator] = None,
        intelligence_engine: Optional[IntelligenceEngine] = None,
        theme_manager: Optional[ThemeManager] = None,
        state_manager: Optional[UiStateManager] = None,
        pipeline: Optional[Any] = None,
        detector: Optional[Any] = None,
    ):
        self.root = root
        self.storage = storage
        self.coordinator = coordinator or pipeline
        self.intelligence_engine = intelligence_engine or detector
        self.pipeline = self.coordinator
        self.detector = self.intelligence_engine
        self.theme_manager = theme_manager or ThemeManager()
        self.state_manager = state_manager or UiStateManager(self.storage)

        # Window Setup
        self.root.title("VEYRA — PC Observability & Incident Intelligence")
        self.root.geometry("1280x800")
        self.root.minsize(1024, 680)

        palette = self.theme_manager.get_palette()
        self.root.configure(bg=palette.bg)

        # Main Layout: Sidebar (Left) + Content Area (Right)
        self.sidebar = NavigationSidebar(
            self.root,
            theme_manager=self.theme_manager,
            on_navigate=self.navigate_to
        )
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        self.content_container = tk.Frame(self.root, bg=palette.bg)
        self.content_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Instantiate Screens
        self.screens: Dict[str, tk.Frame] = {
            "dashboard": DashboardScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "network": NetworkScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "system": SystemScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "incidents": IncidentsScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "history": HistoryScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "what_changed": WhatChangedScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "diagnostics": DiagnosticsScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "gaming": GamingScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "optimization": OptimizationScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "ask_veyra": AskVeyraScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
            "settings": SettingsScreen(self.content_container, theme_manager=self.theme_manager, state_manager=self.state_manager, storage=self.storage),
        }


        self.current_screen_id = "dashboard"
        self.screens["dashboard"].pack(fill=tk.BOTH, expand=True)

        self.theme_manager.register_listener(self.apply_theme)

        # Schedule live polling loop (1.5 second UI refresh, non-blocking)
        self._poll_telemetry()

    def navigate_to(self, route_id: str):
        if route_id not in self.screens or route_id == self.current_screen_id:
            return

        # Handle Gaming Mode Palette Dynamic Switching
        if route_id == "gaming":
            self.theme_manager.set_mode("gaming")
        elif self.theme_manager.mode == "gaming":
            self.theme_manager.set_mode("normal")

        # Hide current screen
        self.screens[self.current_screen_id].pack_forget()

        # Show target screen
        self.screens[route_id].pack(fill=tk.BOTH, expand=True)
        self.current_screen_id = route_id
        self.sidebar.set_active_route(route_id)

        # Immediately refresh data on view entry
        if hasattr(self.screens[route_id], "update_data"):
            self.screens[route_id].update_data()


    def _poll_telemetry(self):
        """Non-blocking periodic update using root.after."""
        try:
            # If collector coordinator is running locally in this process
            if self.coordinator:
                if hasattr(self.coordinator, "run_cycle"):
                    cycle = self.coordinator.run_cycle()
                    primary_obs = cycle.get("cpu") or (next(iter(cycle.values())) if cycle else None)
                    active_incidents = []
                    recent_changes = []
                    if self.intelligence_engine and hasattr(self.intelligence_engine, "process_cycle"):
                        report = self.intelligence_engine.process_cycle(cycle)
                        active_incidents = report.active_incidents
                        recent_changes = report.recent_changes
                    self.state_manager.update_telemetry(
                        observation=primary_obs,
                        active_incidents=active_incidents,
                        recent_changes=recent_changes,
                    )
                elif hasattr(self.coordinator, "collect_snapshot"):
                    snap = self.coordinator.collect_snapshot()
                    assessment = None
                    if self.intelligence_engine and hasattr(self.intelligence_engine, "analyze"):
                        assessment = self.intelligence_engine.analyze(snap)
                    self.state_manager.update_telemetry(snap, assessment)

            # Update active screen data
            active_screen = self.screens.get(self.current_screen_id)
            if active_screen and hasattr(active_screen, "update_data"):
                active_screen.update_data()
        except Exception:
            pass

        # Schedule next tick in 1500 ms
        self.root.after(1500, self._poll_telemetry)

    def apply_theme(self):
        palette = self.theme_manager.get_palette()
        self.root.configure(bg=palette.bg)
        self.content_container.configure(bg=palette.bg)
