"""
VEYRA Time Foundation.
Standardizes internal UTC storage, UI local time conversion, monotonic duration measurement,
and system sleep/wake gap detection.
"""
from datetime import datetime, timezone
import time
from typing import Tuple


def now_utc_iso() -> str:
    """Returns current UTC timestamp formatted as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def now_utc_timestamp() -> float:
    """Returns current UTC epoch timestamp in seconds."""
    return datetime.now(timezone.utc).timestamp()


def monotonic_time() -> float:
    """Returns steady monotonic time in seconds, immune to wall-clock adjustments."""
    return time.monotonic()


def format_local_display(utc_iso_string: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Converts a stored UTC ISO string to the user's local time string for UI presentation."""
    try:
        dt_utc = datetime.fromisoformat(utc_iso_string)
        dt_local = dt_utc.astimezone()  # converts to local system timezone
        return dt_local.strftime(fmt)
    except Exception:
        return utc_iso_string


class TimeTracker:
    """
    Tracks elapsed intervals using both monotonic clock and wall clock to detect
    system suspension (sleep/wake events) and prevent false outage alerts.
    """
    def __init__(self):
        self.last_wall_time = now_utc_timestamp()
        self.last_mono_time = monotonic_time()

    def check_interval(self, expected_interval_seconds: float) -> Tuple[float, bool]:
        """
        Calculates elapsed time and returns (elapsed_seconds, was_sleep_or_gap_detected).
        If wall-clock elapsed time significantly exceeds monotonic elapsed time or expected
        interval, a system sleep/resume or clock jump occurred.
        """
        current_wall = now_utc_timestamp()
        current_mono = monotonic_time()

        mono_elapsed = current_mono - self.last_mono_time
        wall_elapsed = current_wall - self.last_wall_time

        # Sleep detection: If wall elapsed is > 3x expected interval and exceeds monotonic elapsed + 5s
        sleep_detected = (wall_elapsed > (expected_interval_seconds * 3.0)) and (wall_elapsed > mono_elapsed + 5.0)

        # Update last marks
        self.last_wall_time = current_wall
        self.last_mono_time = current_mono

        return mono_elapsed, sleep_detected
