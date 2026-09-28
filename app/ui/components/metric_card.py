"""
VEYRA Metric Card Component.
Displays an individual telemetry metric with large value, units, secondary context,
and explicit freshness indicator. Never fabricates values.
"""
import tkinter as tk
from typing import Optional, Any

from app.ui.theme import ThemeManager
from app.ui.components.status_badge import StatusBadge


class MetricCard(tk.Frame):
    """Card widget displaying title, large metric value, unit, and freshness."""

    def __init__(
        self,
        parent,
        theme_manager: ThemeManager,
        title: str,
        initial_value: Optional[Any] = None,
        unit: str = "",
        secondary_text: str = "",
        freshness: str = "UNAVAILABLE",
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.title = title
        self.unit = unit
        self._secondary_text = secondary_text

        palette = self.theme_manager.get_palette()
        self.configure(
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=14,
            pady=12
        )

        # Top row: Title and Freshness Badge
        top_frame = tk.Frame(self, bg=palette.cards)
        top_frame.pack(fill=tk.X, expand=False, anchor=tk.N)

        self.title_label = tk.Label(
            top_frame,
            text=self.title.upper(),
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        )
        self.title_label.pack(side=tk.LEFT, anchor=tk.W)

        self.badge = StatusBadge(top_frame, theme_manager=self.theme_manager, status=freshness)
        self.badge.pack(side=tk.RIGHT, anchor=tk.E)

        # Middle: Value and Unit
        val_frame = tk.Frame(self, bg=palette.cards)
        val_frame.pack(fill=tk.X, expand=True, pady=(8, 4), anchor=tk.W)

        self.value_label = tk.Label(
            val_frame,
            text=self._format_value(initial_value),
            font=self.theme_manager.font_title(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.value_label.pack(side=tk.LEFT, anchor=tk.SW)

        self.unit_label = tk.Label(
            val_frame,
            text=f" {self.unit}" if self.unit else "",
            font=self.theme_manager.font_heading(),
            fg=palette.accent,
            bg=palette.cards
        )
        self.unit_label.pack(side=tk.LEFT, anchor=tk.SW, padx=(2, 0))

        # Bottom: Secondary context
        self.sec_label = tk.Label(
            self,
            text=self._secondary_text,
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards,
            anchor=tk.W,
            justify=tk.LEFT
        )
        self.sec_label.pack(fill=tk.X, anchor=tk.S, pady=(4, 0))

    def _format_value(self, val: Any) -> str:
        if val is None:
            return "Unavailable"
        if isinstance(val, float):
            return f"{val:.1f}"
        if isinstance(val, bool):
            return "Active" if val else "Inactive"
        return str(val)

    def update_metric(
        self,
        value: Optional[Any],
        freshness: str = "LIVE",
        secondary_text: Optional[str] = None
    ) -> None:
        """Updates the displayed value, freshness, and optional secondary context."""
        palette = self.theme_manager.get_palette()
        text_val = self._format_value(value)
        self.value_label.configure(text=text_val)

        # Mute value text if unavailable
        if text_val == "Unavailable":
            self.value_label.configure(fg=palette.text_secondary, font=self.theme_manager.font_heading())
        else:
            self.value_label.configure(fg=palette.text_primary, font=self.theme_manager.font_title())

        self.badge.update_status(freshness)

        if secondary_text is not None:
            self._secondary_text = secondary_text
            self.sec_label.configure(text=self._secondary_text)

    def apply_theme(self) -> None:
        """Refreshes widget styling according to active palette."""
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.title_label.configure(bg=palette.cards, fg=palette.text_secondary)
        self.value_label.configure(bg=palette.cards)
        self.unit_label.configure(bg=palette.cards, fg=palette.accent)
        self.sec_label.configure(bg=palette.cards, fg=palette.text_secondary)
        self.badge.update_status(self.badge._status)
