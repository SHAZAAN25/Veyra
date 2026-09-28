"""
VEYRA Incident Correlation & Grouping Engine.
Groups co-occurring anomalies across adjacent layers into coherent correlated events.
Assigns explainable correlation_ids to prevent alert floods.
"""
import time
import uuid
from typing import List, Dict

from analyzer.contracts import DetailedIncident, IncidentType


class IncidentCorrelator:
    """
    Correlates multiple simultaneous incidents occurring within a shared time window.
    """
    def __init__(self, grouping_window_seconds: float = 15.0):
        self.grouping_window = grouping_window_seconds
        self._active_correlation_id: str = ""
        self._last_correlation_time: float = 0.0

    def correlate(self, incidents: List[DetailedIncident]) -> List[DetailedIncident]:
        """
        Assigns or unifies correlation_ids across co-occurring incidents.
        """
        if not incidents:
            return []

        now = time.monotonic()
        if (now - self._last_correlation_time) > self.grouping_window or not self._active_correlation_id:
            self._active_correlation_id = f"corr_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        self._last_correlation_time = now

        # Assign correlation ID to all active incidents in this burst
        for inc in incidents:
            if not inc.correlation_id:
                inc.correlation_id = self._active_correlation_id

        return incidents
