"""
VEYRA Central Intelligence & Incident Analysis Engine.
Orchestrates observation buffering, baseline updating, change detection, topology tracking,
deterministic incident evaluation, root-cause assessment, bottleneck investigation,
regression analysis, flight recording, and AI evidence packaging.
"""
from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, Any

from app.core.contracts import Observation, Assessment
from app.core.logging import get_logger
from app.core.time import now_utc_iso
from analyzer.contracts import (
    DetailedIncident,
    RootCauseAssessment,
    ChangeEvent,
    BottleneckCandidate,
    RegressionAssessment,
    AIEvidencePackage
)
from analyzer.thresholds import DetectionThresholds, get_default_thresholds
from analyzer.evidence.window import EvidenceBuffer
from analyzer.evidence.flight_recorder import FlightRecorder, FlightRecorderSnapshot
from analyzer.evidence.replay import IncidentReplayEngine, IncidentReplaySummary
from analyzer.baseline.personal_baseline import PersonalBaselineEngine
from analyzer.changes.what_changed import ChangeDetector
from analyzer.root_cause.topology import NetworkTopologyTracker
from analyzer.root_cause.evaluator import RootCauseEvaluator
from analyzer.incidents.detector import DeterministicIncidentDetector
from analyzer.bottleneck.investigator import BottleneckInvestigator
from analyzer.regression.detector import RegressionDetector
from analyzer.ai.evidence_package import AIEvidenceBuilder


@dataclass
class CycleIntelligenceReport:
    """Holistic analytical intelligence produced for a single collection cycle."""
    timestamp_utc: str
    overall_health: str  # "HEALTHY", "WARNING", "CRITICAL", "UNKNOWN"
    health_score: float  # 0 to 100
    active_incidents: List[DetailedIncident] = field(default_factory=list)
    primary_root_cause: Optional[RootCauseAssessment] = None
    topology_summary: Dict[str, str] = field(default_factory=dict)
    recent_changes: List[ChangeEvent] = field(default_factory=list)
    bottlenecks: List[BottleneckCandidate] = field(default_factory=list)
    regressions: List[RegressionAssessment] = field(default_factory=list)
    flight_snapshots: List[FlightRecorderSnapshot] = field(default_factory=list)
    ai_evidence_package: Optional[AIEvidencePackage] = None


