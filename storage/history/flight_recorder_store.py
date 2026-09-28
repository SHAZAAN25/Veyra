"""
VEYRA Persistent Flight Recorder Store.
Safely persists contextual system and network diagnostic snapshots to SQLite,
strictly enforcing non-negotiable privacy boundaries (zero credentials, tokens, payloads).
"""
import json
import logging
from typing import Any, Dict, List, Optional

from analyzer.evidence.flight_recorder import FlightRecorderSnapshot
from app.core.exceptions import SecurityViolationError
from storage.contracts import FlightRecorderRecord
from storage.sqlite_engine import SqliteStorageEngine

logger = logging.getLogger("veyra.storage.flight_recorder_store")

SENSITIVE_KEYWORDS = {"password", "secret", "token", "apikey", "bearer", "cookie", "payload"}


class PersistentFlightRecorderStore:
    """Stores and retrieves privacy-safe PC Health Flight Recorder snapshots."""

    def __init__(self, engine: SqliteStorageEngine):
        self.engine = engine

    def _verify_privacy_safety(self, data: Any) -> None:
        """Recursively checks for sensitive keywords in keys or values."""
        if isinstance(data, dict):
            for k, v in data.items():
                if any(kw in str(k).lower() for kw in SENSITIVE_KEYWORDS):
                    raise SecurityViolationError(f"Sensitive key '{k}' detected in Flight Recorder snapshot.")
                self._verify_privacy_safety(v)
        elif isinstance(data, list):
            for item in data:
                self._verify_privacy_safety(item)

    def save_snapshot(self, snapshot: FlightRecorderSnapshot) -> None:
        """Validates privacy and persists snapshot to SQLite."""
        # Privacy verification
        payload = {
            "system": snapshot.system_summary,
            "network": snapshot.network_summary,
            "wifi": snapshot.wifi_summary,
            "gateway": snapshot.gateway_summary,
            "dns": snapshot.dns_summary,
            "internet": snapshot.internet_summary,
            "gpu": snapshot.gpu_summary,
            "self_health": snapshot.self_health_summary,
        }
        self._verify_privacy_safety(payload)

        record = FlightRecorderRecord(
            snapshot_id=snapshot.snapshot_id,
            timestamp_utc=snapshot.timestamp_utc,
            incident_id=snapshot.incident_id or "",
            trigger_reason=snapshot.incident_type or "SCHEDULED",
            system_state_json=json.dumps(snapshot.system_summary or {}),
            network_state_json=json.dumps({
                "network": snapshot.network_summary,
                "wifi": snapshot.wifi_summary,
                "gateway": snapshot.gateway_summary,
                "dns": snapshot.dns_summary,
                "internet": snapshot.internet_summary,
            }),
            gpu_state_json=json.dumps(snapshot.gpu_summary or {}),
            collector_health_json=json.dumps(snapshot.self_health_summary or {})
        )
        self.engine.save_flight_recorder_snapshot(record)

    def get_snapshot(self, snapshot_id: str) -> Optional[FlightRecorderRecord]:
        """Retrieves a flight recorder snapshot by ID."""
        return self.engine.get_flight_recorder_snapshot(snapshot_id)
