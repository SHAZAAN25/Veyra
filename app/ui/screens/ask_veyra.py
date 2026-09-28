"""
VEYRA Ask Veyra & Explain My PC Screen.
Grounded AI interface backed strictly by Veyra's verified telemetry, incidents, and baselines.
Provides deterministic natural language answers, explicit citations, and structured system explanations.
Operates 100% offline without requiring API keys or external cloud dependencies.
"""
import tkinter as tk
from typing import Any, Dict, List, Optional

from analyzer.ai.ask_veyra import AskVeyraEngine
from analyzer.ai.contracts import AIResponse, ResponseClassification
from analyzer.ai.explain_my_pc import ExplainMyPCEngine, ExplainMyPCReport
from app.ui.components.status_badge import StatusBadge
from app.ui.state import UiStateManager
from app.ui.theme import ThemeManager
from storage.engine import StorageEngine


class AskVeyraScreen(tk.Frame):
    """Evidence-grounded QA and deterministic PC explanation screen."""

    def __init__(
        self,
        parent,
        theme_manager: ThemeManager,
        state_manager: UiStateManager,
        storage: StorageEngine,
        ask_engine: Optional[AskVeyraEngine] = None,
        explain_engine: Optional[ExplainMyPCEngine] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.state_manager = state_manager
        self.storage = storage
        self.ask_engine = ask_engine or AskVeyraEngine(storage=self.storage)
        self.explain_engine = explain_engine or ExplainMyPCEngine()

        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.bg)

        self.container = tk.Frame(self, bg=palette.bg)
        self.container.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # 1. Header Card
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
            text="EVIDENCE-GROUNDED AI & NATURAL LANGUAGE QUERY",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W)

        self.title_lbl = tk.Label(
            h_left,
            text="Ask Veyra & Explain My PC",
            font=self.theme_manager.font_section(),
            fg=palette.text_primary,
            bg=palette.cards
        )
        self.title_lbl.pack(anchor=tk.W, pady=(2, 0))

        h_right = tk.Frame(self.header_frame, bg=palette.cards)
        h_right.pack(side=tk.RIGHT)

        self.status_badge = StatusBadge(h_right, theme_manager=self.theme_manager, status="HEALTHY")
        self.status_badge.pack(side=tk.LEFT)


        # 2. Split Panes:
        # Top: Explain My PC (Structured Summary)
        # Bottom: Ask Veyra (Interactive QA with Citations)
        self.explain_card = tk.Frame(
            self.container,
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=16,
            pady=14
        )
        self.explain_card.pack(fill=tk.X, pady=(0, 16))

        exp_head = tk.Frame(self.explain_card, bg=palette.cards)
        exp_head.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            exp_head,
            text="EXPLAIN MY PC (STRUCTURED EVIDENCE SYNTHESIS)",
            font=self.theme_manager.font_caption(),
            fg=palette.accent,
            bg=palette.cards
        ).pack(side=tk.LEFT)

        self.explain_btn = tk.Button(
            exp_head,
            text="Refresh Explanation",
            font=self.theme_manager.font_caption(),
            bg=palette.cards,
            fg=palette.accent,
            relief=tk.FLAT,
            padx=10,
            pady=2,
            command=self._generate_explanation
        )
        self.explain_btn.pack(side=tk.RIGHT)

        self.explain_text = tk.Label(
            self.explain_card,
            text="Click 'Refresh Explanation' to generate a structured synthesis of current PC metrics and baselines.",
            font=self.theme_manager.font_body(),
            fg=palette.text_primary,
            bg=palette.cards,
            justify=tk.LEFT,
            wraplength=920
        )
        self.explain_text.pack(anchor=tk.W)

        # 3. Ask Veyra Section
        self.ask_card = tk.Frame(
            self.container,
            bg=palette.cards,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=16,
            pady=14
        )
        self.ask_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            self.ask_card,
            text="ASK VEYRA (OFFLINE EVIDENCE-BACKED INQUIRY)",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        ).pack(anchor=tk.W, pady=(0, 8))

        # Preset Question Chips Row
        self.chips_frame = tk.Frame(self.ask_card, bg=palette.cards)
        self.chips_frame.pack(fill=tk.X, pady=(0, 10))

        presets = [
            "What is my current latency?",
            "Are there any hardware bottlenecks?",
            "What incidents occurred today?",
            "Is my CPU above baseline?",
            "What changed recently?",
        ]
        for p in presets:
            btn = tk.Button(
                self.chips_frame,
                text=p,
                font=("Segoe UI", 8),
                bg=palette.badge_bg,
                fg=palette.text_secondary,
                relief=tk.FLAT,
                padx=8,
                pady=2,
                command=lambda q=p: self._ask_preset(q)
            )
            btn.pack(side=tk.LEFT, padx=3)

        # Query Input Row
        self.input_frame = tk.Frame(self.ask_card, bg=palette.cards)
        self.input_frame.pack(fill=tk.X, pady=(0, 14))

        self.query_var = tk.StringVar()
        self.query_entry = tk.Entry(
            self.input_frame,
            textvariable=self.query_var,
            font=self.theme_manager.font_body(),
            bg=palette.badge_bg,
            fg=palette.text_primary,
            insertbackground=palette.text_primary,
            relief=tk.FLAT,
            highlightbackground=palette.borders,
            highlightthickness=1
        )
        self.query_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=4)
        self.query_entry.bind("<Return>", lambda e: self._submit_query())

        self.ask_btn = tk.Button(
            self.input_frame,
            text="Ask Veyra",
            font=self.theme_manager.font_caption(),
            bg=palette.accent,
            fg=palette.bg,
            relief=tk.FLAT,
            padx=14,
            pady=4,
            command=self._submit_query
        )
        self.ask_btn.pack(side=tk.RIGHT)

        # Answer Display Area
        self.answer_frame = tk.Frame(
            self.ask_card,
            bg=palette.badge_bg,
            highlightbackground=palette.borders,
            highlightthickness=1,
            padx=14,
            pady=12
        )
        self.answer_frame.pack(fill=tk.BOTH, expand=True)

        self.answer_header = tk.Label(
            self.answer_frame,
            text="Awaiting question...",
            font=("Segoe UI", 9, "bold"),
            fg=palette.accent,
            bg=palette.badge_bg
        )
        self.answer_header.pack(anchor=tk.W)

        self.answer_text = tk.Label(
            self.answer_frame,
            text="Type a question above or choose a preset prompt to query real telemetry and incidents.",
            font=self.theme_manager.font_body(),
            fg=palette.text_primary,
            bg=palette.badge_bg,
            justify=tk.LEFT,
            wraplength=880
        )
        self.answer_text.pack(anchor=tk.W, pady=(6, 8))

        self.citations_lbl = tk.Label(
            self.answer_frame,
            text="",
            font=("Segoe UI", 8),
            fg=palette.text_secondary,
            bg=palette.badge_bg,
            justify=tk.LEFT,
            wraplength=880
        )
        self.citations_lbl.pack(anchor=tk.W)

        self._generate_explanation()

    def _generate_explanation(self):
        """Builds structured Explain My PC text."""
        obs = self.state_manager.current_telemetry
        obs_dict = {obs.source: obs} if obs else {}

        baselines = {}
        try:
            stored_bases = self.storage.baselines.get_all_baselines()
            for b in stored_bases:
                baselines[b.metric_name] = b.mean
        except Exception:
            pass

        report: ExplainMyPCReport = self.explain_engine.generate_explanation(
            observations=obs_dict,
            baselines=baselines,
            active_incidents=self.state_manager.current_incidents,
        )

        formatted = (
            f"CURRENT STATE: {report.current_state}\n\n"
            f"OBSERVED CHANGES: {report.observed_changes}\n\n"
            f"IMPORTANT EVENTS: {report.important_events}\n\n"
            f"CONTRIBUTING FACTORS: {report.likely_contributing_factors}\n\n"
            f"CONFIDENCE: {int(report.confidence * 100)}%"
        )
        self.explain_text.configure(text=formatted)

    def _ask_preset(self, text: str):
        self.query_var.set(text)
        self._submit_query()

    def _submit_query(self):
        query = self.query_var.get().strip()
        if not query:
            return

        palette = self.theme_manager.get_palette()
        obs = self.state_manager.current_telemetry
        obs_dict = {obs.source: obs} if obs else {}

        baselines = {}
        try:
            stored_bases = self.storage.baselines.get_all_baselines()
            for b in stored_bases:
                baselines[b.metric_name] = b.mean
        except Exception:
            pass

        response: AIResponse = self.ask_engine.answer_question(
            user_question=query,
            observations=obs_dict,
            baselines=baselines,
            active_incidents=self.state_manager.current_incidents,
        )

        self.answer_header.configure(
            text=f"ANSWER [{response.response_type.value}] — Confidence: {int(response.confidence * 100)}%"
        )
        self.answer_text.configure(text=response.answer)

        cites = []
        if response.citations:
            cites.append("Verified Citations: " + " | ".join(response.citations))
        if response.unknowns:
            cites.append("Unknowns: " + " | ".join(response.unknowns))

        self.citations_lbl.configure(text="\n".join(cites))

    def update_data(self):
        """Called periodically on view refresh."""
        pass
