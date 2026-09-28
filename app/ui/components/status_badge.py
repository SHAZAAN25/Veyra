"""
VEYRA Status Badge Component.
Renders semantic status indicators with icon glyphs and text labels.
Never relies on color alone to communicate state.
"""
import tkinter as tk
from app.ui.theme import ThemeManager


class StatusBadge(tk.Frame):
    """Pill-shaped badge displaying status with symbol + label."""

    ICONS = {
        "HEALTHY": "[OK]",
        "DEGRADED": "[!]",
        "WARNING": "[WARN]",
        "HIGH": "[HIGH]",
        "CRITICAL": "[CRIT]",
        "UNKNOWN": "[?]",
        "LIVE": "[LIVE]",
        "RECENT": "[REC]",
        "STALE": "[STALE]",
        "UNAVAILABLE": "[-]",
    }

    def __init__(self, parent, theme_manager: ThemeManager, status: str = "UNKNOWN", **kwargs):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self._status = status.upper()

        self._label = tk.Label(
            self,
            text="",
            font=self.theme_manager.font_caption(),
            padx=8,
            pady=3,
            relief=tk.FLAT
        )
        self._label.pack(fill=tk.BOTH, expand=True)
        self.update_status(self._status)

    def update_status(self, status: str) -> None:
        """Updates text and background color according to palette."""
        self._status = status.upper()
        palette = self.theme_manager.get_palette()

        color_map = {
            "HEALTHY": (palette.healthy, palette.bg),
            "LIVE": (palette.healthy, palette.bg),
            "WARNING": (palette.warning, palette.bg),
            "RECENT": (palette.warning, palette.bg),
            "HIGH": (palette.high, "#FFFFFF"),
            "CRITICAL": (palette.critical, "#FFFFFF"),
            "DEGRADED": (palette.high, "#FFFFFF"),
            "STALE": (palette.text_secondary, palette.bg),
            "UNAVAILABLE": (palette.text_secondary, palette.bg),
            "UNKNOWN": (palette.text_secondary, palette.bg),
        }

        fg_color, text_color = color_map.get(self._status, (palette.text_secondary, palette.bg))
        icon = self.ICONS.get(self._status, "")
        display_text = f"{icon} {self._status}"

        self.configure(bg=fg_color, bd=1, relief=tk.SOLID)
        self._label.configure(
            text=display_text,
            bg=fg_color,
            fg=text_color,
            font=self.theme_manager.font_caption()
        )
