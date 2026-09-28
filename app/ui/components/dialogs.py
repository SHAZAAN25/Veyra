"""
VEYRA Modal Confirmation Dialog.
Provides explicit, unambiguous confirmation prompts for destructive operations.
"""
import tkinter as tk
from typing import Callable

from app.ui.theme import ThemeManager


class ConfirmationDialog(tk.Toplevel):
    """Modal confirmation dialog for destructive storage or baseline operations."""

    def __init__(
        self,
        parent,
        theme_manager: ThemeManager,
        title: str,
        message: str,
        confirm_text: str = "CONFIRM",
        on_confirm: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.on_confirm = on_confirm

        palette = self.theme_manager.get_palette()
        self.title(title)
        self.configure(bg=palette.bg)
        self.resizable(False, False)
        self.geometry("420x200")
        self.transient(parent)
        self.grab_set()

        # Warning Header
        hdr = tk.Label(
            self,
            text=title.upper(),
            font=self.theme_manager.font_heading(),
            fg=palette.critical,
            bg=palette.bg,
            pady=12
        )
        hdr.pack(fill=tk.X)

        # Message
        msg = tk.Label(
            self,
            text=message,
            font=self.theme_manager.font_body(),
            fg=palette.text_primary,
            bg=palette.bg,
            wraplength=380,
            justify=tk.CENTER,
            padx=16
        )
        msg.pack(fill=tk.BOTH, expand=True)

        # Button row
        btn_frame = tk.Frame(self, bg=palette.bg, pady=12)
        btn_frame.pack(fill=tk.X)

        btn_cancel = tk.Button(
            btn_frame,
            text="Cancel",
            font=self.theme_manager.font_subheading(),
            bg=palette.secondary,
            fg=palette.text_secondary,
            command=self.destroy,
            padx=16,
            pady=4,
            relief=tk.FLAT
        )
        btn_cancel.pack(side=tk.RIGHT, padx=(0, 20))

        btn_action = tk.Button(
            btn_frame,
            text=confirm_text,
            font=self.theme_manager.font_subheading(),
            bg=palette.critical,
            fg="#FFFFFF",
            command=self._handle_confirm,
            padx=16,
            pady=4,
            relief=tk.FLAT
        )
        btn_action.pack(side=tk.RIGHT, padx=10)

    def _handle_confirm(self) -> None:
        self.destroy()
        if self.on_confirm:
            self.on_confirm()
