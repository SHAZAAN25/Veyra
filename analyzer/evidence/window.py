"""
VEYRA Evidence Window & In-Memory Observation Ring Buffer.
Maintains bounded in-memory telemetry to provide contextual evidence before,
during, and after incidents without permanent raw storage.
"""
from collections import deque
import time
from typing import List, Optional

from app.core.contracts import Observation
from analyzer.contracts import EvidenceWindow


class EvidenceBuffer:
    """
    Fixed-capacity circular in-memory buffer holding recent verified observations.
    Thread-safe for sequential reads and non-persistent.
    """
    def __init__(self, max_capacity: int = 120):
        self._max_capacity = max_capacity
        self._buffer: deque[Observation] = deque(maxlen=max_capacity)

    def append(self, observation: Observation) -> None:
        self._buffer.append(observation)

    def get_recent(self, count: int = 30) -> List[Observation]:
        """Returns the most recent N observations."""
        items = list(self._buffer)
        return items[-count:] if len(items) >= count else items

    def get_window_before(self, start_monotonic: float, window_seconds: float = 30.0) -> List[Observation]:
        """
        Retrieves observations occurring in the window [start_monotonic - window_seconds, start_monotonic].
        """
        results: List[Observation] = []
        earliest_time = start_monotonic - window_seconds
        for obs in self._buffer:
            # Check timestamp of first valid measurement in observation
            obs_time = None
            for m in obs.measurements.values():
                obs_time = m.monotonic_timestamp
                break
            if obs_time is not None and earliest_time <= obs_time <= start_monotonic:
                results.append(obs)
        return results

    def create_evidence_window(
        self,
        incident_observations: List[Observation],
        before_count: int = 15,
        after_count: int = 15
    ) -> EvidenceWindow:
        """Constructs an EvidenceWindow using recent buffer contents."""
        all_obs = list(self._buffer)
        if not incident_observations:
            return EvidenceWindow(before_observations=all_obs[-before_count:])

        first_inc = incident_observations[0]
        # Locate index of first incident observation in buffer
        try:
            inc_idx = all_obs.index(first_inc)
            before_obs = all_obs[max(0, inc_idx - before_count):inc_idx]
        except ValueError:
            before_obs = all_obs[:before_count]

        last_inc = incident_observations[-1]
        try:
            last_idx = all_obs.index(last_inc)
            after_obs = all_obs[last_idx + 1:last_idx + 1 + after_count]
        except ValueError:
            after_obs = []

        return EvidenceWindow(
            before_observations=before_obs,
            incident_observations=incident_observations,
            after_observations=after_obs
        )

    def clear(self) -> None:
        self._buffer.clear()

    @property
    def size(self) -> int:
        return len(self._buffer)
