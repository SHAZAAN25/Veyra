"""
VEYRA Incident Card Component.
Displays individual incident summary with severity badges, duration, root cause,
and selection hooks for detailed investigation and replay.
"""
import tkinter as tk
from typing import Callable, Optional

from app.ui.theme import ThemeManager
from app.ui.components.status_badge import StatusBadge
from storage.contracts import IncidentRecord


class IncidentCard(tk.Frame):
    """Selectable card presenting an individual incident summary."""

    def __init__(
        self,
        parent,
        theme_manager: ThemeManager,
        incident: IncidentRecord,
        on_select: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.incident = incident
        self.on_select = on_select

        palette = self.theme_manager.get_palette()
        self.configure(
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=12,
            pady=10,
            cursor="hand2"
        )

        # Header: Incident Type and Severity Badge
        top_frame = tk.Frame(self, bg=palette.cards)
        top_frame.pack(fill=tk.X, expand=True)

        self.title_label = tk.Label(
            top_frame,
            text=self.incident.incident_type.replace("_", " "),
            font=self.theme_manager.font_subheading(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.title_label.pack(side=tk.LEFT)

        self.badge = StatusBadge(top_frame, theme_manager=self.theme_manager, status=self.incident.severity)
        self.badge.pack(side=tk.RIGHT)

        # Summary line
        self.summary_label = tk.Label(
            self,
            text=self.incident.summary,
            font=self.theme_manager.font_body(),
            fg=palette.text_secondary,
            bg=palette.cards,
            anchor=tk.W,
            justify=tk.LEFT
        )
        self.summary_label.pack(fill=tk.X, pady=(4, 2))

        # Metadata line: Root cause & Time
        dur_str = f"{self.incident.duration_seconds:.1f}s" if self.incident.duration_seconds > 0 else "Active"
        meta_text = f"Cause: {self.incident.primary_cause}  |  Duration: {dur_str}  |  Started: {self.incident.started_at_utc}"
        self.meta_label = tk.Label(
            self,
            text=meta_text,
            font=self.theme_manager.font_caption(),
            fg=palette.accent,
            bg=palette.cards,
            anchor=tk.W
        )
        self.meta_label.pack(fill=tk.X, pady=(2, 0))

        # Bind click handlers
        for widget in (self, self.title_label, self.summary_label, self.meta_label, top_frame):
            widget.bind("<Button-1>", lambda e: self._handle_click())

    def _handle_click(self) -> None:
        if self.on_select:
            self.on_select(self.incident.incident_id)

    def apply_theme(self) -> None:
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.title_label.configure(bg=palette.cards, fg=palette.text_primary)
        self.summary_label.configure(bg=palette.cards, fg=palette.text_secondary)
        self.meta_label.configure(bg=palette.cards, fg=palette.accent)
        self.badge.update_status(self.incident.severity)
