"""
VEYRA Settings & Storage Management Screen.
Allows live theme switching (Dark / Light / System), operational mode switching (Normal Cyan / Gaming Crimson),
motion reduction, telemetry collector status, and SQLite database storage controls with confirmation dialogs.
"""
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager
from app.ui.components.dialogs import ConfirmationDialog
from storage.engine import StorageEngine


class SettingsScreen(tk.Frame):
    """Configuration, theme preferences, and storage management screen."""

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

        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)

        self.container = tk.Frame(self, bg=palette.bg)
        self.container.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # 1. Header
        self.header_frame = tk.Frame(self.container, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=12)
        self.header_frame.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            self.header_frame,
            text="APPLICATION PREFERENCES & STORAGE REPOSITORY",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.title_lbl = tk.Label(
            self.header_frame,
            text="Settings & System Governance",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.title_lbl.pack(anchor=tk.W, pady=(2, 0))

        # 2. Main content panels (Grid 2 columns)
        self.panels_frame = tk.Frame(self.container, bg=palette.bg)
        self.panels_frame.pack(fill=tk.BOTH, expand=True)
        self.panels_frame.columnconfigure(0, weight=1)
        self.panels_frame.columnconfigure(1, weight=1)

        # Left Column: Appearance & Mode
        self.left_panel = tk.Frame(self.panels_frame, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=16)
        self.left_panel.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        tk.Label(
            self.left_panel,
            text="APPEARANCE & VISUAL IDENTITY",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 12))

        # Theme selection (Dark / Light / System)
        tk.Label(self.left_panel, text="Theme Mode:", font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards).pack(anchor=tk.W)
        theme_row = tk.Frame(self.left_panel, bg=palette.cards)
        theme_row.pack(fill=tk.X, pady=(4, 12))

        self.theme_var = tk.StringVar(value=self.theme_manager.theme_mode)
        for tm in ["dark", "light", "system"]:
            rb = tk.Radiobutton(
                theme_row,
                text=tm.capitalize(),
                variable=self.theme_var,
                value=tm,
                command=self._on_theme_changed,
                bg=palette.cards,
                fg=palette.text_primary,
                selectcolor=palette.cards_secondary,
                activebackground=palette.cards,
                activeforeground=palette.accent,
                font=self.theme_manager.font_body()
            )
            rb.pack(side=tk.LEFT, padx=6)

        # Operational Mode (Normal Cyan / Gaming Crimson)
        tk.Label(self.left_panel, text="Branding & Operational Mode:", font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards).pack(anchor=tk.W)
        mode_row = tk.Frame(self.left_panel, bg=palette.cards)
        mode_row.pack(fill=tk.X, pady=(4, 12))

        self.mode_var = tk.StringVar(value=self.theme_manager.current_mode)
        for m in ["NORMAL", "GAMING"]:
            rb = tk.Radiobutton(
                mode_row,
                text=f"{m} Mode",
                variable=self.mode_var,
                value=m,
                command=self._on_mode_changed,
                bg=palette.cards,
                fg=palette.text_primary,
                selectcolor=palette.cards_secondary,
                activebackground=palette.cards,
                activeforeground=palette.accent,
                font=self.theme_manager.font_body()
            )
            rb.pack(side=tk.LEFT, padx=6)

        # Reduced Motion Toggle
        self.motion_var = tk.BooleanVar(value=self.theme_manager.reduced_motion)
        cb_motion = tk.Checkbutton(
            self.left_panel,
            text="Enable Reduced Motion (Disable transitions & animations)",
            variable=self.motion_var,
            command=self._on_motion_changed,
            bg=palette.cards,
            fg=palette.text_primary,
            selectcolor=palette.cards_secondary,
            activebackground=palette.cards,
            activeforeground=palette.accent,
            font=self.theme_manager.font_body()
        )
        cb_motion.pack(anchor=tk.W, pady=(8, 16))

        # Localhost API notice
        api_box = tk.Frame(self.left_panel, bg=palette.cards_secondary, padx=12, pady=10, highlightbackground=palette.borders, highlightthickness=1)
        api_box.pack(fill=tk.X, pady=(8, 0))
        tk.Label(api_box, text="SECURITY & DATA CONTRACT", font=self.theme_manager.font_caption(), fg=palette.accent, bg=palette.cards_secondary).pack(anchor=tk.W)
        tk.Label(
            api_box,
            text="Local-first architecture strictly bound to 127.0.0.1.\nZero cloud telemetry, zero external API keys required.",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards_secondary,
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(4, 0))

        # Right Column: Storage & Database Governance
        self.right_panel = tk.Frame(self.panels_frame, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=16)
        self.right_panel.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        tk.Label(
            self.right_panel,
            text="STORAGE & RETENTION GOVERNANCE",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 12))

        # Storage health rows
        self.storage_rows = tk.Frame(self.right_panel, bg=palette.cards)
        self.storage_rows.pack(fill=tk.X, pady=(0, 16))

        self.lbl_db_path = self._create_row(self.storage_rows, "Database Path:", str(self.storage.sqlite.db_path))
        self.lbl_db_size = self._create_row(self.storage_rows, "Database Size:", "Calculating...")
        self.lbl_incidents_cnt = self._create_row(self.storage_rows, "Persisted Incidents:", "Querying...")
        self.lbl_timeline_cnt = self._create_row(self.storage_rows, "Timeline Events:", "Querying...")
        self.lbl_summaries_cnt = self._create_row(self.storage_rows, "Historical Summaries:", "Querying...")

        # Storage Management Actions
        tk.Label(self.right_panel, text="Repository Operations:", font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards).pack(anchor=tk.W, pady=(8, 4))

        actions_frame = tk.Frame(self.right_panel, bg=palette.cards)
        actions_frame.pack(fill=tk.X, pady=4)

        # Compaction button
        self.btn_compact = tk.Button(
            actions_frame,
            text="Compact Database (VACUUM)",
            command=self._action_compact,
            bg=palette.cards_secondary,
            fg=palette.text_primary,
            font=self.theme_manager.font_caption(),
            padx=10,
            pady=4,
            relief=tk.FLAT,
            highlightbackground=palette.borders,
            highlightthickness=1
        )
        self.btn_compact.pack(side=tk.LEFT, padx=(0, 8))

        # Clear history button (Destructive with modal confirmation)
        self.btn_clear = tk.Button(
            actions_frame,
            text="Reset Storage (Purge)",
            command=self._action_clear_storage,
            bg=palette.cards_secondary,
            fg=palette.critical,
            font=self.theme_manager.font_caption(),
            padx=10,
            pady=4,
            relief=tk.FLAT,
            highlightbackground=palette.borders,
            highlightthickness=1
        )
        self.btn_clear.pack(side=tk.LEFT)

        self.theme_manager.register_listener(self.apply_theme)

    def _create_row(self, parent: tk.Frame, label_text: str, val_text: str) -> tk.Label:
        palette = self.theme_manager.get_palette()
        row = tk.Frame(parent, bg=palette.cards)
        row.pack(fill=tk.X, pady=3)

        tk.Label(
            row,
            text=label_text,
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards,
            width=22,
            anchor=tk.W
        ).pack(side=tk.LEFT)

        val_lbl = tk.Label(
            row,
            text=val_text,
            font=self.theme_manager.font_body(),
            fg=palette.text_primary,
            bg=palette.cards,
            anchor=tk.W
        )
        val_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return val_lbl

    def _on_theme_changed(self):
        new_theme = self.theme_var.get()
        self.theme_manager.set_theme(new_theme)

    def _on_mode_changed(self):
        new_mode = self.mode_var.get()
        self.theme_manager.set_mode(new_mode)

    def _on_motion_changed(self):
        self.theme_manager.set_reduced_motion(self.motion_var.get())

    def _action_compact(self):
        try:
            self.storage.run_compaction()
            messagebox.showinfo("Storage Compaction", "Database compaction and rollups completed successfully.")
            self.update_data()
        except Exception as e:
            messagebox.showerror("Compaction Failed", f"Could not compact database: {e}")

    def _action_clear_storage(self):
        def _confirmed():
            try:
                # Reset database by closing and deleting sqlite file
                db_path = Path(self.storage.sqlite.db_path)
                self.storage.sqlite.close()
                if db_path.exists():
                    db_path.unlink()
                # Re-initialize sqlite connection
                self.storage.sqlite._init_db()
                messagebox.showinfo("Storage Purged", "All historical storage, incidents, and baselines have been reset.")
                self.update_data()
            except Exception as e:
                messagebox.showerror("Reset Failed", f"Could not reset storage: {e}")

        ConfirmationDialog(
            self,
            theme_manager=self.theme_manager,
            title="CONFIRM STORAGE PURGE",
            message="Are you sure you want to permanently delete all historical summaries, incidents, and baseline models?\n\nThis action cannot be undone.",
            on_confirm=_confirmed
        )

    def update_data(self):
        """Calculates SQLite database stats and record counts."""
        try:
            db_file = Path(self.storage.sqlite.db_path)
            if db_file.exists():
                size_kb = db_file.stat().st_size / 1024.0
                if size_kb > 1024.0:
                    self.lbl_db_size.configure(text=f"{size_kb / 1024.0:.2f} MB")
                else:
                    self.lbl_db_size.configure(text=f"{size_kb:.1f} KB")
            else:
                self.lbl_db_size.configure(text="0 KB (In-Memory)")

            incidents = self.storage.sqlite.query_incident_records(limit=1000)
            self.lbl_incidents_cnt.configure(text=str(len(incidents)))

            timeline = self.storage.timeline.query_timeline(limit=1000)
            self.lbl_timeline_cnt.configure(text=str(len(timeline)))

            summaries = self.storage.sqlite.query_measurement_summaries(limit=1000)
            self.lbl_summaries_cnt.configure(text=str(len(summaries)))
        except Exception as e:
            self.lbl_db_size.configure(text="Error querying stats")

    def apply_theme(self):
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)
        self.container.configure(bg=palette.bg)
        self.header_frame.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.panels_frame.configure(bg=palette.bg)
        self.left_panel.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.right_panel.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.btn_compact.configure(bg=palette.cards_secondary, fg=palette.text_primary, highlightbackground=palette.borders)
        self.btn_clear.configure(bg=palette.cards_secondary, highlightbackground=palette.borders)
