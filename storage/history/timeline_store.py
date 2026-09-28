"""
VEYRA Persistent PC Timeline Store.
Provides chronological event persistence and unified timeline queries across
incidents, configuration changes, sleep/resume cycles, and performance regressions.
"""
from typing import List, Optional
import json
import uuid

from app.core.time import now_utc_iso
from storage.contracts import TimelineEventRecord
from storage.sqlite_engine import SqliteStorageEngine


class PersistentTimelineStore:
    """Manages long-term storage and chronological querying of the PC Timeline."""

    def __init__(self, engine: SqliteStorageEngine):
        self.engine = engine

    def record_event(
        self,
        event_type: str,
        summary: str,
        severity: str = "INFO",
        source: str = "system",
        reference_id: str = "",
        details: Optional[dict] = None,
        timestamp_utc: Optional[str] = None
    ) -> TimelineEventRecord:
        """Creates and stores a timeline event."""
        event = TimelineEventRecord(
            event_id=f"EVT-{uuid.uuid4().hex[:12]}",
            timestamp_utc=timestamp_utc or now_utc_iso(),
            event_type=event_type,
            severity=severity,
            source=source,
            reference_id=reference_id,
            summary=summary,
            details_json=json.dumps(details or {})
        )
        self.engine.save_timeline_event(event)
        return event

    def query_timeline(
        self,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[TimelineEventRecord]:
        """Queries events on the PC Timeline."""
        return self.engine.query_timeline_events(
            start_utc=start_utc,
            end_utc=end_utc,
            event_types=event_types,
            limit=limit
        )
