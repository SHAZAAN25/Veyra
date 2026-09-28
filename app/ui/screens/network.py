"""
VEYRA Network Screen.
Visualizes the 5-layer network topology (Laptop -> Adapter -> Gateway -> DNS -> Internet),
live interface configuration, Wi-Fi parameters, and historical latency trends.
"""
import tkinter as tk
from typing import Optional

from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager
from app.ui.components.status_badge import StatusBadge
from app.ui.components.chart import HistoricalCanvasChart
from storage.engine import StorageEngine


class NetworkScreen(tk.Frame):
    """Network observability, topology, and diagnostics screen."""

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

        # 1. Topology Banner
        self.topo_frame = tk.Frame(self, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=12)
        self.topo_frame.pack(fill=tk.X, padx=20, pady=(16, 10))

        self.topo_title = tk.Label(
            self.topo_frame,
            text="CROSS-LAYER NETWORK TOPOLOGY",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards,
            anchor=tk.W
        )
        self.topo_title.pack(fill=tk.X, pady=(0, 8))

        # 5 Nodes Container
        self.nodes_frame = tk.Frame(self.topo_frame, bg=palette.cards)
        self.nodes_frame.pack(fill=tk.X, expand=True)

        self.badge_laptop = StatusBadge(self.nodes_frame, theme_manager=self.theme_manager, status="HEALTHY")
        self.badge_laptop.pack(side=tk.LEFT, padx=4)

        lbl1 = tk.Label(self.nodes_frame, text="->", fg=palette.text_secondary, bg=palette.cards, font=self.theme_manager.font_heading())
        lbl1.pack(side=tk.LEFT, padx=4)

        self.badge_adapter = StatusBadge(self.nodes_frame, theme_manager=self.theme_manager, status="UNKNOWN")
        self.badge_adapter.pack(side=tk.LEFT, padx=4)

        lbl2 = tk.Label(self.nodes_frame, text="->", fg=palette.text_secondary, bg=palette.cards, font=self.theme_manager.font_heading())
        lbl2.pack(side=tk.LEFT, padx=4)

        self.badge_gateway = StatusBadge(self.nodes_frame, theme_manager=self.theme_manager, status="UNKNOWN")
        self.badge_gateway.pack(side=tk.LEFT, padx=4)

        lbl3 = tk.Label(self.nodes_frame, text="->", fg=palette.text_secondary, bg=palette.cards, font=self.theme_manager.font_heading())
        lbl3.pack(side=tk.LEFT, padx=4)

        self.badge_dns = StatusBadge(self.nodes_frame, theme_manager=self.theme_manager, status="UNKNOWN")
        self.badge_dns.pack(side=tk.LEFT, padx=4)

        lbl4 = tk.Label(self.nodes_frame, text="->", fg=palette.text_secondary, bg=palette.cards, font=self.theme_manager.font_heading())
        lbl4.pack(side=tk.LEFT, padx=4)

        self.badge_internet = StatusBadge(self.nodes_frame, theme_manager=self.theme_manager, status="UNKNOWN")
        self.badge_internet.pack(side=tk.LEFT, padx=4)

        # 2. Detailed Technical Parameters (Two Columns)
        self.details_row = tk.Frame(self, bg=palette.bg)
        self.details_row.pack(fill=tk.X, padx=20, pady=8)

        # Left Column: Adapter & Wi-Fi Details
        self.box_adapter = tk.Frame(self.details_row, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=14, pady=12)
        self.box_adapter.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self.adapter_hdr = tk.Label(self.box_adapter, text="PHYSICAL & DATA LINK LAYER", font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards, anchor=tk.W)
        self.adapter_hdr.pack(fill=tk.X, pady=(0, 6))

        self.adapter_text = tk.Label(self.box_adapter, text="Loading adapter...", font=self.theme_manager.font_mono(), fg=palette.text_primary, bg=palette.cards, justify=tk.LEFT, anchor=tk.NW)
        self.adapter_text.pack(fill=tk.BOTH, expand=True)

        # Right Column: Gateway, DNS & Upstream Latency
        self.box_wan = tk.Frame(self.details_row, bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=14, pady=12)
        self.box_wan.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        self.wan_hdr = tk.Label(self.box_wan, text="NETWORK & TRANSPORT LAYER", font=self.theme_manager.font_caption(), fg=palette.text_secondary, bg=palette.cards, anchor=tk.W)
        self.wan_hdr.pack(fill=tk.X, pady=(0, 6))

        self.wan_text = tk.Label(self.box_wan, text="Loading transport metrics...", font=self.theme_manager.font_mono(), fg=palette.text_primary, bg=palette.cards, justify=tk.LEFT, anchor=tk.NW)
        self.wan_text.pack(fill=tk.BOTH, expand=True)

        # 3. Historical Latency Chart
        self.chart = HistoricalCanvasChart(self, theme_manager=self.theme_manager, title="Internet Latency Trend (Last 1 Hour)", unit="ms", height=160)
        self.chart.pack(fill=tk.BOTH, expand=True, padx=20, pady=(8, 16))

        self.refresh()

    def refresh(self) -> None:
        """Updates live network metrics and refreshes chart."""
        val = self.state_manager.get_metric_value
        st = self.state_manager.get_metric_state

        # Update Topology Badges
        self.badge_adapter.update_status("HEALTHY" if st("adapter_link_speed_mbps") == "AVAILABLE" else st("adapter_link_speed_mbps"))
        self.badge_gateway.update_status("HEALTHY" if st("gateway_ping_ms") == "AVAILABLE" else st("gateway_ping_ms"))
        self.badge_dns.update_status("HEALTHY" if st("dns_resolution_time_ms") == "AVAILABLE" else st("dns_resolution_time_ms"))
        self.badge_internet.update_status("HEALTHY" if st("network_rtt_ms") == "AVAILABLE" else st("network_rtt_ms"))

        # Format Adapter Text
        adapter_lines = [
            f"Active Adapter : {val('adapter_name') or 'None'}",
            f"MAC Address    : {val('adapter_mac') or 'Unavailable'}",
            f"IPv4 Address   : {val('adapter_ipv4') or 'Unavailable'}",
            f"Link Speed     : {val('adapter_link_speed_mbps') or '0'} Mbps",
            "",
            "WI-FI LINK PARAMETERS:",
            f"SSID / BSSID   : {val('wifi_ssid') or 'N/A'} ({val('wifi_bssid') or 'N/A'})",
            f"Signal Quality : {val('wifi_signal_pct') or '0'}% ({val('wifi_rssi_dbm') or '0'} dBm)",
            f"Radio & Band   : {val('wifi_radio') or 'N/A'} ({val('wifi_band') or 'N/A'}, Ch {val('wifi_channel') or 'N/A'})",
        ]
        self.adapter_text.configure(text="\n".join(adapter_lines))

        # Format Transport Text
        wan_lines = [
            f"Default Gateway : {val('gateway_ip') or 'Unavailable'} ({val('gateway_ping_ms') or 'N/A'} ms)",
            f"DNS Target Server: {val('dns_target') or 'google.com'} ({val('dns_resolution_time_ms') or 'N/A'} ms)",
            f"Internet RTT     : {val('network_rtt_ms') or 'Unavailable'} ms",
            f"Packet Loss Rate : {val('network_packet_loss_pct') or '0.0'}%",
            f"RFC 3550 Jitter  : {val('network_jitter_ms') or 'Unavailable'} ms",
            "",
            "LOCAL THROUGHPUT DELTA:",
            f"Ingress (Download): {val('throughput_in_mbps') or '0.0'} Mbps",
            f"Egress (Upload)   : {val('throughput_out_mbps') or '0.0'} Mbps",
        ]
        self.wan_text.configure(text="\n".join(wan_lines))

        # Load recent 1-hour historical data for chart
        summaries = self.storage.sqlite.query_measurement_summaries(
            metric_name="network_rtt_ms",
            resolution_seconds=60,
            limit=60
        )
        if hasattr(self.chart, "set_data"):
            self.chart.set_data(summaries, title="Internet Latency Trend", unit="ms")
        elif hasattr(self.chart, "render_data"):
            pts = []
            for s in summaries:
                ts = 0.0
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(s.bucket_start_utc.replace("Z", "+00:00"))
                    ts = dt.timestamp()
                except Exception:
                    pass
                pts.append((ts, s.mean_value))
            self.chart.render_data(pts, unit="ms")

    def update_data(self) -> None:
        """Alias for refresh to unify screen lifecycle interface."""
        self.refresh()

    def apply_theme(self) -> None:
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)
        self.topo_frame.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.topo_title.configure(bg=palette.cards, fg=palette.text_secondary)
        self.nodes_frame.configure(bg=palette.cards)
        self.details_row.configure(bg=palette.bg)
        self.box_adapter.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.adapter_hdr.configure(bg=palette.cards, fg=palette.text_secondary)
        self.adapter_text.configure(bg=palette.cards, fg=palette.text_primary)
        self.box_wan.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.wan_hdr.configure(bg=palette.cards, fg=palette.text_secondary)
        self.wan_text.configure(bg=palette.cards, fg=palette.text_primary)
        self.chart.apply_theme()
        self.refresh()
