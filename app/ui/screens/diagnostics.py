"""
VEYRA Advanced Diagnostics Screen.
Provides on-demand cross-layer network and system diagnostic execution,
visual Cross-Layer Root Cause Graph, and evidence-grounded recommendations.
"""
import tkinter as tk
from typing import Any, Dict, List, Optional

from app.ui.components.status_badge import StatusBadge
from app.ui.state import UiStateManager
from app.ui.theme import ThemeManager
from diagnostics.contracts import (
    CrossLayerGraph,
    DiagnosticLayer,
    DiagnosticReport,
    DiagnosticStatus,
    GraphNode,
    LayerStatus,
)
from diagnostics.runner import DiagnosticRunner
from storage.engine import StorageEngine


class DiagnosticsScreen(tk.Frame):
    """Interactive screen for on-demand cross-layer diagnostic investigations."""

    def __init__(
        self,
        parent,
        theme_manager: ThemeManager,
        state_manager: UiStateManager,
        storage: StorageEngine,
        runner: Optional[DiagnosticRunner] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.state_manager = state_manager
        self.storage = storage
        self.runner = runner or DiagnosticRunner(storage=self.storage)

        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)

        self.container = tk.Frame(self, bg=palette.bg)
        self.container.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # 1. Header & Actions Bar
        self.header_frame = tk.Frame(
            self.container,
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=16,
            pady=12
        )
        self.header_frame.pack(fill=tk.X, pady=(0, 16))

        h_left = tk.Frame(self.header_frame, bg=palette.cards)
        h_left.pack(side=tk.LEFT)

        tk.Label(
            h_left,
            text="ADVANCED CROSS-LAYER DIAGNOSTICS",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.title_lbl = tk.Label(
            h_left,
            text="Network & System Root Cause Investigation",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.title_lbl.pack(anchor=tk.W, pady=(2, 0))

        h_right = tk.Frame(self.header_frame, bg=palette.cards)
        h_right.pack(side=tk.RIGHT)

        self.status_badge = StatusBadge(h_right, theme_manager=self.theme_manager, status="HEALTHY")
        self.status_badge.pack(side=tk.LEFT, padx=(0, 12))


        self.cancel_btn = tk.Button(
            h_right,
            text="Cancel",
            font=self.theme_manager.font_caption(),
            bg=palette.cards,
            fg=palette.text_secondary,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            state=tk.DISABLED,
            command=self._handle_cancel
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.run_btn = tk.Button(
            h_right,
            text="Run Full Diagnostics",
            font=self.theme_manager.font_caption(),
            bg=palette.accent,
            fg=palette.bg,
            relief=tk.FLAT,
            padx=14,
            pady=4,
            activebackground=palette.hover,
            command=self._handle_run
        )
        self.run_btn.pack(side=tk.LEFT)

        # 2. Cross-Layer Root Cause Graph Panel
        self.graph_card = tk.Frame(
            self.container,
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=16,
            pady=14
        )
        self.graph_card.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            self.graph_card,
            text="TOPOLOGICAL ROOT CAUSE GRAPH (PC → INTERNET)",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 8))

        self.graph_nodes_frame = tk.Frame(self.graph_card, bg=palette.cards)
        self.graph_nodes_frame.pack(fill=tk.X, pady=4)

        # 6 layers in order
        self.layer_keys = [
            ("pc", "1. Local PC"),
            ("adapter", "2. Adapter"),
            ("wifi", "3. Wi-Fi"),
            ("gateway", "4. Gateway"),
            ("dns", "5. DNS"),
            ("internet", "6. Internet"),
        ]
        self.node_widgets: Dict[str, Dict[str, tk.Widget]] = {}

        for idx, (node_id, label) in enumerate(self.layer_keys):
            node_box = tk.Frame(
                self.graph_nodes_frame,
                bg=palette.badge_bg,
                highlightbackground=palette.borders,
                highlightthickness=1,
                padx=10,
                pady=8
            )
            node_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

            title_lbl = tk.Label(
                node_box,
                text=label,
                font=self.theme_manager.font_caption(),
                fg=palette.text_primary,
                bg=palette.badge_bg
            )
            title_lbl.pack(anchor=tk.W)

            status_lbl = tk.Label(
                node_box,
                text="STANDBY",
                font=("Segoe UI", 9, "bold"),
                fg=palette.text_secondary,
                bg=palette.badge_bg
            )
            status_lbl.pack(anchor=tk.W, pady=(2, 0))

            detail_lbl = tk.Label(
                node_box,
                text="Not tested yet",
                font=("Segoe UI", 8),
                fg=palette.text_secondary,
                bg=palette.badge_bg
            )
            detail_lbl.pack(anchor=tk.W)

            self.node_widgets[node_id] = {
                "box": node_box,
                "status": status_lbl,
                "detail": detail_lbl,
            }

        # 3. Assessment & Recommendations Card
        self.assessment_card = tk.Frame(
            self.container,
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=16,
            pady=14
        )
        self.assessment_card.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            self.assessment_card,
            text="INVESTIGATION ASSESSMENT & ACTIONS",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.assessment_text = tk.Label(
            self.assessment_card,
            text="Click 'Run Full Diagnostics' to begin deterministic investigation across all network layers.",
            font=self.theme_manager.font_body(),
            fg=palette.text_primary,
            bg=palette.cards,
            justify=tk.LEFT,
            wraplength=900
        )
        self.assessment_text.pack(anchor=tk.W, pady=(6, 4))

        self.recs_label = tk.Label(
            self.assessment_card,
            text="",
            font=self.theme_manager.font_caption(),
            fg=palette.accent,
            bg=palette.cards,
            justify=tk.LEFT,
            wraplength=900
        )
        self.recs_label.pack(anchor=tk.W)

        # 4. Detailed Test Results Table
        self.results_card = tk.Frame(
            self.container,
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=16,
            pady=14
        )
        self.results_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            self.results_card,
            text="INDIVIDUAL PROBE MEASUREMENTS",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 8))

        self.results_list_frame = tk.Frame(self.results_card, bg=palette.cards)
        self.results_list_frame.pack(fill=tk.BOTH, expand=True)

    def _handle_run(self):
        """Starts asynchronous diagnostic investigation."""
        self.run_btn.configure(state=tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL)
        self.status_badge.update_status("WARNING")
        self.assessment_text.configure(text="Diagnostics running... Inspecting adapter, Wi-Fi, gateway, DNS, and upstream internet.")

        self.runner.start_async(
            target="internet",
            on_complete=self._on_run_complete
        )

    def _handle_cancel(self):
        """Aborts running diagnostics."""
        self.runner.cancel()
        self.status_badge.update_status("HIGH")
        self.cancel_btn.configure(state=tk.DISABLED)
        self.run_btn.configure(state=tk.NORMAL)


    def _on_run_complete(self, report: DiagnosticReport):
        """Dispatches UI update on main thread."""
        try:
            self.after(0, lambda: self._apply_report(report))
        except Exception:
            pass

    def _apply_report(self, report: DiagnosticReport):
        """Renders diagnostic report into UI widgets."""
        palette = self.theme_manager.get_palette()
        self.run_btn.configure(state=tk.NORMAL)
        self.cancel_btn.configure(state=tk.DISABLED)

        # Update Badge
        if report.status == DiagnosticStatus.COMPLETED:
            if any(n.status == LayerStatus.FAILED for n in report.graph.nodes.values()):
                self.status_badge.update_status("CRITICAL")
            elif any(n.status == LayerStatus.DEGRADED for n in report.graph.nodes.values()):
                self.status_badge.update_status("WARNING")
            else:
                self.status_badge.update_status("HEALTHY")
        elif report.status == DiagnosticStatus.CANCELLED:
            self.status_badge.update_status("HIGH")
        else:
            self.status_badge.update_status("CRITICAL")


        # Update Graph Nodes
        for nid, w_dict in self.node_widgets.items():
            node = report.graph.nodes.get(nid)
            if node:
                st_text = node.status.value
                w_dict["status"].configure(text=st_text)
                w_dict["detail"].configure(text=node.details[:40] if node.details else "")

                if node.status == LayerStatus.HEALTHY:
                    color = palette.healthy
                elif node.status == LayerStatus.DEGRADED:
                    color = palette.warning
                elif node.status == LayerStatus.FAILED:
                    color = palette.critical
                else:
                    color = palette.text_secondary

                w_dict["status"].configure(fg=color)
                w_dict["box"].configure(highlightbackground=color)

        # Update Assessment & Recommendations
        self.assessment_text.configure(text=f"{report.assessment} (Confidence: {int(report.confidence * 100)}%)")
        if report.recommendations:
            recs_fmt = "Recommendations:\n• " + "\n• ".join(report.recommendations)
            self.recs_label.configure(text=recs_fmt)
        else:
            self.recs_label.configure(text="")

        # Update Results Table
        for child in self.results_list_frame.winfo_children():
            child.destroy()

        for item in report.test_results:
            row = tk.Frame(self.results_list_frame, bg=palette.cards, pady=4)
            row.pack(fill=tk.X)

            tk.Label(
                row,
                text=item.test_name,
                font=("Segoe UI", 9, "bold"),
                fg=palette.text_primary,
                bg=palette.cards,
                width=20,
                anchor=tk.W
            ).pack(side=tk.LEFT)

            tk.Label(
                row,
                text=f"Target: {item.target}",
                font=("Segoe UI", 9),
                fg=palette.text_secondary,
                bg=palette.cards,
                width=25,
                anchor=tk.W
            ).pack(side=tk.LEFT)

            lat_text = f"{item.latency_ms:.1f} ms" if item.latency_ms is not None else "--"
            loss_text = f"{item.packet_loss_pct:.0f}% loss" if item.packet_loss_pct is not None else "--"
            tk.Label(
                row,
                text=f"RTT: {lat_text} | Loss: {loss_text}",
                font=("Segoe UI", 9),
                fg=palette.text_secondary,
                bg=palette.cards,
                width=24,
                anchor=tk.W
            ).pack(side=tk.LEFT)

            status_color = palette.healthy if item.status == LayerStatus.HEALTHY else (
                palette.warning if item.status == LayerStatus.DEGRADED else palette.critical
            )
            tk.Label(
                row,
                text=item.status.value,
                font=("Segoe UI", 9, "bold"),
                fg=status_color,
                bg=palette.cards
            ).pack(side=tk.RIGHT)

    def update_data(self):
        """Called periodically on view refresh."""
        pass
