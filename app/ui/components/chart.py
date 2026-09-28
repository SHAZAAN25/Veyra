"""
VEYRA Historical Canvas Chart Component.
Pure Tkinter vector canvas chart. Visualizes real historical summaries with bounds,
gridlines, and timestamps. Strictly avoids fake smoothing and never plots missing data as zero.
"""
from datetime import datetime, timezone
import tkinter as tk
from typing import List, Optional, Tuple

from app.ui.theme import ThemeManager
from storage.contracts import MeasurementSummaryRecord


class HistoricalCanvasChart(tk.Frame):
    """Interactive vector time-series canvas chart."""

    def __init__(
        self,
        parent,
        theme_manager: ThemeManager,
        title: str = "Metric History",
        unit: str = "ms",
        height: int = 180,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.title = title
        self.unit = unit
        self.height = height
        self._data: List[MeasurementSummaryRecord] = []

        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.cards, highlightbackground=palette.borders, highlightthickness=1)

        # Header with Title and Unit
        self.header_frame = tk.Frame(self, bg=palette.cards)
        self.header_frame.pack(fill=tk.X, padx=12, pady=(10, 4))

        self.title_label = tk.Label(
            self.header_frame,
            text=f"{self.title.upper()} ({self.unit})",
            font=self.theme_manager.font_caption(),
            fg=palette.text_secondary,
            bg=palette.cards
        )
        self.title_label.pack(side=tk.LEFT)

        self.stat_label = tk.Label(
            self.header_frame,
            text="",
            font=self.theme_manager.font_caption(),
            fg=palette.accent,
            bg=palette.cards
        )
        self.stat_label.pack(side=tk.RIGHT)

        # Drawing Canvas
        self.canvas = tk.Canvas(
            self,
            bg=palette.cards,
            height=self.height,
            highlightthickness=0,
            relief=tk.FLAT
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.canvas.bind("<Configure>", lambda e: self.redraw())

    def set_data(self, records: List[MeasurementSummaryRecord], title: Optional[str] = None, unit: Optional[str] = None) -> None:
        """Loads new historical summary records and redraws the chart."""
        self._data = records
        if title:
            self.title = title
        if unit is not None:
            self.unit = unit
        palette = self.theme_manager.get_palette()
        self.title_label.configure(text=f"{self.title.upper()} ({self.unit})")
        self.redraw()

    def render_data(
        self,
        points: List[Tuple[float, Optional[float]]],
        unit: Optional[str] = None,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None
    ) -> None:
        """Renders raw (timestamp, value) tuples converted to lightweight MeasurementSummaryRecords."""
        records: List[MeasurementSummaryRecord] = []
        for ts, val in points:
            from datetime import datetime, timezone
            dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts > 0 else "1970-01-01T00:00:00Z"
            records.append(
                MeasurementSummaryRecord(
                    metric_name=self.title,
                    bucket_start_utc=dt_str,
                    bucket_end_utc=dt_str,
                    resolution_seconds=60,
                    sample_count=1 if val is not None else 0,
                    min_value=val,
                    max_value=val,
                    mean_value=val,
                    median_value=val,
                    p95_value=val,
                    std_dev=0.0
                )
            )
        self.set_data(records, unit=unit)

    def redraw(self) -> None:
        """Renders vector chart directly onto the Tkinter canvas."""
        self.canvas.delete("all")
        palette = self.theme_manager.get_palette()
        self.canvas.configure(bg=palette.cards)

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50 or h < 50:
            return

        # Padding margins
        pad_left = 45
        pad_right = 20
        pad_top = 15
        pad_bottom = 25

        plot_w = w - pad_left - pad_right
        plot_h = h - pad_top - pad_bottom

        if not self._data:
            self.canvas.create_text(
                w / 2, h / 2,
                text="No historical data available for selected range.",
                fill=palette.text_secondary,
                font=self.theme_manager.font_caption()
            )
            self.stat_label.configure(text="")
            return

        # Extract valid values
        valid_points: List[Tuple[int, float]] = []
        for i, rec in enumerate(self._data):
            if rec.mean_value is not None:
                valid_points.append((i, rec.mean_value))

        if not valid_points:
            self.canvas.create_text(
                w / 2, h / 2,
                text="All samples in range are UNAVAILABLE.",
                fill=palette.warning,
                font=self.theme_manager.font_caption()
            )
            self.stat_label.configure(text="0 Valid Samples")
            return

        vals = [p[1] for p in valid_points]
        min_v = min(vals)
        max_v = max(vals)
        if min_v == max_v:
            max_v += 1.0
            min_v = max(0.0, min_v - 1.0)

        # Update stats text
        avg_val = sum(vals) / len(vals)
        self.stat_label.configure(text=f"Avg: {avg_val:.1f} {self.unit}  |  Min: {min_v:.1f}  |  Max: {max_v:.1f}")

        # Draw gridlines & Y labels
        steps = 3
        for s in range(steps + 1):
            y_ratio = s / steps
            y = pad_top + plot_h * (1.0 - y_ratio)
            v_val = min_v + (max_v - min_v) * y_ratio
            self.canvas.create_line(pad_left, y, w - pad_right, y, fill=palette.borders, dash=(2, 4))
            self.canvas.create_text(
                pad_left - 8, y,
                text=f"{v_val:.1f}",
                fill=palette.text_secondary,
                font=self.theme_manager.font_caption(),
                anchor=tk.E
            )

        # Plot data line
        n_points = len(self._data)
        coords: List[float] = []

        for i, val in valid_points:
            x_ratio = i / (n_points - 1) if n_points > 1 else 0.5
            y_ratio = (val - min_v) / (max_v - min_v) if max_v > min_v else 0.5
            x = pad_left + plot_w * x_ratio
            y = pad_top + plot_h * (1.0 - y_ratio)
            coords.extend([x, y])

        if len(coords) >= 4:
            # Draw primary line
            self.canvas.create_line(*coords, fill=palette.accent, width=2)

        # Draw point dots
        for i in range(0, len(coords), 2):
            px, py = coords[i], coords[i + 1]
            self.canvas.create_oval(px - 2, py - 2, px + 2, py + 2, fill=palette.accent, outline=palette.cards)

        # Draw start/end time markers
        t_start = self._data[0].bucket_start_utc.split("T")[-1][:5] if "T" in self._data[0].bucket_start_utc else ""
        t_end = self._data[-1].bucket_end_utc.split("T")[-1][:5] if "T" in self._data[-1].bucket_end_utc else ""
        self.canvas.create_text(pad_left, h - 10, text=t_start, fill=palette.text_secondary, font=self.theme_manager.font_caption(), anchor=tk.W)
        self.canvas.create_text(w - pad_right, h - 10, text=t_end, fill=palette.text_secondary, font=self.theme_manager.font_caption(), anchor=tk.E)

    def apply_theme(self) -> None:
        """Updates styling and redraws."""
        palette = self.theme_manager.get_palette()
        self.configure(bg=palette.cards, highlightbackground=palette.borders)
        self.header_frame.configure(bg=palette.cards)
        self.title_label.configure(bg=palette.cards, fg=palette.text_secondary)
        self.stat_label.configure(bg=palette.cards, fg=palette.accent)
        self.redraw()
