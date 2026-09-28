"""
VEYRA Gaming Intelligence & Session DNA Screen.
Implements locked Gaming branding, Crimson visual hierarchy, reliable game identification,
real-time gaming session telemetry, and Gaming Session DNA.
Strictly prohibits fabricated FPS.
"""
import tkinter as tk
from typing import Any, Dict, List, Optional

from analyzer.gaming.contracts import (
    GameIdentity,
    GamingSession,
    GamingSessionDNA,
    GamingSessionState,
)
from analyzer.gaming.detector import GameDetector
from analyzer.gaming.profile_manager import GameProfileManager
from analyzer.gaming.session_engine import GamingSessionEngine
from app.ui.components.metric_card import MetricCard
from app.ui.components.status_badge import StatusBadge
from app.ui.state import UiStateManager
from app.ui.theme import ThemeManager
from storage.engine import StorageEngine


class GamingScreen(tk.Frame):
    """Gaming Intelligence and Session DNA monitoring screen."""

    def __init__(
        self,
        parent,
        theme_manager: ThemeManager,
        state_manager: UiStateManager,
        storage: StorageEngine,
        session_engine: Optional[GamingSessionEngine] = None,
        profile_manager: Optional[GameProfileManager] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.state_manager = state_manager
        self.storage = storage
        self.session_engine = session_engine or GamingSessionEngine(storage=self.storage)
        self.profile_manager = profile_manager or GameProfileManager(storage=self.storage)

        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)

        self.container = tk.Frame(self, bg=palette.bg)
        self.container.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # 1. Header Card (Crimson Accent)
        self.header_frame = tk.Frame(
            self.container,
            bg=palette.cards,
            highlightbackground="#FF3045",  # Locked Gaming Crimson
            highlightthickness=1,
            padx=16,
            pady=12
        )
        self.header_frame.pack(fill=tk.X, pady=(0, 16))

        h_left = tk.Frame(self.header_frame, bg=palette.cards)
        h_left.pack(side=tk.LEFT)

        tk.Label(
            h_left,
            text="GAMING PERFORMANCE INTELLIGENCE // PERFORM MODE",
            font=self.theme_manager.font_caption(),
            fg="#FF3045",
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.game_title_lbl = tk.Label(
            h_left,
            text="Game: Unknown",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.game_title_lbl.pack(anchor=tk.W, pady=(2, 0))

        self.game_meta_lbl = tk.Label(
            h_left,
            text="Process: None detected | Source: UNKNOWN",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        )
        self.game_meta_lbl.pack(anchor=tk.W)

        h_right = tk.Frame(self.header_frame, bg=palette.cards)
        h_right.pack(side=tk.RIGHT)

        self.session_badge = StatusBadge(h_right, theme_manager=self.theme_manager, status="HEALTHY")
        self.session_badge.pack(side=tk.LEFT, padx=(0, 12))


        self.session_btn = tk.Button(
            h_right,
            text="Start Gaming Session",
            font=self.theme_manager.font_caption(),
            bg="#FF3045",
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=14,
            pady=4,
            command=self._toggle_session
        )
        self.session_btn.pack(side=tk.LEFT)

        # 2. Session DNA & Telemetry Split Cards
        self.split_frame = tk.Frame(self.container, bg=palette.bg)
        self.split_frame.pack(fill=tk.X, pady=(0, 16))
        self.split_frame.columnconfigure(0, weight=1)
        self.split_frame.columnconfigure(1, weight=1)

        # Left: Gaming Session DNA
        self.dna_card = tk.Frame(
            self.split_frame,
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=16,
            pady=14
        )
        self.dna_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        tk.Label(
            self.dna_card,
            text="GAMING SESSION DNA",
            font=self.theme_manager.font_caption(),
            fg="#FF3045",
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.stability_score_lbl = tk.Label(
            self.dna_card,
            text="Stability: -- / 100",
            font=("Segoe UI", 16, "bold"),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.stability_score_lbl.pack(anchor=tk.W, pady=(4, 2))

        self.dna_char_lbl = tk.Label(
            self.dna_card,
            text="Characteristic: STANDBY | System: NOMINAL | Network: GOOD",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        )
        self.dna_char_lbl.pack(anchor=tk.W)

        self.dna_summary_lbl = tk.Label(
            self.dna_card,
            text="Start or detect an active game session to compute session stability and workload characteristics.",
            font=self.theme_manager.font_body(),
            fg=palette.text_secondary,
            bg=palette.cards,
            justify=tk.LEFT,
            wraplength=450
        )
        self.dna_summary_lbl.pack(anchor=tk.W, pady=(8, 0))

        # Right: FPS Integrity Notice & Real Telemetry Highlights
        self.telemetry_card = tk.Frame(
            self.split_frame,
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=16,
            pady=14
        )
        self.telemetry_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        tk.Label(
            self.telemetry_card,
            text="FRAME RATE INTEGRITY & TELEMETRY",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.fps_lbl = tk.Label(
            self.telemetry_card,
            text="FPS: Unavailable",
            font=("Segoe UI", 16, "bold"),
            fg=palette.warning,
            bg=palette.cards
        )
        self.fps_lbl.pack(anchor=tk.W, pady=(4, 2))

        tk.Label(
            self.telemetry_card,
            text="Veyra strictly adheres to Zero Metric Fabrication. In-game rendering telemetry (FPS/frame times) requires dedicated hooking tools and is never simulated or guessed.",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards,
            justify=tk.LEFT,
            wraplength=450
        ).pack(anchor=tk.W, pady=(2, 0))

        # 3. Live Metrics Row
        self.metrics_frame = tk.Frame(self.container, bg=palette.bg)
        self.metrics_frame.pack(fill=tk.X, pady=(0, 16))

        self.card_cpu = MetricCard(self.metrics_frame, title="CPU LOAD", unit="%", theme_manager=self.theme_manager)
        self.card_cpu.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        self.card_gpu = MetricCard(self.metrics_frame, title="GPU CORE", unit="%", theme_manager=self.theme_manager)
        self.card_gpu.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        self.card_ram = MetricCard(self.metrics_frame, title="RAM LOAD", unit="%", theme_manager=self.theme_manager)
        self.card_ram.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        self.card_lat = MetricCard(self.metrics_frame, title="NETWORK RTT", unit="ms", theme_manager=self.theme_manager)
        self.card_lat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        # 4. Historical Gaming Sessions Table
        self.history_card = tk.Frame(
            self.container,
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=16,
            pady=14
        )
        self.history_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            self.history_card,
            text="RECENT GAMING SESSIONS & STABILITY DNA",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 8))

        self.sessions_list_frame = tk.Frame(self.history_card, bg=palette.cards)
        self.sessions_list_frame.pack(fill=tk.BOTH, expand=True)

        self._refresh_history_table()

    def _toggle_session(self):
        """Starts or ends a manual gaming session."""
        if self.session_engine.is_session_active:
            completed = self.session_engine.end_session()
            self.session_btn.configure(text="Start Gaming Session", bg="#FF3045")
            self.session_badge.update_status("HEALTHY")
            if completed and completed.session_dna:
                self.stability_score_lbl.configure(text=f"Stability: {completed.session_dna.stability_score:.1f} / 100")
                self.dna_summary_lbl.configure(text=completed.session_dna.summary)
            self._refresh_history_table()
        else:
            self.session_engine.start_session()
            self.session_btn.configure(text="End Gaming Session", bg=self.theme_manager.get_palette().cards)
            self.session_badge.update_status("LIVE")
            self._update_game_identity()


    def _update_game_identity(self):
        """Detects active game and updates banner."""
        palette = self.theme_manager.get_palette()
        active = self.session_engine.active_session
        if active and active.game.is_validated:
            self.game_title_lbl.configure(text=f"Game: {active.game.name}")
            self.game_meta_lbl.configure(
                text=f"Process: {active.game.executable} [PID {active.game.process_id}] | Source: {active.game.detection_source.value}"
            )
        else:
            # Poll detector
            detected = self.session_engine.detector.detect_active_game()
            if detected.is_validated:
                self.game_title_lbl.configure(text=f"Game: {detected.name}")
                self.game_meta_lbl.configure(
                    text=f"Process: {detected.executable} [PID {detected.process_id}] | Source: {detected.detection_source.value}"
                )
            else:
                self.game_title_lbl.configure(text="Game: Unknown")
                self.game_meta_lbl.configure(text="No known game process running | Source: UNKNOWN")

    def _refresh_history_table(self):
        """Renders recent gaming sessions from SQLite storage."""
        palette = self.theme_manager.get_palette()
        for child in self.sessions_list_frame.winfo_children():
            child.destroy()

        try:
            sessions = self.storage.list_gaming_sessions(limit=5)
            if not sessions:
                tk.Label(
                    self.sessions_list_frame,
                    text="No previous gaming sessions recorded in SQLite history.",
                    font=self.theme_manager.font_caption(),
                    fg=palette.text_secondary,
                    bg=palette.cards
                ).pack(anchor=tk.W, pady=8)
                return

            for s in sessions:
                row = tk.Frame(self.sessions_list_frame, bg=palette.cards, pady=4)
                row.pack(fill=tk.X)

                dna = s.to_dict().get("session_dna", {})
                score = dna.get("stability_score", "--")

                tk.Label(
                    row,
                    text=s.game_name,
                    font=("Segoe UI", 9, "bold"),
                    fg=palette.text_primary,
                    bg=palette.cards,
                    width=20,
                    anchor=tk.W
                ).pack(side=tk.LEFT)

                tk.Label(
                    row,
                    text=f"Duration: {s.duration_seconds:.0f}s | Status: {s.status}",
                    font=("Segoe UI", 9),
                    fg=palette.text_secondary,
                    bg=palette.cards,
                    width=25,
                    anchor=tk.W
                ).pack(side=tk.LEFT)

                cpu_str = f"CPU: {s.avg_cpu_pct}%" if s.avg_cpu_pct else "CPU: --"
                lat_str = f"RTT: {s.avg_latency_ms}ms" if s.avg_latency_ms else "RTT: --"
                tk.Label(
                    row,
                    text=f"{cpu_str} | {lat_str}",
                    font=("Segoe UI", 9),
                    fg=palette.text_secondary,
                    bg=palette.cards,
                    width=25,
                    anchor=tk.W
                ).pack(side=tk.LEFT)

                tk.Label(
                    row,
                    text=f"DNA Stability: {score}/100",
                    font=("Segoe UI", 9, "bold"),
                    fg="#FF3045",
                    bg=palette.cards
                ).pack(side=tk.RIGHT)
        except Exception:
            pass

    def update_data(self):
        """Called periodically by UI polling loop."""
        self._update_game_identity()

        # Update metric cards from state manager
        telemetry = self.state_manager.current_telemetry
        if telemetry:
            def gv(k):
                m = telemetry.get_metric(k)
                return m.value if m and m.value is not None else None

            cpu = gv("cpu_utilization_pct")
            gpu = gv("gpu_utilization_pct")
            ram = gv("ram_utilization_pct")
            lat = gv("internet_latency_ms")

            self.card_cpu.update_value(cpu)
            self.card_gpu.update_value(gpu)
            self.card_ram.update_value(ram)
            self.card_lat.update_value(lat)

            # Record into session buffer if session is active
            if self.session_engine.is_session_active:
                self.session_engine.record_observation(telemetry)
