"""
VEYRA Entry Point — Stage 4 Professional UI & Localhost API.
Validates environment, branding integrity, initializes local SQLite storage,
collector coordinator, intelligence engine, and launches either the Desktop GUI or headless daemon.
"""
import sys
import argparse
import tkinter as tk
from pathlib import Path

# Ensure project root is in sys.path
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.core.branding import verify_branding_manifest
from app.core.config import load_default_config
from app.core.logging import get_logger
from app.core.paths import get_default_db_path, is_frozen, ensure_app_data_dirs
from storage.engine import StorageEngine
from collectors.coordinator import CollectionCoordinator
from analyzer.engine import IntelligenceEngine
from app.api.routes import ApiRouteDispatcher
from app.api.server import LocalApiServer
from app.ui.app import VeyraDesktopApp
from app.ui.theme import ThemeManager
from app.ui.state import UiStateManager

logger = get_logger("entrypoint")


def main():
    parser = argparse.ArgumentParser(description="VEYRA — PC Observability & Incident Intelligence")
    parser.add_argument("--headless", action="store_true", help="Run background collection & API server without Desktop UI")
    parser.add_argument("--api-port", type=int, default=8765, help="Port for localhost API server")
    parser.add_argument("--db-path", type=str, default=None, help="Path to SQLite database file")
    args = parser.parse_args()

    logger.info("STARTUP", "Initializing VEYRA Desktop & Observability Engine...")

    # 1. Branding Integrity Lock Verification
    print("\n==================================================")
    print("VEYRA -- PC OBSERVABILITY & INCIDENT INTELLIGENCE")
    print("==================================================")
    
    branding_report = verify_branding_manifest()
    print(branding_report.print_summary())
    if not branding_report.is_valid:
        logger.critical("BRANDING_INTEGRITY_FAILURE", "Locked branding asset verification failed!")
        sys.exit(1)

    # 2. Configuration & Security Boundary Verification
    try:
        config = load_default_config()
        config.app.api_port = args.api_port
        logger.info("CONFIG_LOADED", f"Configuration verified. Local binding: 127.0.0.1:{args.api_port}")
        print(f"Configuration: VALID (Localhost binding: 127.0.0.1:{args.api_port})")
    except Exception as e:
        logger.critical("CONFIG_ERROR", f"Configuration validation failed: {e}")
        print(f"Configuration Error: {e}")
        sys.exit(1)

    # 3. Initialize Storage & Observability Subsystems
    if args.db_path:
        db_path = Path(args.db_path)
    elif is_frozen():
        ensure_app_data_dirs()
        db_path = get_default_db_path()
    else:
        db_path = Path("data") / "veyra_local.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    storage = StorageEngine(db_path)
    coordinator = CollectionCoordinator()
    intelligence_engine = IntelligenceEngine()
    theme_mgr = ThemeManager()
    state_mgr = UiStateManager(storage)

    # 4. Launch Localhost API Server (Daemon)
    dispatcher = ApiRouteDispatcher(
        config=config,
        storage=storage,
        latest_observation_fn=lambda: state_mgr.latest_observation,
        latest_assessment_fn=lambda: state_mgr.latest_assessment
    )
    api_server = LocalApiServer(
        config=config,
        dispatcher=dispatcher
    )
    api_server.start()
    print(f"Localhost API: Active at http://127.0.0.1:{args.api_port}/api/v1/status")

    if args.headless:
        print("Running in headless daemon mode. Press Ctrl+C to terminate.")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down VEYRA daemon...")
            api_server.stop()
            sys.exit(0)

    # 5. Launch Tkinter Desktop Application
    try:
        root = tk.Tk()

        # Wire up initial telemetry sample
        initial_cycle = coordinator.run_cycle()
        initial_report = intelligence_engine.process_cycle(initial_cycle)
        primary_obs = initial_cycle.get("cpu") or (next(iter(initial_cycle.values())) if initial_cycle else None)
        state_mgr.update_telemetry(
            observation=primary_obs,
            active_incidents=initial_report.active_incidents,
            recent_changes=initial_report.recent_changes
        )

        app = VeyraDesktopApp(
            root=root,
            storage=storage,
            coordinator=coordinator,
            intelligence_engine=intelligence_engine,
            theme_manager=theme_mgr,
            state_manager=state_mgr
        )

        def _on_close():
            api_server.stop()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", _on_close)
        print("Desktop UI: Launched. Entering main event loop.\n")
        root.mainloop()

    except Exception as e:
        logger.critical("DESKTOP_UI_ERROR", f"Failed to start desktop application: {e}")
        api_server.stop()
        raise


if __name__ == "__main__":
    main()
