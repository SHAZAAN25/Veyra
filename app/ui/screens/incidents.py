"""
VEYRA Incidents & Investigation Screen.
Lists active and resolved incidents with filtering by severity and subsystem,
and provides deep incident inspection with embedded Incident Replay visualization.
"""
import tkinter as tk
from typing import Optional, List, Dict, Any

from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager
from app.ui.components.status_badge import StatusBadge
from app.ui.components.incident_card import IncidentCard
from app.ui.components.replay_viewer import ReplayViewer
from storage.engine import StorageEngine


class IncidentsScreen(tk.Frame):
    """Incidents overview and deep investigation screen."""

    def __init__(
        self,
        parent,
        theme_manager: ThemeManager,
        state_manager: UiStateManager,
        storage: StorageEngine,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.state_manager = state_manager
        self.storage = storage
        self.selected_incident_id: Optional[str] = None

        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)

        self.container = tk.Frame(self, bg=palette.bg)
        self.container.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # 1. Header & Filter Bar
        self.header_frame = tk.Frame(self.container, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=12)
        self.header_frame.pack(fill=tk.X, pady=(0, 16))

        h_left = tk.Frame(self.header_frame, bg=palette.cards)
        h_left.pack(side=tk.LEFT)

        tk.Label(
            h_left,
            text="INCIDENT INTELLIGENCE & FLIGHT RECORDER",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.summary_lbl = tk.Label(
            h_left,
            text="Investigating system & network anomalies across time",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.summary_lbl.pack(anchor=tk.W, pady=(2, 0))

        # Severity filter buttons
        h_right = tk.Frame(self.header_frame, bg=palette.cards)
        h_right.pack(side=tk.RIGHT)

        tk.Label(
            h_right,
            text="FILTER:",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.filter_var = tk.StringVar(value="ALL")
        for f_name in ["ALL", "CRITICAL", "HIGH", "WARNING"]:
            btn = tk.Radiobutton(
                h_right,
                text=f_name,
                variable=self.filter_var,
                value=f_name,
                command=self._on_filter_changed,
                bg=palette.cards,
                fg=palette.text_primary,
                selectcolor=palette.cards_secondary,
                activebackground=palette.cards,
                activeforeground=palette.accent,
                font=self.theme_manager.font_caption()
            )
            btn.pack(side=tk.LEFT, padx=4)

        # 2. Main split view: Incident List (Left, 40%) vs Detail & Replay (Right, 60%)
        self.split_frame = tk.Frame(self.container, bg=palette.bg)
        self.split_frame.pack(fill=tk.BOTH, expand=True)
        self.split_frame.columnconfigure(0, weight=4)
        self.split_frame.columnconfigure(1, weight=6)
        self.split_frame.rowconfigure(0, weight=1)

        # Left: Incident Scrollable List
        self.list_panel = tk.Frame(self.split_frame, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=12, pady=12)
        self.list_panel.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        tk.Label(
            self.list_panel,
            text="RECORDED INCIDENTS",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 8))

        self.list_canvas = tk.Canvas(self.list_panel, bg=palette.cards, highlightthickness=0)
        self.list_scrollbar = tk.Scrollbar(self.list_panel, orient=tk.VERTICAL, command=self.list_canvas.yview)
        self.list_inner = tk.Frame(self.list_canvas, bg=palette.cards)

        self.list_inner.bind("<Configure>", lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.canvas_window = self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_canvas.bind("<Configure>", lambda e: self.list_canvas.itemconfig(self.canvas_window, width=e.width))

        self.list_canvas.configure(yscrollcommand=self.list_scrollbar.set)
        self.list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right: Incident Replay & Deep Inspection
        self.detail_panel = tk.Frame(self.split_frame, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=12)
        self.detail_panel.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        tk.Label(
            self.detail_panel,
            text="INCIDENT INVESTIGATION & REPLAY",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 8))

        self.replay_viewer = ReplayViewer(self.detail_panel, theme_manager=self.theme_manager)
        self.replay_viewer.pack(fill=tk.BOTH, expand=True)

        self.theme_manager.register_listener(self.apply_theme)

    def _on_filter_changed(self):
        self.update_data()

    def _select_incident(self, incident_id: str):
        self.selected_incident_id = incident_id
        replay_data = self.storage.replay.reconstruct_replay(incident_id)
        if replay_data:
            self.replay_viewer.load_replay(replay_data)
        else:
            self.replay_viewer.clear()

    def update_data(self):
        """Fetches persisted incidents and populates the list view."""
        palette = self.theme_manager.get_palette()
        filter_sev = self.filter_var.get()
        
        # Clear existing incident cards
        for widget in self.list_inner.winfo_children():
            widget.destroy()

        try:
            records = self.storage.sqlite.query_incident_records(limit=30)
            incidents = [r.to_dict() for r in records]
            if filter_sev != "ALL":
                incidents = [inc for inc in incidents if inc.get("severity") == filter_sev]

            self.summary_lbl.configure(text=f"{len(incidents)} Incidents Recorded | Storage: Stage 3 SQLite")

            if not incidents:
                empty_lbl = tk.Label(
                    self.list_inner,
                    text="No incidents matching current criteria.\nSystem and network operating stably.",
                    font=self.theme_manager.font_body(),
                    fg=palette.text_secondary,
                    bg=palette.cards,
                    pady=30
                )
                empty_lbl.pack(fill=tk.BOTH, expand=True)
                if not self.selected_incident_id:
                    self.replay_viewer.clear()
                return

            for inc in incidents:
                inc_id = inc.get("incident_id", "")
                card = IncidentCard(
                    self.list_inner,
                    theme_manager=self.theme_manager,
                    incident_data=inc,
                    on_click=lambda i_id=inc_id: self._select_incident(i_id)
                )
                card.pack(fill=tk.X, pady=4)

            # Auto-select the first incident if none selected or selection invalid
            if (not self.selected_incident_id or not any(i.get("incident_id") == self.selected_incident_id for i in incidents)):
                first_id = incidents[0].get("incident_id")
                self._select_incident(first_id)

        except Exception as e:
            err_lbl = tk.Label(
                self.list_inner,
                text=f"Failed to query incidents: {e}",
                font=self.theme_manager.font_caption(),
                fg=palette.critical,
                bg=palette.cards,
                pady=20
            )
            err_lbl.pack()

    def apply_theme(self):
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)
        self.container.configure(bg=palette.bg)
        self.header_frame.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.split_frame.configure(bg=palette.bg)
        self.list_panel.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.list_canvas.configure(bg=palette.cards)
        self.list_inner.configure(bg=palette.cards)
        self.detail_panel.configure(bg=palette.cards, highlightbackground=palette.borders)
