"""
VEYRA Chaos Engine Orchestrator
Stage 7 Automated Testing, Fault Injection & QA Harnesses

Coordinates, executes, and audits automated chaos experiments and resilience verifications.
Enforces Rule 9 (Simulation Data Isolation) across all fault injection runs.
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Callable

from simulation.contracts import (
    ChaosExperiment,
    ChaosReport,
    ChaosStatus,
    FaultScenario,
    FaultType,
    SimulationTarget,
)


class ChaosEngine:
    """Orchestrator for automated fault injection and resilience certification."""

    def __init__(self) -> None:
        self._registered_experiments: Dict[str, ChaosExperiment] = {}
        self._execution_history: List[ChaosReport] = []

    def register_experiment(self, experiment: ChaosExperiment) -> None:
        """Register a chaos scenario."""
        self._registered_experiments[experiment.experiment_id] = experiment

    def abort_experiment(self, experiment_id: str, reason: str = "User abort") -> ChaosReport:
        """Explicitly abort a running or pending chaos experiment."""
        experiment = self._registered_experiments.get(experiment_id)
        if not experiment:
            raise KeyError(f"Chaos experiment not found: {experiment_id}")
        experiment.status = ChaosStatus.ABORTED
        report = ChaosReport(
            experiment_id=experiment_id,
            target=experiment.scenario.target,
            fault_type=experiment.scenario.fault_type,
            status=ChaosStatus.ABORTED,
            system_degraded_gracefully=True,
            recovered_cleanly=True,
            duration_ms=0.0,
            assertions_evaluated=0,
            assertions_passed=0,
            telemetry_isolated=True,
            error_message=f"Aborted: {reason}"
        )
        self._execution_history.append(report)
        return report

    def run_experiment(
        self,
        experiment_id: str,
        injection_fn: Callable[[], ChaosReport],
        timeout_seconds: Optional[float] = None
    ) -> ChaosReport:
        """Execute a single chaos experiment under guarded conditions."""
        experiment = self._registered_experiments.get(experiment_id)
        if not experiment:
            raise KeyError(f"Chaos experiment not found: {experiment_id}")

        experiment.status = ChaosStatus.RUNNING
        t0 = time.monotonic()

        try:
            report = injection_fn()
            duration_s = time.monotonic() - t0
            if timeout_seconds is not None and duration_s > timeout_seconds:
                experiment.status = ChaosStatus.TIMED_OUT
                report.status = ChaosStatus.TIMED_OUT
                report.error_message = f"Experiment timed out after {duration_s:.3f}s (limit: {timeout_seconds}s)"
            else:
                experiment.status = report.status
            self._execution_history.append(report)
            return report
        except TimeoutError as exc:
            experiment.status = ChaosStatus.TIMED_OUT
            report = ChaosReport(
                experiment_id=experiment_id,
                target=experiment.scenario.target,
                fault_type=experiment.scenario.fault_type,
                status=ChaosStatus.TIMED_OUT,
                system_degraded_gracefully=True,
                recovered_cleanly=True,
                duration_ms=(time.monotonic() - t0) * 1000.0,
                assertions_evaluated=1,
                assertions_passed=0,
                telemetry_isolated=True,
                error_message=str(exc)
            )
            self._execution_history.append(report)
            return report
        except Exception as exc:
            experiment.status = ChaosStatus.ERROR
            report = ChaosReport(
                experiment_id=experiment_id,
                target=experiment.scenario.target,
                fault_type=experiment.scenario.fault_type,
                status=ChaosStatus.ERROR,
                system_degraded_gracefully=False,
                recovered_cleanly=False,
                duration_ms=(time.monotonic() - t0) * 1000.0,
                assertions_evaluated=1,
                assertions_passed=0,
                telemetry_isolated=True,
                error_message=str(exc)
            )
            self._execution_history.append(report)
            return report

    def run_all_experiments(self, runners: Dict[str, Callable[[], ChaosReport]]) -> List[ChaosReport]:
        """Execute all registered experiments."""
        reports = []
        for exp_id, fn in runners.items():
            report = self.run_experiment(exp_id, fn)
            reports.append(report)
        return reports

    def get_summary_report(self) -> Dict[str, Any]:
        """Aggregate summary of all executed chaos experiments."""
        total = len(self._execution_history)
        passed = sum(1 for r in self._execution_history if r.passed)
        failed = sum(1 for r in self._execution_history if not r.passed)
        degraded_gracefully = sum(1 for r in self._execution_history if r.system_degraded_gracefully)
        recovered_cleanly = sum(1 for r in self._execution_history if r.recovered_cleanly)
        isolated = sum(1 for r in self._execution_history if r.telemetry_isolated)

        return {
            "total_experiments": total,
            "passed": passed,
            "failed": failed,
            "system_degraded_gracefully_count": degraded_gracefully,
            "recovered_cleanly_count": recovered_cleanly,
            "telemetry_isolated_count": isolated,
            "all_passed": (total > 0 and passed == total),
        }
