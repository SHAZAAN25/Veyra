"""
VEYRA Reliable Game Identity Detector.
Identifies games strictly from running process information or registered user profiles.
Never fabricates game presence and never guesses from CPU/GPU usage patterns.
"""
import logging
import os
from typing import Dict, List, Optional, Set

import psutil

from analyzer.gaming.contracts import GameDetectionSource, GameIdentity

logger = logging.getLogger("veyra.analyzer.gaming.detector")

# Known common game executable patterns (case-insensitive)
DEFAULT_KNOWN_GAMES: Dict[str, str] = {
    "cs2.exe": "Counter-Strike 2",
    "csgo.exe": "Counter-Strike: Global Offensive",
    "valorant.exe": "VALORANT",
    "valorant-win64-shipping.exe": "VALORANT",
    "dota2.exe": "Dota 2",
    "r5apex.exe": "Apex Legends",
    "fortniteclient-win64-shipping.exe": "Fortnite",
    "overwatch.exe": "Overwatch 2",
    "leagueclient.exe": "League of Legends",
    "league of legends.exe": "League of Legends",
    "cyberpunk2077.exe": "Cyberpunk 2077",
    "witcher3.exe": "The Witcher 3",
    "gta5.exe": "Grand Theft Auto V",
    "rocketleague.exe": "Rocket League",
    "rainbowsix.exe": "Rainbow Six Siege",
    "eldenring.exe": "Elden Ring",
    "destiny2.exe": "Destiny 2",
    "starfield.exe": "Starfield",
    "baldursgate3.exe": "Baldur's Gate 3",
    "bg3.exe": "Baldur's Gate 3",
    "warframe.x64.exe": "Warframe",
}


class GameDetector:
    """Discovers active games on the system with high verification standards."""

    def __init__(self, custom_profiles: Optional[Dict[str, str]] = None):
        # Maps executable lowercase filename -> Friendly Game Title
        self._signatures: Dict[str, str] = dict(DEFAULT_KNOWN_GAMES)
        if custom_profiles:
            for exe, name in custom_profiles.items():
                self._signatures[exe.lower()] = name

    def register_profile(self, executable: str, game_name: str) -> None:
        """Adds or updates a custom game signature."""
        clean_exe = os.path.basename(executable).lower()
        self._signatures[clean_exe] = game_name

    def unregister_profile(self, executable: str) -> None:
        clean_exe = os.path.basename(executable).lower()
        self._signatures.pop(clean_exe, None)

    def detect_active_game(self) -> GameIdentity:
        """
        Scans running processes and matches against known validated executable signatures.
        Returns GameIdentity. If no game is found, returns 'Unknown' with is_validated=False.
        """
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = proc.info.get("name")
                    if not pname:
                        continue
                    pname_lower = pname.lower()
                    if pname_lower in self._signatures:
                        friendly_name = self._signatures[pname_lower]
                        pid = proc.info.get("pid")
                        return GameIdentity(
                            name=friendly_name,
                            executable=pname,
                            process_id=pid,
                            detection_source=GameDetectionSource.PROCESS_MATCH,
                            is_validated=True,
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug(f"Process inspection during game detection encountered: {e}")

        return GameIdentity(
            name="Unknown",
            executable=None,
            process_id=None,
            detection_source=GameDetectionSource.UNKNOWN,
            is_validated=False,
        )
