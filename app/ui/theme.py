"""
VEYRA UI Theme Engine & Design System Tokens.
Strictly implements UI_DESIGN_SYSTEM.md palettes, typography, and dynamic mode switching.
Supports Dark, Light, and System themes, as well as Normal (Cyan) and Gaming (Crimson) modes.
"""
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
import os
from pathlib import Path


@dataclass(frozen=True)
class Palette:
    """Color tokens for a specific theme and mode combination."""
    bg: str
    secondary: str
    cards: str
    borders: str
    text_primary: str
    text_secondary: str
    accent: str
    healthy: str
    warning: str
    high: str
    critical: str
    hover: str
    badge_bg: str

    @property
    def cards_secondary(self) -> str:
        return self.secondary

    @property
    def bg_secondary(self) -> str:
        return self.secondary


# Normal Mode Dark Theme (Default)
PALETTE_NORMAL_DARK = Palette(
    bg="#0B0D10",
    secondary="#12161B",
    cards="#181D23",
    borders="#2A3139",
    text_primary="#F1F3F5",
    text_secondary="#9AA3AD",
    accent="#27D3E6",  # Locked Cyan
    healthy="#35C99A",
    warning="#E8B84A",
    high="#E8794F",
    critical="#E05252",
    hover="#222933",
    badge_bg="#1C232B"
)

# Normal Mode Light Theme
PALETTE_NORMAL_LIGHT = Palette(
    bg="#F8F9FA",
    secondary="#EEF1F4",
    cards="#FFFFFF",
    borders="#D1D7DC",
    text_primary="#1A202C",
    text_secondary="#5A6578",
    accent="#0099AA",  # Deep readable Cyan
    healthy="#249C75",
    warning="#C98D10",
    high="#C85B2E",
    critical="#C53030",
    hover="#E2E6EA",
    badge_bg="#E8ECF0"
)

# Gaming Mode Crimson Theme
PALETTE_GAMING = Palette(
    bg="#080A0C",
    secondary="#101418",
    cards="#14191E",
    borders="#32252A",
    text_primary="#F5F5F5",
    text_secondary="#A39699",
    accent="#FF3045",  # Locked Crimson
    healthy="#32D7A0",
    warning="#FFB03A",
    high="#FF6B35",
    critical="#FF4655",  # Hot accent
    hover="#20181C",
    badge_bg="#26161B"
)


class ThemeManager:
    """Manages active color palette, typography, reduced motion, and branding asset paths."""

    def __init__(self, mode: str = "normal", theme: str = "dark", reduced_motion: bool = False):
        self._mode = mode.lower()
        self._theme = theme.lower()
        self._reduced_motion = reduced_motion
        self._listeners: List[Callable[[], None]] = []

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, val: str) -> None:
        val = val.lower()
        if val in ("normal", "gaming") and val != self._mode:
            self._mode = val
            self._notify()

    @property
    def theme(self) -> str:
        return self._theme

    @theme.setter
    def theme(self, val: str) -> None:
        val = val.lower()
        if val in ("dark", "light", "system") and val != self._theme:
            self._theme = val
            self._notify()

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    @reduced_motion.setter
    def reduced_motion(self, val: bool) -> None:
        if self._reduced_motion != val:
            self._reduced_motion = val
            self._notify()

    @property
    def current_mode(self) -> str:
        return self._mode.upper()

    @property
    def theme_mode(self) -> str:
        return self._theme

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def set_theme(self, theme: str) -> None:
        self.theme = theme

    def set_reduced_motion(self, val: bool) -> None:
        self.reduced_motion = val

    def register_listener(self, listener: Callable[[], None]) -> None:
        """Alias for add_listener."""
        self.add_listener(listener)

    def add_listener(self, listener: Callable[[], None]) -> None:
        """Subscribes a view to theme/mode changes for instant in-memory redraws."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                pass

    def get_palette(self) -> Palette:
        """Returns the active color palette based on mode and theme."""
        if self._mode == "gaming":
            return PALETTE_GAMING
        if self._theme == "light":
            return PALETTE_NORMAL_LIGHT
        return PALETTE_NORMAL_DARK

    def get_branding_logo_path(self, size: int = 128) -> str:
        """
        Returns the absolute path to the official locked logo asset.
        NEVER dynamically recolors or generates logos.
        """
        base_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "branding"
        sub = "gaming" if self._mode == "gaming" else "normal"
        prefix = "VEYRA_Gaming_Logo" if self._mode == "gaming" else "VEYRA_Normal_Logo"
        
        # Check standard sizes: 128x128, 256x256, 512x512, EXACT
        target_file = base_dir / sub / f"{prefix}_{size}x{size}.png"
        if not target_file.exists():
            target_file = base_dir / sub / f"{prefix}_EXACT.png"
        return str(target_file)

    def get_branding_icon_path(self) -> str:
        """Returns the official .ico path for window icons."""
        base_dir = Path(__file__).resolve().parent.parent.parent / "assets" / "branding"
        sub = "gaming" if self._mode == "gaming" else "normal"
        icon_name = "VEYRA_Gaming_Icon.ico" if self._mode == "gaming" else "VEYRA_Normal_Icon.ico"
        return str(base_dir / sub / icon_name)

    # Standard font definitions for Tkinter widgets
    @staticmethod
    def font_title() -> tuple:
        return ("Segoe UI", 16, "bold")

    @staticmethod
    def font_heading() -> tuple:
        return ("Segoe UI", 12, "bold")

    @staticmethod
    def font_section() -> tuple:
        return ("Segoe UI", 11, "bold")

    @staticmethod
    def font_subheading() -> tuple:
        return ("Segoe UI", 10, "bold")

    @staticmethod
    def font_body() -> tuple:
        return ("Segoe UI", 9)

    @staticmethod
    def font_caption() -> tuple:
        return ("Segoe UI", 8)

    @staticmethod
    def font_mono() -> tuple:
        return ("Consolas", 9)

    @staticmethod
    def font_mono_large() -> tuple:
        return ("Consolas", 14, "bold")
