"""
VEYRA Sidebar Navigation Component.
Displays locked official branding logo and manages screen navigation routes.
"""
import tkinter as tk
from typing import Callable, Dict
from pathlib import Path

from app.ui.theme import ThemeManager


class NavigationSidebar(tk.Frame):
    """Sidebar navigation panel with branding and route selection."""

    ROUTES = [
        ("dashboard", "Dashboard"),
        ("network", "Network"),
        ("system", "System"),
        ("incidents", "Incidents"),
        ("history", "History"),
        ("what_changed", "What Changed"),
        ("diagnostics", "Diagnostics"),
        ("gaming", "Gaming Mode"),
        ("optimization", "Optimization"),
        ("ask_veyra", "Ask Veyra"),
        ("settings", "Settings"),
    ]


    def __init__(
        self,
        parent,
        theme_manager: ThemeManager,
        on_navigate: Callable[[str], None],
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.on_navigate = on_navigate
        self.active_route = "dashboard"
        self.buttons: Dict[str, tk.Button] = {}

        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.secondary, width=220, highlightbackground=palette.borders, highlightthickness=1)
        self.pack_propagate(False)

        # 1. Branding Header
        self.brand_frame = tk.Frame(self, bg=palette.secondary, pady=20, padx=16)
        self.brand_frame.pack(fill=tk.X)

        self.logo_label = tk.Label(
            self.brand_frame,
            text="VEYRA",
            font=("Segoe UI", 18, "bold"),
            fg=palette.accent,
            bg=palette.secondary
        )
        self.logo_label.pack(anchor=tk.W)

        self.tagline = tk.Label(
            self.brand_frame,
            text="PC OBSERVABILITY",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.secondary
        )
        self.tagline.pack(anchor=tk.W, pady=(2, 0))

        # 2. Navigation Buttons
        self.nav_items_frame = tk.Frame(self, bg=palette.secondary, padx=8)
        self.nav_items_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        for route_id, label in self.ROUTES:
            btn = tk.Button(
                self.nav_items_frame,
                text=f"  {label}",
                font=self.theme_manager.font_body(),
                anchor=tk.W,
                relief=tk.FLAT,
                bd=0,
                padx=12,
                pady=8,
                command=lambda r=route_id: self._handle_click(r)
            )
            btn.pack(fill=tk.X, pady=2)
            self.buttons[route_id] = btn

        # 3. Footer / Version Info
        self.footer_frame = tk.Frame(self, bg=palette.secondary, padx=16, pady=16)
        self.footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.mode_lbl = tk.Label(
            self.footer_frame,
            text="NORMAL MODE",
            font=self.theme_manager.font_caption(),
            fg=palette.accent,
            bg=palette.secondary
        )
        self.mode_lbl.pack(anchor=tk.W)

        self.ver_lbl = tk.Label(
            self.footer_frame,
            text="VEYRA | Local",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.secondary
        )

        self.ver_lbl.pack(anchor=tk.W, pady=(2, 0))

        self.theme_manager.register_listener(self.apply_theme)
        self._update_button_styles()

    def _handle_click(self, route_id: str):
        self.set_active_route(route_id)
        self.on_navigate(route_id)

    def set_active_route(self, route_id: str):
        self.active_route = route_id
        self._update_button_styles()

    def _update_button_styles(self):
        palette = self.theme_manager.get_palette()
        for route_id, btn in self.buttons.items():
            if route_id == self.active_route:
                btn.configure(
                    bg=palette.cards,
                    fg=palette.accent,
                    activebackground=palette.cards,
                    activeforeground=palette.accent
                )
            else:
                btn.configure(
                    bg=palette.secondary,
                    fg=palette.text_secondary,
                    activebackground=palette.cards,
                    activeforeground=palette.text_primary
                )

    def apply_theme(self):
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.secondary, highlightbackground=palette.borders)
        self.brand_frame.configure(bg=palette.secondary)
        self.logo_label.configure(fg=palette.accent, bg=palette.secondary)
        self.tagline.configure(fg=palette.text_secondary, bg=palette.secondary)
        self.nav_items_frame.configure(bg=palette.secondary)
        self.footer_frame.configure(bg=palette.secondary)
        self.mode_lbl.configure(text=f"{self.theme_manager.current_mode} MODE", fg=palette.accent, bg=palette.secondary)
        self.ver_lbl.configure(fg=palette.text_secondary, bg=palette.secondary)
        self._update_button_styles()
