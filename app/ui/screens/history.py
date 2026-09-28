"""
VEYRA Historical Analytics Screen.
Provides multi-metric historical time-range exploration (1h, 24h, 7d, 30d)
using Stage 3 SQLite summaries and high-resolution chart rendering.
"""
import tkinter as tk
from typing import Optional, List, Tuple

from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager
from app.ui.components.status_badge import StatusBadge
from app.ui.components.chart import HistoricalCanvasChart
from storage.engine import StorageEngine


class HistoryScreen(tk.Frame):
    """Historical time-series analysis and metrics screen."""

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

        # 1. Header & Controls
        self.header_frame = tk.Frame(self.container, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=12)
        self.header_frame.pack(fill=tk.X, pady=(0, 16))

        h_left = tk.Frame(self.header_frame, bg=palette.cards)
        h_left.pack(side=tk.LEFT)

        tk.Label(
            h_left,
            text="HISTORICAL PC & NETWORK MEMORY",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.title_lbl = tk.Label(
            h_left,
            text="Stage 3 Long-Term Historical Queries",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.title_lbl.pack(anchor=tk.W, pady=(2, 0))

        # Controls Right: Metric selection and Range selection
        h_right = tk.Frame(self.header_frame, bg=palette.cards)
        h_right.pack(side=tk.RIGHT)

        # Metric Selector
        tk.Label(h_right, text="METRIC:", font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards).pack(side=tk.LEFT, padx=(0, 4))
        self.metric_var = tk.StringVar(value="ping_ms_avg")
        self.metric_menu = tk.OptionMenu(
            h_right,
            self.metric_var,
            "ping_ms_avg",
            "loss_pct",
            "cpu_avg",
            "ram_avg",
            "disk_io_avg",
            command=lambda _: self.update_data()
        )
        self.metric_menu.configure(
            bg=palette.cards_secondary,
            fg=palette.text_primary,
            font=self.theme_manager.font_caption(),
            highlightthickness=0
        )
        self.metric_menu.pack(side=tk.LEFT, padx=(0, 16))

        # Limit / Range Selector
        tk.Label(h_right, text="INTERVALS:", font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards).pack(side=tk.LEFT, padx=(0, 4))
        self.limit_var = tk.StringVar(value="60")
        for lim in ["20", "60", "120", "288"]:
            rb = tk.Radiobutton(
                h_right,
                text=lim,
                variable=self.limit_var,
                value=lim,
                command=self.update_data,
                bg=palette.cards,
                fg=palette.text_primary,
                selectcolor=palette.cards_secondary,
                activebackground=palette.cards,
                activeforeground=palette.accent,
                font=self.theme_manager.font_caption()
            )
            rb.pack(side=tk.LEFT, padx=2)

        # 2. Historical Chart Area
        self.chart_panel = tk.Frame(self.container, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=16)
        self.chart_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

        self.chart_title = tk.Label(
            self.chart_panel,
            text="HISTORICAL TREND ANALYSIS",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.chart_title.pack(anchor=tk.W, pady=(0, 8))

        self.chart = HistoricalCanvasChart(self.chart_panel, theme_manager=self.theme_manager, height=260)
        self.chart.pack(fill=tk.BOTH, expand=True)

        self.chart_footer = tk.Label(
            self.chart_panel,
            text="Source: SQLite summaries | Missing intervals rendered as gaps | No artificial smoothing",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        )
        self.chart_footer.pack(anchor=tk.E, pady=(8, 0))

        # 3. Summary Statistics Table (Min, Max, Avg, P95)
        self.stats_panel = tk.Frame(self.container, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=12)
        self.stats_panel.pack(fill=tk.X)

        for c in range(4):
            self.stats_panel.columnconfigure(c, weight=1)

        self.stat_min = self._create_stat_cell(self.stats_panel, 0, "MINIMUM")
        self.stat_avg = self._create_stat_cell(self.stats_panel, 1, "AVERAGE")
        self.stat_max = self._create_stat_cell(self.stats_panel, 2, "PEAK / MAX")
        self.stat_count = self._create_stat_cell(self.stats_panel, 3, "INTERVAL COUNT")

        self.theme_manager.register_listener(self.apply_theme)

    def _create_stat_cell(self, parent: tk.Frame, col: int, label: str) -> tk.Label:
        palette = self.theme_manager.get_palette()
        frame = tk.Frame(parent, bg=palette.cards)
        frame.grid(row=0, column=col, sticky="nsew", padx=8)

        tk.Label(frame, text=label, font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards).pack(anchor=tk.W)
        val_lbl = tk.Label(frame, text="—", font=self.theme_manager.font_section(), fg=palette.accent, bg=palette.cards)
        val_lbl.pack(anchor=tk.W, pady=(2, 0))
        return val_lbl

    def update_data(self):
        """Queries historical summaries and plots the selected metric."""
        metric_key = self.metric_var.get()
        try:
            limit = int(self.limit_var.get())
        except ValueError:
            limit = 60

        units = {
            "ping_ms_avg": "ms",
            "loss_pct": "%",
            "cpu_avg": "%",
            "ram_avg": "%",
            "disk_io_avg": "%"
        }
        unit = units.get(metric_key, "")

        self.chart_title.configure(text=f"HISTORICAL TREND: {metric_key.upper()} ({unit})")

        try:
            summaries = self.storage.sqlite.query_measurement_summaries(
                metric_name=metric_key,
                resolution_seconds=60,
                limit=limit
            )
            if not summaries:
                self.chart.render_data([], unit=unit)
                self.stat_min.configure(text="—")
                self.stat_avg.configure(text="—")
                self.stat_max.configure(text="—")
                self.stat_count.configure(text="0")
                return

            points: List[Tuple[float, Optional[float]]] = []
            vals: List[float] = []

            for s in summaries:
                ts = 0.0
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(s.bucket_start_utc.replace("Z", "+00:00"))
                    ts = dt.timestamp()
                except Exception:
                    pass
                val = s.mean_value
                points.append((ts, val))
                if val is not None:
                    vals.append(float(val))

            self.chart.render_data(points, unit=unit)

            if vals:
                min_v = min(vals)
                max_v = max(vals)
                avg_v = sum(vals) / len(vals)
                self.stat_min.configure(text=f"{min_v:.1f} {unit}")
                self.stat_avg.configure(text=f"{avg_v:.1f} {unit}")
                self.stat_max.configure(text=f"{max_v:.1f} {unit}")
                self.stat_count.configure(text=f"{len(vals)} / {len(summaries)}")
            else:
                self.stat_min.configure(text="N/A")
                self.stat_avg.configure(text="N/A")
                self.stat_max.configure(text="N/A")
                self.stat_count.configure(text=f"0 / {len(summaries)}")

        except Exception as e:
            self.chart.render_data([], unit=unit)

    def apply_theme(self):
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)
        self.container.configure(bg=palette.bg)
        self.header_frame.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.chart_panel.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.stats_panel.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.chart_title.configure(fg=palette.text_primary, bg=palette.cards)
        self.chart_footer.configure(fg=palette.text_secondary, bg=palette.cards)
