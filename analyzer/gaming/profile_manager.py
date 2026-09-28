"""
VEYRA Game-Specific Performance Profile Manager.
Manages user and system profiles for gaming titles, including preferred telemetry metrics
and baseline references. Strictly safe: never modifies game files or anti-cheat configurations.
"""
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.time import now_utc_iso
from storage.contracts import GamingProfileRecord
from storage.engine import StorageEngine

logger = logging.getLogger("veyra.analyzer.gaming.profile_manager")


class GameProfileManager:
    """Manages game profile creation, retrieval, updates, and deletion."""

    def __init__(self, storage: StorageEngine):
        self.storage = storage

    def create_or_update_profile(
        self,
        game_name: str,
        executable: str,
        expected_process: Optional[str] = None,
        preferred_metrics: Optional[List[str]] = None,
        baseline_references: Optional[Dict[str, Any]] = None,
        known_config: Optional[Dict[str, Any]] = None,
    ) -> GamingProfileRecord:
        """Creates or updates a game performance profile."""
        existing = self.storage.get_gaming_profile(game_name)
        profile_id = existing.profile_id if existing else f"prof_{uuid.uuid4().hex[:12]}"
        created_at = existing.created_at_utc if existing else now_utc_iso()

        rec = GamingProfileRecord(
            profile_id=profile_id,
            game_name=game_name,
            executable=executable,
            expected_process=expected_process or executable,
            preferred_metrics_json=json.dumps(preferred_metrics or ["cpu", "gpu", "latency", "packet_loss"]),
            baseline_references_json=json.dumps(baseline_references or {}),
            known_config_json=json.dumps(known_config or {}),
            created_at_utc=created_at,
            updated_at_utc=now_utc_iso(),
        )
        self.storage.save_gaming_profile(rec)
        logger.info(f"Saved game profile: {game_name} [{profile_id}]")
        return rec

    def get_profile(self, profile_id_or_name: str) -> Optional[GamingProfileRecord]:
        return self.storage.get_gaming_profile(profile_id_or_name)

    def list_profiles(self) -> List[GamingProfileRecord]:
        return self.storage.list_gaming_profiles()

    def delete_profile(self, profile_id: str) -> bool:
        """Deletes profile metadata. Historical sessions are strictly preserved."""
        return self.storage.delete_gaming_profile(profile_id)
