"""
VEYRA PC Timeline View Component.
Displays chronological event markers for incidents, network changes, and regressions.
"""
import tkinter as tk
from typing import List, Optional

from app.ui.theme import ThemeManager
from storage.contracts import TimelineEventRecord


class TimelineView(tk.Frame):
    """Chronological event feed component."""

    def __init__(self, parent, theme_manager: ThemeManager, max_items: int = 15, **kwargs):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.max_items = max_items
        self._events: List[TimelineEventRecord] = []

        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=14, pady=12)

        self.title_label = tk.Label(
            self,
            text="PC TIMELINE HIGHLIGHTS",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards,
            anchor=tk.W
        )
        self.title_label.pack(fill=tk.X, pady=(0, 8))

        self.list_container = tk.Frame(self, bg=palette.cards)
        self.list_container.pack(fill=tk.BOTH, expand=True)

    def set_events(self, events: List[TimelineEventRecord]) -> None:
        """Populates the timeline with events."""
        self._events = events[:self.max_items]
        self._render()

    def _render(self) -> None:
        for child in self.list_container.winfo_children():
            child.destroy()

        palette = self.theme_manager.get_palette()

        if not self._events:
            empty_lbl = tk.Label(
                self.list_container,
                text="No events recorded on timeline yet.",
                font=self.theme_manager.font_body(),
                fg=palette.text_secondary,
                bg=palette.cards,
                anchor=tk.W
            )
            empty_lbl.pack(fill=tk.X, pady=8)
            return

        for ev in self._events:
            row = tk.Frame(self.list_container, bg=palette.cards, pady=4)
            row.pack(fill=tk.X, expand=True)

            t_str = ev.timestamp_utc.split("T")[-1][:8] if "T" in ev.timestamp_utc else ev.timestamp_utc

            t_lbl = tk.Label(
                row,
                text=t_str,
                font=self.theme_manager.font_mono(),
                fg=palette.accent,
                bg=palette.cards,
                width=10,
                anchor=tk.W
            )
            t_lbl.pack(side=tk.LEFT)

            type_color = palette.critical if ev.severity in ("CRITICAL", "HIGH") else (palette.warning if ev.severity == "WARNING" else palette.text_primary)
            summary_lbl = tk.Label(
                row,
                text=f"[{ev.event_type}] {ev.summary}",
                font=self.theme_manager.font_body(),
                fg=type_color,
                bg=palette.cards,
                anchor=tk.W,
                justify=tk.LEFT
            )
            summary_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

    def apply_theme(self) -> None:
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.title_label.configure(bg=palette.cards, fg=palette.text_secondary)
        self.list_container.configure(bg=palette.cards)
        self._render()