class IntelligenceEngine:
    """
    Master analyzer transforming raw verified observations into explainable, deterministic intelligence.
    """
    def __init__(self, thresholds: Optional[DetectionThresholds] = None):
        self.logger = get_logger("analyzer.engine")
        self.thresholds = thresholds or get_default_thresholds()

        # Core intelligence components
        self.evidence_buffer = EvidenceBuffer(max_capacity=150)
        self.baseline_engine = PersonalBaselineEngine()
        self.change_detector = ChangeDetector()
        self.topology_tracker = NetworkTopologyTracker()
        self.incident_detector = DeterministicIncidentDetector(self.thresholds)
        self.root_cause_evaluator = RootCauseEvaluator(self.topology_tracker)
        self.bottleneck_investigator = BottleneckInvestigator()
        self.regression_detector = RegressionDetector(self.baseline_engine)
        self.flight_recorder = FlightRecorder()
        self.replay_engine = IncidentReplayEngine()
        self.ai_evidence_builder = AIEvidenceBuilder()

    def process_cycle(self, observations: Dict[str, Observation]) -> CycleIntelligenceReport:
        """
        Executes complete intelligence evaluation across verified observations.
        Employs strict failure isolation to ensure single-component errors never crash the engine.
        """
        # 1. Update In-Memory Buffers and Baselines
        for obs in observations.values():
            self.evidence_buffer.append(obs)
            self.baseline_engine.record_observation(obs)

        # 2. Change Detection ("What Changed?")
        changes: List[ChangeEvent] = []
        try:
            changes = self.change_detector.detect_changes(observations)
        except Exception as e:
            self.logger.error("CHANGE_DETECTION_ERROR", f"Change detector error: {e}")

        # 3. Topology State Update
        try:
            self.topology_tracker.update_topology(observations)
        except Exception as e:
            self.logger.error("TOPOLOGY_UPDATE_ERROR", f"Topology tracker error: {e}")

        # 4. Incident Detection
        active_incidents: List[DetailedIncident] = []
        try:
            active_incidents = self.incident_detector.evaluate_observations(observations)
        except Exception as e:
            self.logger.error("INCIDENT_DETECTION_ERROR", f"Incident detector error: {e}")

        # 5. Enrich Incidents with Evidence Windows, Root Cause, and Flight Recorder
        primary_root_cause: Optional[RootCauseAssessment] = None
        flight_snapshots: List[FlightRecorderSnapshot] = []

        for idx, inc in enumerate(active_incidents):
            try:
                # Attach bounded evidence window
                inc.evidence_window = self.evidence_buffer.create_evidence_window(
                    incident_observations=self.evidence_buffer.get_recent(5)
                )
                # Evaluate root cause
                rc = self.root_cause_evaluator.evaluate_incident_root_cause(inc, observations)
                inc.root_cause = rc
                if idx == 0:
                    primary_root_cause = rc

                # Generate Flight Recorder Snapshot
                snapshot = self.flight_recorder.create_snapshot(
                    snapshot_id=f"flight_{inc.incident_id}",
                    observations=observations,
                    incident=inc
                )
                flight_snapshots.append(snapshot)
            except Exception as e:
                self.logger.error("INCIDENT_ENRICHMENT_ERROR", f"Error enriching incident {inc.incident_id}: {e}")

        # 6. Bottleneck Investigation
        bottlenecks: List[BottleneckCandidate] = []
        try:
            bottlenecks = self.bottleneck_investigator.investigate(observations)
        except Exception as e:
            self.logger.error("BOTTLENECK_INVESTIGATION_ERROR", f"Bottleneck investigator error: {e}")

        # 7. Performance Regression Detection
        regressions: List[RegressionAssessment] = []
        try:
            recent_obs = self.evidence_buffer.get_recent(10)
            for m_name in ["internet_latency_rtt_ms", "internet_packet_loss_pct", "cpu_utilization_pct"]:
                reg = self.regression_detector.evaluate_regression(recent_obs, m_name)
                if reg.is_significant:
                    regressions.append(reg)
        except Exception as e:
            self.logger.error("REGRESSION_DETECTION_ERROR", f"Regression detector error: {e}")

        # 8. Compile AI Evidence Package
        ai_pkg: Optional[AIEvidencePackage] = None
        try:
            ai_pkg = self.ai_evidence_builder.build_package(
                active_incidents=active_incidents,
                root_cause=primary_root_cause,
                changes=changes,
                bottlenecks=bottlenecks,
                regressions=regressions,
                current_observations=observations
            )
        except Exception as e:
            self.logger.error("AI_EVIDENCE_BUILD_ERROR", f"AI evidence builder error: {e}")

        # 9. Compute Overall Health & Score (0 - 100)
        health_score = 100.0
        health_status = "HEALTHY"

        for inc in active_incidents:
            if inc.severity.value == "CRITICAL":
                health_score -= 40.0
            elif inc.severity.value == "HIGH":
                health_score -= 25.0
            elif inc.severity.value == "WARNING":
                health_score -= 10.0

        for _ in regressions:
            health_score -= 10.0

        for _ in bottlenecks:
            health_score -= 5.0

        health_score = max(0.0, round(health_score, 1))
        if health_score < 50.0:
            health_status = "CRITICAL"
        elif health_score < 80.0:
            health_status = "WARNING"

        return CycleIntelligenceReport(
            timestamp_utc=now_utc_iso(),
            overall_health=health_status,
            health_score=health_score,
            active_incidents=active_incidents,
            primary_root_cause=primary_root_cause,
            topology_summary=self.topology_tracker.get_topology_summary(),
            recent_changes=changes,
            bottlenecks=bottlenecks,
            regressions=regressions,
            flight_snapshots=flight_snapshots,
            ai_evidence_package=ai_pkg
        )
