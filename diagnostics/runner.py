"""
VEYRA Diagnostic Runner.
Executes non-blocking diagnostic investigations in background threads, manages run state,
cancellation signals, timeout bounds, and automatically persists results to SQLite.
"""
import json
import logging
import threading
from typing import Callable, List, Optional
import uuid

from app.core.time import now_utc_iso
from diagnostics.contracts import DiagnosticReport, DiagnosticStatus
from diagnostics.investigator import CrossLayerInvestigator
from storage.contracts import DiagnosticResultRecord, DiagnosticRunRecord
from storage.engine import StorageEngine

logger = logging.getLogger("veyra.diagnostics.runner")


class DiagnosticRunner:
    """Manages lifecycle, async execution, cancellation, and storage of diagnostic investigations."""

    def __init__(
        self,
        storage: Optional[StorageEngine] = None,
        investigator: Optional[CrossLayerInvestigator] = None
    ):
        self.storage = storage
        self.investigator = investigator or CrossLayerInvestigator()
        self._current_report: Optional[DiagnosticReport] = None
        self._status: DiagnosticStatus = DiagnosticStatus.QUEUED
        self._cancel_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def status(self) -> DiagnosticStatus:
        return self._status

    @property
    def latest_report(self) -> Optional[DiagnosticReport]:
        return self._current_report

    def is_running(self) -> bool:
        return self._status == DiagnosticStatus.RUNNING

    def cancel(self) -> None:
        """Sets the cancellation flag to cleanly abort in-flight probes."""
        self._cancel_event.set()
        logger.info("Diagnostic cancellation requested.")

    def run_sync(
        self,
        target: str = "internet",
        run_type: str = "FULL_SYSTEM_AND_NETWORK",
        timeout_seconds: float = 15.0,
        historical_incidents: Optional[List] = None
    ) -> DiagnosticReport:
        """Executes diagnostic synchronously (useful for tests or CLI)."""
        with self._lock:
            self._cancel_event.clear()
            self._status = DiagnosticStatus.RUNNING

        try:
            report = self.investigator.run_investigation(
                target=target,
                run_type=run_type,
                timeout_seconds=timeout_seconds,
                cancel_event=self._cancel_event,
                historical_incidents=historical_incidents
            )
            self._current_report = report
            self._status = report.status
            self._persist_report(report)
            return report
        except Exception as e:
            logger.error(f"Diagnostic run failed: {e}")
            self._status = DiagnosticStatus.FAILED
            raise

    def start_async(
        self,
        target: str = "internet",
        run_type: str = "FULL_SYSTEM_AND_NETWORK",
        timeout_seconds: float = 15.0,
        on_complete: Optional[Callable[[DiagnosticReport], None]] = None,
        historical_incidents: Optional[List] = None
    ) -> None:
        """Launches diagnostic investigation on a daemon background worker thread."""
        with self._lock:
            if self._status == DiagnosticStatus.RUNNING:
                logger.warning("Diagnostic investigation already running. Ignoring duplicate start.")
                return
            self._cancel_event.clear()
            self._status = DiagnosticStatus.RUNNING

        def _worker():
            try:
                report = self.investigator.run_investigation(
                    target=target,
                    run_type=run_type,
                    timeout_seconds=timeout_seconds,
                    cancel_event=self._cancel_event,
                    historical_incidents=historical_incidents
                )
                self._current_report = report
                self._status = report.status
                self._persist_report(report)
                if on_complete:
                    on_complete(report)
            except Exception as e:
                logger.error(f"Background diagnostic execution failed: {e}")
                self._status = DiagnosticStatus.FAILED

        self._worker_thread = threading.Thread(target=_worker, daemon=True, name="VeyraDiagnosticWorker")
        self._worker_thread.start()

    def _persist_report(self, report: DiagnosticReport) -> None:
        """Writes DiagnosticRunRecord and DiagnosticResultRecords into storage safely."""
        if not self.storage:
            return

        try:
            run_rec = DiagnosticRunRecord(
                run_id=report.run_id,
                target=report.target,
                run_type=report.run_type,
                status=report.status.value,
                started_at_utc=report.started_at_utc,
                ended_at_utc=report.ended_at_utc,
                duration_seconds=report.duration_seconds,
                assessment=report.assessment,
                confidence=report.confidence,
                evidence_json=json.dumps(report.evidence),
                affected_layers_json=json.dumps(report.affected_layers),
                recommendations_json=json.dumps(report.recommendations),
            )
            self.storage.save_diagnostic_run(run_rec)

            for item in report.test_results:
                res_rec = DiagnosticResultRecord(
                    result_id=f"res_{uuid.uuid4().hex[:12]}",
                    run_id=report.run_id,
                    test_name=item.test_name,
                    target=item.target,
                    status=item.status.value,
                    latency_ms=item.latency_ms,
                    packet_loss_pct=item.packet_loss_pct,
                    details_json=json.dumps(item.details),
                    created_at_utc=item.created_at_utc,
                )
                self.storage.save_diagnostic_result(res_rec)
        except Exception as e:
            logger.error(f"Failed to persist diagnostic report to storage: {e}")
