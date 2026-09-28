"""
VEYRA Minimal Background Supervisor.
Stage 8 Packaging & Process Reliability.

Provides user-space process supervision with bounded restart behavior,
preventing crash storms, infinite loops, and resource leaks without requiring
Windows Service elevation or administrator privileges.
"""
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.core.paths import get_logs_dir

logger = logging.getLogger("veyra.supervisor")


@dataclass
class SupervisorConfig:
    """Bounded supervisor parameters."""
    max_restarts: int = 5
    restart_window_seconds: float = 60.0
    restart_delay_seconds: float = 2.0
    heartbeat_interval_seconds: float = 1.0


class ProcessSupervisor:
    """
    Supervises a target VEYRA worker process under least-privilege user-space semantics.
    Enforces restart rate-limiting and clean lifecycle management.
    """

    def __init__(self, target_cmd: List[str], config: Optional[SupervisorConfig] = None) -> None:
        self.target_cmd = target_cmd
        self.config = config or SupervisorConfig()
        self.restart_timestamps: List[float] = []
        self._process: Optional[subprocess.Popen] = None
        self._stop_requested = False

    def is_looping(self) -> bool:
        """Determines if the process is crashing too frequently (restart storm)."""
        now = time.monotonic()
        # Keep only timestamps within the rolling window
        self.restart_timestamps = [
            t for t in self.restart_timestamps
            if now - t <= self.config.restart_window_seconds
        ]
        return len(self.restart_timestamps) >= self.config.max_restarts

    def start_process(self) -> subprocess.Popen:
        """Spawns the child process safely without shell execution."""
        self.restart_timestamps.append(time.monotonic())
        logger.info(f"Supervisor spawning: {' '.join(self.target_cmd)}")
        self._process = subprocess.Popen(
            self.target_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False
        )
        return self._process

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Requests graceful shutdown of the child process."""
        self._stop_requested = True
        if self._process and self._process.poll() is None:
            logger.info("Supervisor terminating child process...")
            self._process.terminate()
            try:
                self._process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                logger.warning("Child process did not exit in time; killing.")
                self._process.kill()
                self._process.wait()

    def run_single_check(self) -> Optional[int]:
        """
        Polls child process state once. Returns exit code if terminated, or None if still running.
        If terminated unexpectedly and not looping, restarts the child.
        """
        if self._process is None:
            if not self._stop_requested and not self.is_looping():
                self.start_process()
            return None

        exit_code = self._process.poll()
        if exit_code is not None:
            logger.info(f"Supervised child exited with code {exit_code}")
            if not self._stop_requested:
                if self.is_looping():
                    logger.critical(
                        f"Restart storm detected: {len(self.restart_timestamps)} restarts in "
                        f"{self.config.restart_window_seconds}s. Aborting supervisor to prevent thrashing."
                    )
                    return exit_code
                time.sleep(self.config.restart_delay_seconds)
                self.start_process()
            return exit_code
        return None
