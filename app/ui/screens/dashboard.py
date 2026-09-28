"""
VEYRA Dashboard Screen.
Primary landing experience communicating overall health, active anomalies,
key live metrics, baseline comparisons, and PC timeline highlights.
"""
import tkinter as tk
from typing import Optional

from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager
from app.ui.components.status_badge import StatusBadge
from app.ui.components.metric_card import MetricCard
from app.ui.components.timeline_view import TimelineView
from storage.engine import StorageEngine


class DashboardScreen(tk.Frame):
    """Primary operational overview screen."""

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

        # 1. Top Status Banner (Overall Health + Freshness)
        self.banner = tk.Frame(self, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=12)
        self.banner.pack(fill=tk.X, padx=20, pady=(16, 12))

        banner_left = tk.Frame(self.banner, bg=palette.cards)
        banner_left.pack(side=tk.LEFT)

        self.sys_title = tk.Label(
            banner_left,
            text="SYSTEM & NETWORK STATUS",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        )
        self.sys_title.pack(anchor=tk.W)

        self.status_badge = StatusBadge(banner_left, theme_manager=self.theme_manager, status="UNKNOWN")
        self.status_badge.pack(anchor=tk.W, pady=(4, 0))

        banner_right = tk.Frame(self.banner, bg=palette.cards)
        banner_right.pack(side=tk.RIGHT)

        self.freshness_badge = StatusBadge(banner_right, theme_manager=self.theme_manager, status="UNAVAILABLE")
        self.freshness_badge.pack(anchor=tk.E)

        self.ts_label = tk.Label(
            banner_right,
            text="Connecting to engine...",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        )
        self.ts_label.pack(anchor=tk.E, pady=(4, 0))

        # 2. Active Incidents Alert Bar (Visible only when active incidents exist)
        self.alert_frame = tk.Frame(self, bg=palette.critical, padx=14, pady=8)
        self.alert_label = tk.Label(
            self.alert_frame,
            text="",
            font=self.theme_manager.font_subheading(),
            fg="#FFFFFF",
            bg=palette.critical,
            anchor=tk.W
        )
        self.alert_label.pack(fill=tk.X)

        # 3. Key Telemetry Grid (2 rows x 4 columns)
        self.grid_frame = tk.Frame(self, bg=palette.bg)
        self.grid_frame.pack(fill=tk.X, padx=20, pady=8)

        # Row 1: Network Metrics
        self.card_gateway = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="Gateway Ping", unit="ms")
        self.card_gateway.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.card_internet = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="Internet RTT", unit="ms")
        self.card_internet.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        self.card_loss = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="Packet Loss", unit="%")
        self.card_loss.grid(row=0, column=2, sticky="nsew", padx=6, pady=6)

        self.card_jitter = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="Jitter (RFC 3550)", unit="ms")
        self.card_jitter.grid(row=0, column=3, sticky="nsew", padx=6, pady=6)

        # Row 2: System Metrics
        self.card_cpu = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="CPU Utilization", unit="%")
        self.card_cpu.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        self.card_ram = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="RAM Utilization", unit="%")
        self.card_ram.grid(row=1, column=1, sticky="nsew", padx=6, pady=6)

        self.card_disk = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="Disk Utilization", unit="%")
        self.card_disk.grid(row=1, column=2, sticky="nsew", padx=6, pady=6)

        self.card_wifi = MetricCard(self.grid_frame, theme_manager=self.theme_manager, title="Wi-Fi Signal", unit="%")
        self.card_wifi.grid(row=1, column=3, sticky="nsew", padx=6, pady=6)

        for col in range(4):
            self.grid_frame.columnconfigure(col, weight=1)

        # 4. Bottom Context Area: Timeline Highlights & Baseline Quick Info
        self.bottom_frame = tk.Frame(self, bg=palette.bg)
        self.bottom_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(8, 16))

        self.timeline_component = TimelineView(self.bottom_frame, theme_manager=self.theme_manager, max_items=5)
        self.timeline_component.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self.baseline_box = tk.Frame(self.bottom_frame, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=14, pady=12)
        self.baseline_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        self.baseline_hdr = tk.Label(
            self.baseline_box,
            text="PERSONAL PC BASELINE OVERVIEW",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards,
            anchor=tk.W
        )
        self.baseline_hdr.pack(fill=tk.X, pady=(0, 8))

        self.baseline_content = tk.Label(
            self.baseline_box,
            text="Loading personal baseline status...",
            font=self.theme_manager.font_body(),
            fg=palette.text_primary,
            bg=palette.cards,
            justify=tk.LEFT,
            anchor=tk.NW
        )
        self.baseline_content.pack(fill=tk.BOTH, expand=True)

        self.refresh()

    def refresh(self) -> None:
        """Pulls latest state from UiStateManager and updates widgets."""
        obs = self.state_manager.latest_observation
        freshness = self.state_manager.freshness_state
        health = self.state_manager.overall_health

        # Update Banner
        self.status_badge.update_status(health)
        self.freshness_badge.update_status(freshness)

        if obs:
            t_short = obs.timestamp_utc.split("T")[-1][:8] if "T" in obs.timestamp_utc else obs.timestamp_utc
            self.ts_label.configure(text=f"Last updated: {t_short} UTC")
        else:
            self.ts_label.configure(text="Awaiting telemetry...")

        # Update Active Incident Warning Bar
        active = self.state_manager.active_incidents
        if active:
            first_inc = active[0]
            self.alert_label.configure(
                text=f"[ACTIVE INCIDENT] {first_inc.incident_type.value}: {first_inc.summary} (Duration: {first_inc.duration_seconds:.0f}s)"
            )
            if not self.alert_frame.winfo_ismapped():
                self.alert_frame.pack(fill=tk.X, padx=20, pady=(0, 8), before=self.grid_frame)
        else:
            if self.alert_frame.winfo_ismapped():
                self.alert_frame.pack_forget()

        # Update Metric Cards
        self.card_gateway.update_metric(
            self.state_manager.get_metric_value("gateway_ping_ms"),
            freshness=self.state_manager.get_metric_state("gateway_ping_ms")
        )
        self.card_internet.update_metric(
            self.state_manager.get_metric_value("network_rtt_ms"),
            freshness=self.state_manager.get_metric_state("network_rtt_ms")
        )
        self.card_loss.update_metric(
            self.state_manager.get_metric_value("network_packet_loss_pct"),
            freshness=self.state_manager.get_metric_state("network_packet_loss_pct")
        )
        self.card_jitter.update_metric(
            self.state_manager.get_metric_value("network_jitter_ms"),
            freshness=self.state_manager.get_metric_state("network_jitter_ms")
        )
        self.card_cpu.update_metric(
            self.state_manager.get_metric_value("cpu_utilization_pct"),
            freshness=self.state_manager.get_metric_state("cpu_utilization_pct")
        )
        self.card_ram.update_metric(
            self.state_manager.get_metric_value("memory_utilization_pct"),
            freshness=self.state_manager.get_metric_state("memory_utilization_pct")
        )
        self.card_disk.update_metric(
            self.state_manager.get_metric_value("disk_utilization_pct"),
            freshness=self.state_manager.get_metric_state("disk_utilization_pct")
        )
        self.card_wifi.update_metric(
            self.state_manager.get_metric_value("wifi_signal_pct"),
            freshness=self.state_manager.get_metric_state("wifi_signal_pct")
        )

        # Update Timeline
        timeline_events = self.storage.timeline.query_timeline(limit=5)
        self.timeline_component.set_events(timeline_events)

        # Update Baseline Overview
        base = self.storage.baselines.get_baseline("network_rtt_ms")
        if base:
            txt = (
                f"Metric: Internet RTT\n"
                f"Status: {base.quality.value}\n"
                f"Samples: {base.sample_count}\n"
                f"Mean: {base.mean} ms  |  p95: {base.p95} ms\n"
                f"Normal Range: {base.min_value} - {base.max_value} ms"
            )
        else:
            txt = "No established baseline yet.\nPersonal baseline is observing normal behavior..."
        self.baseline_content.configure(text=txt)

    def update_data(self) -> None:
        """Alias for refresh to unify screen lifecycle interface."""
        self.refresh()

    def apply_theme(self) -> None:
        """Applies active theme colors to all child widgets."""
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)
        self.banner.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.sys_title.configure(bg=palette.cards, fg=palette.text_secondary)
        self.ts_label.configure(bg=palette.cards, fg=palette.text_secondary)
        self.grid_frame.configure(bg=palette.bg)
        self.bottom_frame.configure(bg=palette.bg)
        self.baseline_box.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.baseline_hdr.configure(bg=palette.cards, fg=palette.text_secondary)
        self.baseline_content.configure(bg=palette.cards, fg=palette.text_primary)

        for card in (self.card_gateway, self.card_internet, self.card_loss, self.card_jitter,
                     self.card_cpu, self.card_ram, self.card_disk, self.card_wifi):
            card.apply_theme()

        self.timeline_component.apply_theme()
        self.refresh()
