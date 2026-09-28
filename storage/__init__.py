"""
VEYRA Storage Engine Interfaces & Implementations.
Establishes the contract for RAM buffering, historical compaction, and incident storage.
Raw telemetry is stored ephemerally in RAM; only compacted summaries are persisted permanently.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.contracts import HistoricalSummary, Incident, Observation


class BaseStorageEngine(ABC):
    """Abstract base class for VEYRA persistence engines."""

    @abstractmethod
    def append_raw_observation(self, observation: Observation) -> None:
        """Buffers raw observation into RAM buffer."""
        pass

    @abstractmethod
    def persist_summary(self, summary: HistoricalSummary) -> None:
        """Persists a compacted historical rollup bucket into long-term SQLite storage."""
        pass

    @abstractmethod
    def query_summaries(
        self,
        metric_name: str,
        start_utc: str,
        end_utc: str,
        bucket_size_minutes: int
    ) -> List[HistoricalSummary]:
        """Retrieves aggregated historical summaries for display in charts."""
        pass

    @abstractmethod
    def persist_incident(self, incident: Incident) -> None:
        """Permanently records an incident snapshot with root-cause diagnostic records."""
        pass

    @abstractmethod
    def query_incidents(self, limit: int = 50) -> List[Incident]:
        """Retrieves historical incidents."""
        pass


from storage.sqlite_engine import SqliteStorageEngine
from storage.engine import StorageEngine

__all__ = [
    "BaseStorageEngine",
    "SqliteStorageEngine",
    "StorageEngine",
]
