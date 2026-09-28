"""
VEYRA Visual Incident Replay Component.
Visualizes persistent Before -> During -> After incident timelines answering the 5 core
replay questions from real historical evidence.
"""
import tkinter as tk
from typing import Any, Dict, Optional

from app.ui.theme import ThemeManager


class ReplayViewer(tk.Frame):
    """Interactive visual timeline player for incident replay packages."""

    def __init__(self, parent, theme_manager: ThemeManager, **kwargs):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self._replay_data: Optional[Dict[str, Any]] = None
        self._current_phase = "EVENT"

        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1, padx=16, pady=14)

        # Header Title
        self.header_label = tk.Label(
            self,
            text="INCIDENT REPLAY & EVIDENCE INVESTIGATOR",
            font=self.theme_manager.font_heading(),
            fg=palette.text_primary,
            bg=palette.cards,
            anchor=tk.W
        )
        self.header_label.pack(fill=tk.X)

        # Phase Selector Bar: [ 1. BEFORE ] [ 2. EVENT ] [ 3. RECOVERY ]
        self.phase_bar = tk.Frame(self, bg=palette.cards)
        self.phase_bar.pack(fill=tk.X, pady=(12, 10))

        self.btn_before = tk.Button(
            self.phase_bar,
            text="1. BEFORE (Normal Baseline)",
            font=self.theme_manager.font_subheading(),
            command=lambda: self.select_phase("BEFORE"),
            relief=tk.FLAT,
            padx=10,
            pady=4
        )
        self.btn_before.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_event = tk.Button(
            self.phase_bar,
            text="2. EVENT (Failure Window)",
            font=self.theme_manager.font_subheading(),
            command=lambda: self.select_phase("EVENT"),
            relief=tk.FLAT,
            padx=10,
            pady=4
        )
        self.btn_event.pack(side=tk.LEFT, padx=6)

        self.btn_recovery = tk.Button(
            self.phase_bar,
            text="3. RECOVERY (Post-Incident)",
            font=self.theme_manager.font_subheading(),
            command=lambda: self.select_phase("RECOVERY"),
            relief=tk.FLAT,
            padx=10,
            pady=4
        )
        self.btn_recovery.pack(side=tk.LEFT, padx=6)

        # Content Box
        self.content_frame = tk.Frame(self, bg=palette.bg, highlightbackground=palette.borders, highlightthickness=1, padx=12, pady=12)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.phase_title = tk.Label(
            self.content_frame,
            text="",
            font=self.theme_manager.font_subheading(),
            fg=palette.accent,
            bg=palette.bg,
            anchor=tk.W
        )
        self.phase_title.pack(fill=tk.X)

        self.details_label = tk.Label(
            self.content_frame,
            text="No incident selected for replay.",
            font=self.theme_manager.font_mono(),
            fg=palette.text_primary,
            bg=palette.bg,
            justify=tk.LEFT,
            anchor=tk.NW
        )
        self.details_label.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.apply_theme()

    def set_replay(self, replay_data: Dict[str, Any]) -> None:
        """Loads persistent replay data and renders default EVENT phase."""
        self._replay_data = replay_data
        self.select_phase("EVENT")

    def load_replay(self, replay_data: Dict[str, Any]) -> None:
        """Alias for set_replay."""
        self.set_replay(replay_data)

    def clear(self) -> None:
        """Clears current replay view."""
        self._replay_data = None
        self.details_label.configure(text="No incident selected for replay.")

    def select_phase(self, phase: str) -> None:
        """Switches the active replay phase view."""
        self._current_phase = phase
        palette = self.theme_manager.get_palette()

        # Update button highlights
        for btn, name in ((self.btn_before, "BEFORE"), (self.btn_event, "EVENT"), (self.btn_recovery, "RECOVERY")):
            if name == phase:
                btn.configure(bg=palette.accent, fg=palette.bg)
            else:
                btn.configure(bg=palette.secondary, fg=palette.text_secondary)

        if not self._replay_data:
            self.details_label.configure(text="No incident selected for replay.")
            return

        answers = self._replay_data.get("answers", {})

        if phase == "BEFORE":
            self.phase_title.configure(text="Phase 1: What was normal before the event?")
            normal = answers.get("what_was_normal", {})
            lines = ["METRIC BASELINE SUMMARY PRIOR TO INCIDENT:"]
            if normal:
                for k, v in normal.items():
                    lines.append(f"  * {k:<24}: Mean={v.get('mean')} | Min={v.get('min')} | Max={v.get('max')}")
            else:
                lines.append("  (No prior telemetry samples captured in Before window)")
            self.details_label.configure(text="\n".join(lines), fg=palette.text_primary)

        elif phase == "EVENT":
            self.phase_title.configure(text="Phase 2: What changed and what failed?")
            what_changed = answers.get("what_changed", {})
            what_failed = answers.get("what_failed", {})
            lines = [
                "ANOMALY TRIGGER & FAILURE BREAKDOWN:",
                f"  * Trigger Metric      : {what_changed.get('trigger_metric')} = {what_changed.get('trigger_value')}",
                f"  * Primary Root Cause  : {what_failed.get('primary_cause')}",
                f"  * Cause Explanation   : {what_failed.get('cause_explanation')}",
                f"  * Confidence Score    : {what_failed.get('confidence_score') * 100:.0f}%",
                f"  * Affected Layers     : {', '.join(what_failed.get('affected_layers', []))}",
                f"  * Incident Severity   : {what_failed.get('severity')}",
                f"  * Duration            : {what_failed.get('duration_seconds')} seconds",
            ]
            self.details_label.configure(text="\n".join(lines), fg=palette.warning)

        elif phase == "RECOVERY":
            self.phase_title.configure(text="Phase 3: What recovered and what remained degraded?")
            what_recovered = answers.get("what_recovered", {})
            remained_degraded = answers.get("what_remained_degraded", [])
            lines = [
                "RECOVERY VERIFICATION:",
                f"  * Incident Status     : {what_recovered.get('status')}",
                f"  * Recovery Metric Val : {what_recovered.get('recovery_value')}",
                f"  * Ended At            : {what_recovered.get('ended_at_utc')}",
                "",
                "LINGERING DEGRADATION STATUS:"
            ]
            if remained_degraded:
                for deg in remained_degraded:
                    lines.append(f"  [!] {deg}")
            else:
                lines.append("  [OK] All measured telemetry returned within normal baseline parameters.")

            self.details_label.configure(text="\n".join(lines), fg=palette.healthy)

    def apply_theme(self) -> None:
        """Applies active theme colors."""
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.header_label.configure(bg=palette.cards, fg=palette.text_primary)
        self.phase_bar.configure(bg=palette.cards)
        self.content_frame.configure(bg=palette.bg, highlightbackground=palette.borders)
        self.phase_title.configure(bg=palette.bg, fg=palette.accent)
        self.details_label.configure(bg=palette.bg)
        self.select_phase(self._current_phase)
