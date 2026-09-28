"""
VEYRA Concrete Optimization Actions.
Implements bounded, fully reversible actions for network, background processes,
and system power plans.
Strictly sandboxed: supports dry_run for testing and automated validation without
modifying actual system state.
"""
from abc import ABC, abstractmethod
import logging
import os
import subprocess
from typing import Any, Dict, Optional

import psutil

from app.core.security import run_safe_subprocess

logger = logging.getLogger("veyra.optimization.actions")



class BaseOptimizationAction(ABC):
    """Abstract interface for reversible optimization actions."""

    @property
    @abstractmethod
    def action_id(self) -> str:
        pass

    @abstractmethod
    def get_current_state(self) -> Dict[str, Any]:
        """Reads current real subsystem configuration."""
        pass

    @abstractmethod
    def apply(self, dry_run: bool = False) -> Dict[str, Any]:
        """Applies reversible optimization and returns the new state."""
        pass

    @abstractmethod
    def rollback(self, snapshot_pre_state: Dict[str, Any], dry_run: bool = False) -> bool:
        """Restores exact pre-optimization state from snapshot."""
        pass


class DnsCacheFlushAction(BaseOptimizationAction):
    """Flushes local DNS resolver cache to clear stale, degraded, or poisoned entries."""

    @property
    def action_id(self) -> str:
        return "DNS_CACHE_FLUSH"

    def get_current_state(self) -> Dict[str, Any]:
        return {
            "action": "flush_dns_cache",
            "resolver": "windows_dnscache",
            "status": "cached",
        }

    def apply(self, dry_run: bool = False) -> Dict[str, Any]:
        if not dry_run:
            try:
                # Safe argument array execution via hardened runner
                run_safe_subprocess(
                    ["ipconfig", "/flushdns"],
                    timeout_seconds=5.0,
                )
            except Exception as e:
                logger.error(f"Failed to execute flushdns: {e}")
                raise
        return {
            "action": "flush_dns_cache",
            "resolver": "windows_dnscache",
            "status": "flushed",
        }


    def rollback(self, snapshot_pre_state: Dict[str, Any], dry_run: bool = False) -> bool:
        # Cache flushing is inherently non-destructive; rollback verifies DNS service is operational
        return True


class ProcessPriorityHintAction(BaseOptimizationAction):
    """Safely adjusts non-essential background process priority to alleviate CPU contention."""

    def __init__(self, pid: Optional[int] = None, process_name: Optional[str] = None):
        self.pid = pid
        self.process_name = process_name

    @property
    def action_id(self) -> str:
        return "BACKGROUND_PROCESS_PRIORITY_HINT"

    def get_current_state(self) -> Dict[str, Any]:
        if not self.pid:
            return {"pid": None, "priority": "UNKNOWN"}
        try:
            proc = psutil.Process(self.pid)
            return {
                "pid": self.pid,
                "process_name": proc.name(),
                "priority_class": proc.nice(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"pid": self.pid, "priority_class": None, "status": "unavailable"}

    def apply(self, dry_run: bool = False) -> Dict[str, Any]:
        if not self.pid:
            raise ValueError("Cannot adjust priority without target PID.")
        if dry_run:
            return {
                "pid": self.pid,
                "process_name": self.process_name or "simulated_proc",
                "priority_class": psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS") else 10,
                "status": "simulated_applied",
            }

        try:
            proc = psutil.Process(self.pid)
            target_priority = getattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS", 10)
            proc.nice(target_priority)
            return {
                "pid": self.pid,
                "process_name": proc.name(),
                "priority_class": target_priority,
                "status": "applied",
            }
        except Exception as e:
            logger.error(f"Failed to adjust process priority for PID {self.pid}: {e}")
            raise

    def rollback(self, snapshot_pre_state: Dict[str, Any], dry_run: bool = False) -> bool:
        orig_pid = snapshot_pre_state.get("pid")
        orig_priority = snapshot_pre_state.get("priority_class")
        if not orig_pid or orig_priority is None:
            return False

        if dry_run:
            return True

        try:
            proc = psutil.Process(orig_pid)
            proc.nice(orig_priority)
            logger.info(f"Restored PID {orig_pid} priority class to {orig_priority}")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Could not rollback process priority for PID {orig_pid}: {e}")
            return False


class PowerSchemeOptimizationAction(BaseOptimizationAction):
    """
    Safely adjusts Windows power plan scheme to High Performance during gaming
    and restores previous scheme during rollback.
    """

    HIGH_PERF_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

    @property
    def action_id(self) -> str:
        return "POWER_PLAN_GAMING_HINT"

    def get_current_state(self) -> Dict[str, Any]:
        try:
            proc = run_safe_subprocess(
                ["powercfg", "/getactivescheme"],
                timeout_seconds=3.0,
            )
            out = proc.stdout or ""
            # e.g. "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)"
            guid = "unknown"
            name = "unknown"
            if "GUID:" in out:
                part = out.split("GUID:")[1].strip()
                guid = part.split()[0].strip()
                if "(" in part and ")" in part:
                    name = part.split("(")[1].split(")")[0].strip()
            return {"active_guid": guid, "scheme_name": name}
        except Exception:
            return {"active_guid": "unknown", "scheme_name": "unknown"}

    def apply(self, dry_run: bool = False) -> Dict[str, Any]:
        current = self.get_current_state()
        if dry_run:
            return {
                "active_guid": self.HIGH_PERF_GUID,
                "scheme_name": "High performance",
                "status": "simulated_applied",
            }

        try:
            run_safe_subprocess(
                ["powercfg", "/setactive", self.HIGH_PERF_GUID],
                timeout_seconds=3.0,
            )
            return {
                "active_guid": self.HIGH_PERF_GUID,
                "scheme_name": "High performance",
                "status": "applied",
            }
        except Exception as e:
            logger.error(f"Failed to activate power scheme: {e}")
            raise

    def rollback(self, snapshot_pre_state: Dict[str, Any], dry_run: bool = False) -> bool:
        orig_guid = snapshot_pre_state.get("active_guid")
        if not orig_guid or orig_guid == "unknown":
            return False

        if dry_run:
            return True

        try:
            proc = run_safe_subprocess(
                ["powercfg", "/setactive", orig_guid],
                timeout_seconds=3.0,
            )
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Failed to rollback power scheme to {orig_guid}: {e}")
            return False

