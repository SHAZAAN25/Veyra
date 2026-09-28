"""
VEYRA What Changed? Historical Comparison Screen.
Provides automated differential analysis across time windows (Current vs Yesterday,
Current vs Baseline) and displays persistent configuration change events.
"""
import tkinter as tk
from typing import Optional, List, Dict, Any

from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager
from app.ui.components.status_badge import StatusBadge
from storage.engine import StorageEngine


class WhatChangedScreen(tk.Frame):
    """Historical comparative analysis and change attribution screen."""

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

        # 1. Header Banner
        self.header_frame = tk.Frame(self.container, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=12)
        self.header_frame.pack(fill=tk.X, pady=(0, 16))

        h_left = tk.Frame(self.header_frame, bg=palette.cards)
        h_left.pack(side=tk.LEFT)

        tk.Label(
            h_left,
            text="HISTORICAL COMPARISON & ROOT CAUSE ATTRIBUTION",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.title_lbl = tk.Label(
            h_left,
            text="What Changed on this PC?",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.title_lbl.pack(anchor=tk.W, pady=(2, 0))

        # 2. Split Comparison Panels:
        # Left: Telemetry Shift (Baseline vs Current)
        # Right: Detected Configuration & Network Changes
        self.split_frame = tk.Frame(self.container, bg=palette.bg)
        self.split_frame.pack(fill=tk.BOTH, expand=True)
        self.split_frame.columnconfigure(0, weight=1)
        self.split_frame.columnconfigure(1, weight=1)

        # Left Panel: Metric Deviations
        self.metric_panel = tk.Frame(self.split_frame, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=16)
        self.metric_panel.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        tk.Label(
            self.metric_panel,
            text="STATISTICAL BASELINE DEVIATIONS",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 8))

        self.baseline_info_lbl = tk.Label(
            self.metric_panel,
            text="Comparing live state against personal established baseline...",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards,
            wraplength=350,
            justify=tk.LEFT
        )
        self.baseline_info_lbl.pack(anchor=tk.W, pady=(0, 12))

        self.metric_rows_frame = tk.Frame(self.metric_panel, bg=palette.cards)
        self.metric_rows_frame.pack(fill=tk.BOTH, expand=True)

        # Right Panel: Configuration & Environment Changes
        self.change_panel = tk.Frame(self.split_frame, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=16)
        self.change_panel.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        tk.Label(
            self.change_panel,
            text="CONFIGURATION & ENVIRONMENT CHANGES",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 8))

        self.changes_scroll_canvas = tk.Canvas(self.change_panel, bg=palette.cards, highlightthickness=0)
        self.changes_scrollbar = tk.Scrollbar(self.change_panel, orient=tk.VERTICAL, command=self.changes_scroll_canvas.yview)
        self.changes_inner = tk.Frame(self.changes_scroll_canvas, bg=palette.cards)

        self.changes_inner.bind("<Configure>", lambda e: self.changes_scroll_canvas.configure(scrollregion=self.changes_scroll_canvas.bbox("all")))
        self.canvas_window = self.changes_scroll_canvas.create_window((0, 0), window=self.changes_inner, anchor="nw")
        self.changes_scroll_canvas.bind("<Configure>", lambda e: self.changes_scroll_canvas.itemconfig(self.canvas_window, width=e.width))

        self.changes_scroll_canvas.configure(yscrollcommand=self.changes_scrollbar.set)
        self.changes_scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.changes_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.theme_manager.register_listener(self.apply_theme)

    def _render_diff_row(self, parent: tk.Frame, metric_name: str, baseline_str: str, current_str: str, diff_str: str, is_significant: bool):
        palette = self.theme_manager.get_palette()
        row = tk.Frame(parent, bg=palette.cards_secondary, padx=10, pady=8, highlightbackground=palette.borders, highlightthickness=1)
        row.pack(fill=tk.X, pady=4)

        top_line = tk.Frame(row, bg=palette.cards_secondary)
        top_line.pack(fill=tk.X)

        tk.Label(top_line, text=metric_name, font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards_secondary).pack(side=tk.LEFT)
        diff_color = palette.warning if is_significant else palette.healthy
        tk.Label(top_line, text=diff_str, font=self.theme_manager.font_caption(), fg=diff_color, bg=palette.cards_secondary).pack(side=tk.RIGHT)

        val_line = tk.Frame(row, bg=palette.cards_secondary)
        val_line.pack(fill=tk.X, pady=(4, 0))

        tk.Label(val_line, text=f"Baseline: {baseline_str}", font=self.theme_manager.font_body(), fg=palette.text_secondary, bg=palette.cards_secondary).pack(side=tk.LEFT)
        tk.Label(val_line, text=f"Current: {current_str}", font=self.theme_manager.font_body(), fg=palette.text_primary, bg=palette.cards_secondary).pack(side=tk.RIGHT)

    def update_data(self):
        """Refreshes baseline deviations and timeline configuration changes."""
        palette = self.theme_manager.get_palette()

        # 1. Update metric comparisons from personal baseline
        for w in self.metric_rows_frame.winfo_children():
            w.destroy()

        try:
            baseline = self.storage.baselines.get_baseline("network_rtt_ms")
            obs = self.state_manager.latest_observation

            if baseline and baseline.quality.value in ("ESTABLISHED", "LOW_CONFIDENCE"):
                self.baseline_info_lbl.configure(
                    text=f"Baseline Quality: {baseline.quality.value} ({baseline.sample_count} samples). Evaluating statistical drift."
                )

                # Ping comparison
                if obs:
                    m = obs.get_metric("network_rtt_ms")
                    if m and m.is_valid and isinstance(m.value, (int, float)):
                        b_val = baseline.mean
                        c_val = float(m.value)
                        diff = c_val - b_val
                        diff_str = f"+{diff:.1f} ms" if diff > 0 else f"{diff:.1f} ms"
                        self._render_diff_row(self.metric_rows_frame, "NETWORK LATENCY (RTT)", f"{b_val:.1f} ms", f"{c_val:.1f} ms", diff_str, is_significant=abs(diff) > 15)

                    m_cpu = obs.get_metric("cpu_utilization_pct")
                    if m_cpu and m_cpu.is_valid and isinstance(m_cpu.value, (int, float)):
                        base_cpu = self.storage.baselines.get_baseline("cpu_utilization_pct")
                        if base_cpu:
                            b_val = base_cpu.mean
                            c_val = float(m_cpu.value)
                            diff = c_val - b_val
                            diff_str = f"+{diff:.1f}%" if diff > 0 else f"{diff:.1f}%"
                            self._render_diff_row(self.metric_rows_frame, "CPU LOAD", f"{b_val:.1f}%", f"{c_val:.1f}%", diff_str, is_significant=abs(diff) > 25)

                    m_ram = obs.get_metric("memory_utilization_pct")
                    if m_ram and m_ram.is_valid and isinstance(m_ram.value, (int, float)):
                        base_ram = self.storage.baselines.get_baseline("memory_utilization_pct")
                        if base_ram:
                            b_val = base_ram.mean
                            c_val = float(m_ram.value)
                            diff = c_val - b_val
                            diff_str = f"+{diff:.1f}%" if diff > 0 else f"{diff:.1f}%"
                            self._render_diff_row(self.metric_rows_frame, "RAM COMMIT", f"{b_val:.1f}%", f"{c_val:.1f}%", diff_str, is_significant=abs(diff) > 20)
            else:
                self.baseline_info_lbl.configure(text="Baseline is currently learning. Accumulating operational samples for statistical deviation analysis.")
                tk.Label(
                    self.metric_rows_frame,
                    text="Baseline Still Learning\n(Minimum 10 measurement intervals required for drift analysis)",
                    font=self.theme_manager.font_caption(),
                    fg=palette.text_secondary,
                    bg=palette.cards,
                    pady=20
                ).pack()
        except Exception as e:
            self.baseline_info_lbl.configure(text=f"Baseline query error: {e}")

        # 2. Update Timeline Configuration Changes
        for w in self.changes_inner.winfo_children():
            w.destroy()

        try:
            timeline_events = self.storage.timeline.query_timeline(limit=20)
            # Filter for configuration changes or network shifts
            config_events = [e.to_dict() for e in timeline_events if "CONFIG" in e.event_type or "CHANGE" in e.event_type]

            if not config_events:
                tk.Label(
                    self.changes_inner,
                    text="No environment or configuration alterations recorded.\nNetwork adapter, gateway, and system parameters remain stable.",
                    font=self.theme_manager.font_body(),
                    fg=palette.text_secondary,
                    bg=palette.cards,
                    pady=30
                ).pack()
            else:
                for ev in config_events:
                    card = tk.Frame(self.changes_inner, bg=palette.cards_secondary, padx=10, pady=8, highlightbackground=palette.borders, highlightthickness=1)
                    card.pack(fill=tk.X, pady=4)

                    tk.Label(card, text=ev.get("title", "Configuration Shift"), font=self.theme_manager.font_body(), fg=palette.text_primary, bg=palette.cards_secondary).pack(anchor=tk.W)
                    tk.Label(card, text=ev.get("description", ""), font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards_secondary).pack(anchor=tk.W, pady=(2, 0))
        except Exception:
            pass

    def apply_theme(self):
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)
        self.container.configure(bg=palette.bg)
        self.header_frame.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.split_frame.configure(bg=palette.bg)
        self.metric_panel.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.change_panel.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.changes_scroll_canvas.configure(bg=palette.cards)
        self.changes_inner.configure(bg=palette.cards)
