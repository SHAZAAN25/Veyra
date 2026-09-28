"""
VEYRA System Health & Hardware Bottleneck Screen.
Displays real-time and historical CPU, Memory, Disk, and GPU metrics,
with personal PC baseline deviations and hardware bottleneck context.
"""
import tkinter as tk
from typing import Optional

from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager
from app.ui.components.status_badge import StatusBadge
from app.ui.components.metric_card import MetricCard
from app.ui.components.chart import HistoricalCanvasChart
from storage.engine import StorageEngine


class SystemScreen(tk.Frame):
    """System health and hardware resource screen."""

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

        # Main scrollable or structured container
        self.container = tk.Frame(self, bg=palette.bg)
        self.container.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # 1. Header Banner
        self.banner = tk.Frame(self.container, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=12)
        self.banner.pack(fill=tk.X, pady=(0, 16))

        banner_left = tk.Frame(self.banner, bg=palette.cards)
        banner_left.pack(side=tk.LEFT)

        self.title_lbl = tk.Label(
            banner_left,
            text="HARDWARE & SUBSYSTEM TELEMETRY",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        )
        self.title_lbl.pack(anchor=tk.W)

        self.health_badge = StatusBadge(banner_left, theme_manager=self.theme_manager, status="HEALTHY")
        self.health_badge.pack(anchor=tk.W, pady=(4, 0))

        banner_right = tk.Frame(self.banner, bg=palette.cards)
        banner_right.pack(side=tk.RIGHT)

        self.freshness_badge = StatusBadge(banner_right, theme_manager=self.theme_manager, status="UNAVAILABLE")
        self.freshness_badge.pack(anchor=tk.E)

        # 2. Key Metrics Grid
        self.grid_frame = tk.Frame(self.container, bg=palette.bg)
        self.grid_frame.pack(fill=tk.X, pady=(0, 16))
        for col in range(4):
            self.grid_frame.columnconfigure(col, weight=1, uniform="sys_card")

        self.card_cpu = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="CPU UTILIZATION", unit="%")
        self.card_cpu.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.card_ram = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="RAM USAGE", unit="%")
        self.card_ram.grid(row=0, column=1, padx=4, sticky="ew")

        self.card_disk = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="DISK ACTIVITY", unit="%")
        self.card_disk.grid(row=0, column=2, padx=4, sticky="ew")

        self.card_gpu = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="GPU UTILIZATION", unit="%")
        self.card_gpu.grid(row=0, column=3, padx=(8, 0), sticky="ew")

        # 3. Two Columns: Details Panel (Left) & Historical Load Chart (Right)
        self.lower_frame = tk.Frame(self.container, bg=palette.bg)
        self.lower_frame.pack(fill=tk.BOTH, expand=True)
        self.lower_frame.columnconfigure(0, weight=1)
        self.lower_frame.columnconfigure(1, weight=1)

        # Left: Hardware & Bottleneck Analysis
        self.details_card = tk.Frame(self.lower_frame, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=16)
        self.details_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        tk.Label(
            self.details_card,
            text="HARDWARE BOTTLENECK ANALYSIS",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 12))

        self.bottleneck_desc = tk.Label(
            self.details_card,
            text="Evaluating CPU, memory pressure, disk queues, and GPU subsystem...",
            font=self.theme_manager.font_body(),
            fg=palette.text_secondary,
            bg=palette.cards,
            wraplength=350,
            justify=tk.LEFT
        )
        self.bottleneck_desc.pack(anchor=tk.W, pady=(0, 16))

        # Hardware specs / details
        self.details_rows = tk.Frame(self.details_card, bg=palette.cards)
        self.details_rows.pack(fill=tk.X)

        self.lbl_cpu_detail = self._create_row(self.details_rows, "CPU Model / Cores:", "Querying...")
        self.lbl_ram_detail = self._create_row(self.details_rows, "Physical Memory:", "Querying...")
        self.lbl_disk_detail = self._create_row(self.details_rows, "Primary Disk:", "Querying...")
        self.lbl_gpu_detail = self._create_row(self.details_rows, "Graphics Subsystem:", "Querying...")

        # Right: Historical System Chart
        self.chart_card = tk.Frame(self.lower_frame, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=16)
        self.chart_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        tk.Label(
            self.chart_card,
            text="HISTORICAL CPU LOAD (LAST 24 HOURS)",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 12))

        self.chart = HistoricalCanvasChart(self.chart_card, theme_manager=self.theme_manager, height=180)
        self.chart.pack(fill=tk.BOTH, expand=True)

        self.chart_meta = tk.Label(
            self.chart_card,
            text="Range: Last 24h | Storage: Stage 3 SQLite Summaries",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        )
        self.chart_meta.pack(anchor=tk.E, pady=(8, 0))

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
            width=20,
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

    def update_data(self):
        """Pulls latest system metrics and historical queries safely."""
        val = self.state_manager.get_metric_value
        st = self.state_manager.get_metric_state
        palette = self.theme_manager.get_palette()

        freshness = self.state_manager.freshness_state
        self.freshness_badge.update_status(freshness)

        cpu_val = val("cpu_utilization_pct")
        ram_val = val("memory_utilization_pct")
        disk_val = val("disk_utilization_pct")
        gpu_val = val("gpu_temperature_c")

        self.card_cpu.update_metric(cpu_val, freshness=st("cpu_utilization_pct"))
        self.card_ram.update_metric(ram_val, freshness=st("memory_utilization_pct"))
        self.card_disk.update_metric(disk_val, freshness=st("disk_utilization_pct"))
        self.card_gpu.update_metric(gpu_val, freshness=st("gpu_temperature_c"))

        self.lbl_cpu_detail.configure(text=f"Total: {cpu_val if cpu_val is not None else 'N/A'}%")
        self.lbl_ram_detail.configure(text=f"Used: {ram_val if ram_val is not None else 'N/A'}%")
        self.lbl_disk_detail.configure(text=f"Active Queue/Time: {disk_val if disk_val is not None else 'N/A'}%")
        self.lbl_gpu_detail.configure(text=f"GPU Temp: {gpu_val if gpu_val is not None else 'N/A'} C")

        # Bottleneck assessment
        sys_health = self.state_manager.overall_health
        self.health_badge.update_status(sys_health)

        if sys_health == "HEALTHY":
            self.bottleneck_desc.configure(
                text="No hardware bottlenecks or resource saturation detected. System operates within normal baseline boundaries.",
                fg=palette.healthy
            )
        elif sys_health in ("WARNING", "HIGH", "CRITICAL"):
            self.bottleneck_desc.configure(
                text=f"Subsystem contention identified. Severity: {sys_health}. Review active incident details for root cause analysis.",
                fg=palette.warning if sys_health == "WARNING" else palette.critical
            )
        else:
            self.bottleneck_desc.configure(
                text="Awaiting initial system telemetry and hardware assessment...",
                fg=palette.text_secondary
            )

        # Refresh historical CPU chart from Stage 3 SQLite summaries
        try:
            summaries = self.storage.sqlite.query_measurement_summaries(
                metric_name="cpu_utilization_pct",
                resolution_seconds=60,
                limit=48
            )
            if summaries:
                chart_points = []
                for s in summaries:
                    # s is a MeasurementSummaryRecord
                    ts = 0.0
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(s.bucket_start_utc.replace("Z", "+00:00"))
                        ts = dt.timestamp()
                    except Exception:
                        pass
                    chart_points.append((ts, s.mean_value))
                self.chart.render_data(chart_points, unit="%", min_val=0.0, max_val=100.0)
                self.chart_meta.configure(text=f"Range: Last {len(chart_points)} intervals | CPU Load Trend")
            else:
                self.chart.render_data([], unit="%")
                self.chart_meta.configure(text="No historical system summaries stored yet.")
        except Exception:
            self.chart.render_data([], unit="%")

    def apply_theme(self):
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)
        self.container.configure(bg=palette.bg)
        self.banner.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.title_lbl.configure(fg=palette.text_secondary, bg=palette.cards)
        self.grid_frame.configure(bg=palette.bg)
        self.lower_frame.configure(bg=palette.bg)
        self.details_card.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.chart_card.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.chart_meta.configure(fg=palette.text_secondary, bg=palette.cards)
