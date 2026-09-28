"""
VEYRA Path & Directory Resolution Engine.
Stage 8 Packaging & Production Runtime.

Enforces strict separation between read-only installation binaries and writable user data:
- INSTALLATION DIRECTORY: sys._MEIPASS or C:\\Program Files\\VEYRA (Read-Only)
- USER DATA DIRECTORY: %LOCALAPPDATA%\\VEYRA (Writable by standard unprivileged user)
"""
import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Returns True if running inside a packaged standalone executable (e.g. PyInstaller)."""
    return getattr(sys, "frozen", False)


def get_installation_dir() -> Path:
    """
    Returns the root directory of the installation or application bundle.
    Contains immutable application binaries, packages, and assets.
    """
    if is_frozen():
        # PyInstaller onefile extracts to _MEIPASS; onedir resides next to executable
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
        return Path(sys.executable).parent.resolve()
    # Development source tree root
    return Path(__file__).resolve().parent.parent.parent


def get_app_data_dir() -> Path:
    """
    Returns the root directory for writable user state.
    Default: %LOCALAPPDATA%\\VEYRA
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        base = Path(local_appdata)
    else:
        base = Path.home() / "AppData" / "Local"
    return base / "VEYRA"


def get_data_dir() -> Path:
    """Returns directory for SQLite databases and historical records."""
    return get_app_data_dir() / "data"


def get_logs_dir() -> Path:
    """Returns directory for production logs."""
    return get_app_data_dir() / "logs"


def get_config_dir() -> Path:
    """Returns directory for user-specific configuration."""
    return get_app_data_dir() / "config"


def get_default_db_path() -> Path:
    """Returns authoritative path to production SQLite database."""
    return get_data_dir() / "history.sqlite"


def get_branding_dir() -> Path:
    """Returns path to immutable branding assets."""
    install_branding = get_installation_dir() / "assets" / "branding"
    if install_branding.exists():
        return install_branding
    # Fallback to current working directory or executable directory
    exe_branding = Path(sys.executable).parent / "assets" / "branding"
    if exe_branding.exists():
        return exe_branding
    return install_branding


def ensure_app_data_dirs() -> None:
    """Initializes required user data directories safely."""
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_logs_dir().mkdir(parents=True, exist_ok=True)
    get_config_dir().mkdir(parents=True, exist_ok=True)
