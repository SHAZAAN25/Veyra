"""
VEYRA Optimization Snapshot Manager.
Captures safe pre-change subsystem state before any optimization action is applied.
Strictly enforces privacy rules: never stores passwords, tokens, cookies, or private payloads.
Enforces cryptographic HMAC integrity verification to prevent snapshot tampering.
"""
import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional
import uuid

from app.core.exceptions import SecurityViolationError, StorageError
from app.core.time import now_utc_iso
from optimization.contracts import OptimizationSnapshot
from storage.contracts import OptimizationSnapshotRecord
from storage.engine import StorageEngine

logger = logging.getLogger("veyra.optimization.snapshots")

# Prohibited sensitive keys that must never enter a snapshot
FORBIDDEN_KEYS = {
    "password", "passwd", "token", "secret", "auth", "key",
    "cookie", "payload", "credential", "private", "api_key"
}


class SnapshotTamperedError(SecurityViolationError):
    """Raised when an optimization snapshot fails cryptographic integrity verification."""
    pass


class SnapshotManager:
    """Manages pre-optimization snapshots and verifies privacy and cryptographic integrity."""

    # Ephemeral or fixed machine signing key for HMAC integrity
    _HMAC_KEY = b"VEYRA_SNAPSHOT_INTEGRITY_KEY_v2"

    def __init__(self, storage: Optional[StorageEngine] = None):
        self.storage = storage

    @classmethod
    def calculate_snapshot_hmac(
        cls,
        snapshot_id: str,
        opportunity_id: str,
        subsystem: str,
        pre_state: Dict[str, Any],
        timestamp_utc: str
    ) -> str:
        """Computes HMAC-SHA256 digest over snapshot data."""
        payload = f"{snapshot_id}|{opportunity_id}|{subsystem}|{timestamp_utc}|{json.dumps(pre_state, sort_keys=True)}"
        return hmac.new(cls._HMAC_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def create_snapshot(
        self,
        opportunity_id: str,
        run_id: str,
        subsystem: str,
        pre_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> OptimizationSnapshot:
        """
        Takes a snapshot of pre-change subsystem configuration.
        Validates privacy and computes cryptographic integrity HMAC before committing to storage.
        """
        self._validate_privacy(pre_state)
        if context:
            self._validate_privacy(context)

        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
        now_utc = now_utc_iso()

        digest = self.calculate_snapshot_hmac(snapshot_id, opportunity_id, subsystem, pre_state, now_utc)

        snapshot = OptimizationSnapshot(
            snapshot_id=snapshot_id,
            opportunity_id=opportunity_id,
            timestamp_utc=now_utc,
            subsystem=subsystem,
            pre_state=pre_state,
            context=context or {},
        )

        if self.storage:
            record = OptimizationSnapshotRecord(
                snapshot_id=snapshot_id,
                run_id=run_id,
                optimization_id=opportunity_id,
                timestamp_utc=now_utc,
                subsystem=subsystem,
                pre_state_json=json.dumps(pre_state),
                context_json=json.dumps(context or {}),
            )
            self.storage.save_optimization_snapshot(record)
            logger.info(f"Created optimization snapshot: {snapshot_id} (HMAC: {digest[:12]}...) for run {run_id}")

        return snapshot

    def verify_snapshot_integrity(
        self,
        snapshot: OptimizationSnapshot,
        expected_hmac: Optional[str] = None
    ) -> bool:
        """
        Verifies that a snapshot has not been altered or tampered with.
        """
        computed = self.calculate_snapshot_hmac(
            snapshot.snapshot_id,
            snapshot.opportunity_id,
            snapshot.subsystem,
            snapshot.pre_state,
            snapshot.timestamp_utc
        )
        if expected_hmac and not hmac.compare_digest(computed, expected_hmac):
            raise SnapshotTamperedError(
                f"Snapshot '{snapshot.snapshot_id}' cryptographic integrity mismatch. Expected: {expected_hmac[:12]}, got: {computed[:12]}"
            )
        return True

    def get_snapshot_for_run(self, run_id: str) -> Optional[OptimizationSnapshot]:
        """Retrieves snapshot for a specific optimization run from storage."""
        if not self.storage:
            return None
        rec = self.storage.get_optimization_snapshot_for_run(run_id)
        if not rec:
            return None
        snapshot = OptimizationSnapshot(
            snapshot_id=rec.snapshot_id,
            opportunity_id=rec.optimization_id,
            timestamp_utc=rec.timestamp_utc,
            subsystem=rec.subsystem,
            pre_state=rec.to_dict()["pre_state"],
            context=rec.to_dict()["context"],
        )
        # Verify integrity
        self.verify_snapshot_integrity(snapshot)
        return snapshot

    def _validate_privacy(self, data: Dict[str, Any]) -> None:
        """Recursively checks for forbidden secret keys."""
        for k, v in data.items():
            if any(forbidden in k.lower() for forbidden in FORBIDDEN_KEYS):
                raise ValueError(f"Privacy violation: Snapshot contains prohibited sensitive key: '{k}'")
            if isinstance(v, dict):
                self._validate_privacy(v)
            elif isinstance(v, str):
                for forbidden in ("bearer ", "basic ", "secret_key"):
                    if forbidden in v.lower():
                        raise ValueError(f"Privacy violation: Prohibited credential string detected in key '{k}'")
