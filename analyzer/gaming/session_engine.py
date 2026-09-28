"""
VEYRA Gaming Session Engine & DNA Analysis.
Manages session lifecycles, collects genuine continuous session observations,
calculates deterministic Gaming Session DNA, and performs session comparisons.
"""
from collections import deque
import json
import logging
import time
from typing import Any, Dict, List, Optional
import uuid

from analyzer.contracts import DetailedIncident
from analyzer.gaming.contracts import (
    GameIdentity,
    GamingComparisonResult,
    GamingSession,
    GamingSessionDNA,
    GamingSessionState,
    NetworkStabilityRating,
    SessionPerformanceCharacteristic,
    SystemPressureRating,
)
from analyzer.gaming.detector import GameDetector
from app.core.contracts import MetricState, Observation
from app.core.time import now_utc_iso
from storage.contracts import GamingSessionRecord
from storage.engine import StorageEngine

logger = logging.getLogger("veyra.analyzer.gaming.session_engine")


class GamingSessionEngine:
    """Orchestrates gaming session lifecycle, telemetry buffering, and DNA generation."""

    def __init__(
        self,
        storage: Optional[StorageEngine] = None,
        detector: Optional[GameDetector] = None,
        max_buffer_samples: int = 7200  # Up to 2-3 hours at 1-1.5s interval
    ):
        self.storage = storage
        self.detector = detector or GameDetector()
        self.max_buffer_samples = max_buffer_samples

        self._active_session: Optional[GamingSession] = None
        self._samples: deque[Dict[str, Any]] = deque(maxlen=max_buffer_samples)
        self._session_incidents: List[str] = []
        self._bottlenecks_detected: set[str] = set()
        self._t0_perf: float = 0.0

    @property
    def active_session(self) -> Optional[GamingSession]:
        return self._active_session

    @property
    def is_session_active(self) -> bool:
        return self._active_session is not None and self._active_session.state == GamingSessionState.ACTIVE

    def start_session(self, game: Optional[GameIdentity] = None) -> GamingSession:
        """Starts a new gaming session in ACTIVE state."""
        if self._active_session and self._active_session.state == GamingSessionState.ACTIVE:
            logger.warning("Active gaming session already underway. Ending previous session as interrupted.")
            self.interrupt_session()

        detected_game = game or self.detector.detect_active_game()
        session_id = f"gsess_{uuid.uuid4().hex[:12]}"
        now_utc = now_utc_iso()
        self._t0_perf = time.perf_counter()

        self._active_session = GamingSession(
            session_id=session_id,
            game=detected_game,
            state=GamingSessionState.ACTIVE,
            started_at_utc=now_utc,
            fps_telemetry=None,  # Explicitly None unless genuine frame-rate collector exists
        )
        self._samples.clear()
        self._session_incidents.clear()
        self._bottlenecks_detected.clear()

        logger.info(f"Gaming session started: {detected_game.name} [{session_id}]")
        return self._active_session

    def record_observation(
        self,
        observation: Observation,
        active_incidents: Optional[List[DetailedIncident]] = None,
        active_bottlenecks: Optional[List[str]] = None
    ) -> None:
        """Buffers real telemetry measurements into the active gaming session."""
        if not self.is_session_active or not self._active_session:
            return

        def get_val(metric_name: str) -> Optional[float]:
            m = observation.get_metric(metric_name)
            if m and m.state == MetricState.AVAILABLE and isinstance(m.value, (int, float)):
                return float(m.value)
            return None

        sample: Dict[str, Any] = {
            "timestamp": time.time(),
            "cpu_pct": get_val("cpu_utilization_pct"),
            "gpu_pct": get_val("gpu_utilization_pct"),
            "ram_pct": get_val("ram_utilization_pct"),
            "vram_pct": get_val("gpu_memory_utilization_pct"),
            "latency_ms": get_val("internet_latency_ms"),
            "packet_loss_pct": get_val("internet_packet_loss_pct"),
        }
        self._samples.append(sample)

        # Track incidents occurred during this session
        if active_incidents:
            for inc in active_incidents:
                itype = inc.incident_type.value if hasattr(inc.incident_type, "value") else str(inc.incident_type)
                if itype not in self._session_incidents:
                    self._session_incidents.append(itype)

        # Track bottleneck candidates
        if active_bottlenecks:
            for b in active_bottlenecks:
                self._bottlenecks_detected.add(str(b))

    def end_session(self, status: GamingSessionState = GamingSessionState.COMPLETED) -> Optional[GamingSession]:
        """Finalizes the active session, computes Gaming Session DNA, and persists to storage."""
        if not self._active_session:
            return None

        now_utc = now_utc_iso()
        duration = round(time.perf_counter() - self._t0_perf, 2)
        self._active_session.ended_at_utc = now_utc
        self._active_session.duration_seconds = duration
        self._active_session.state = status

        # Compute metric aggregates
        cpu_samples = [s["cpu_pct"] for s in self._samples if s.get("cpu_pct") is not None]
        gpu_samples = [s["gpu_pct"] for s in self._samples if s.get("gpu_pct") is not None]
        ram_samples = [s["ram_pct"] for s in self._samples if s.get("ram_pct") is not None]
        vram_samples = [s["vram_pct"] for s in self._samples if s.get("vram_pct") is not None]
        lat_samples = [s["latency_ms"] for s in self._samples if s.get("latency_ms") is not None]
        loss_samples = [s["packet_loss_pct"] for s in self._samples if s.get("packet_loss_pct") is not None]

        self._active_session.avg_cpu_pct = round(sum(cpu_samples) / len(cpu_samples), 1) if cpu_samples else None
        self._active_session.avg_gpu_pct = round(sum(gpu_samples) / len(gpu_samples), 1) if gpu_samples else None
        self._active_session.avg_ram_pct = round(sum(ram_samples) / len(ram_samples), 1) if ram_samples else None
        self._active_session.avg_vram_pct = round(sum(vram_samples) / len(vram_samples), 1) if vram_samples else None
        self._active_session.avg_latency_ms = round(sum(lat_samples) / len(lat_samples), 1) if lat_samples else None
        self._active_session.packet_loss_pct = round(sum(loss_samples) / len(loss_samples), 2) if loss_samples else None
        self._active_session.incident_count = len(self._session_incidents)
        self._active_session.bottleneck_candidates = sorted(list(self._bottlenecks_detected))

        # Compute Gaming Session DNA
        dna = self._calculate_session_dna(
            cpu_samples=cpu_samples,
            gpu_samples=gpu_samples,
            ram_samples=ram_samples,
            lat_samples=lat_samples,
            loss_samples=loss_samples,
            incidents=self._session_incidents,
            bottlenecks=self._active_session.bottleneck_candidates,
            sample_count=len(self._samples),
        )
        self._active_session.session_dna = dna

        # Persist session
        self._persist_session(self._active_session)

        completed_session = self._active_session
        self._active_session = None
        return completed_session

    def interrupt_session(self) -> Optional[GamingSession]:
        """Marks the active session as INTERRUPTED due to system restart or sleep."""
        return self.end_session(status=GamingSessionState.INTERRUPTED)

    def _calculate_session_dna(
        self,
        cpu_samples: List[float],
        gpu_samples: List[float],
        ram_samples: List[float],
        lat_samples: List[float],
        loss_samples: List[float],
        incidents: List[str],
        bottlenecks: List[str],
        sample_count: int,
    ) -> GamingSessionDNA:
        """Deterministic mathematical calculation of Gaming Session DNA."""
        stability_score = 100.0

        avg_loss = sum(loss_samples) / len(loss_samples) if loss_samples else 0.0
        stability_score -= min(35.0, avg_loss * 5.0)

        # Latency volatility penalty
        if len(lat_samples) >= 5:
            diffs = [abs(lat_samples[i] - lat_samples[i - 1]) for i in range(1, len(lat_samples))]
            jitter = sum(diffs) / len(diffs)
            if jitter > 20.0:
                stability_score -= 15.0
            elif jitter > 10.0:
                stability_score -= 8.0

        # Incidents penalty
        stability_score -= min(40.0, len(incidents) * 10.0)

        # Resource saturation penalty
        if ram_samples and max(ram_samples) >= 92.0:
            stability_score -= 10.0
        if cpu_samples and (sum(cpu_samples) / len(cpu_samples)) >= 90.0:
            stability_score -= 10.0

        stability_score = round(max(0.0, min(100.0, stability_score)), 1)

        # Network Stability Rating
        if avg_loss > 2.0:
            net_rating = NetworkStabilityRating.DEGRADED
        elif avg_loss > 0.0 or (lat_samples and max(lat_samples) - min(lat_samples) > 50.0):
            net_rating = NetworkStabilityRating.VOLATILE
        elif lat_samples and (sum(lat_samples) / len(lat_samples)) < 40.0:
            net_rating = NetworkStabilityRating.EXCELLENT
        else:
            net_rating = NetworkStabilityRating.GOOD

        # System Pressure Rating
        avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
        avg_ram = sum(ram_samples) / len(ram_samples) if ram_samples else 0.0
        if avg_cpu >= 90.0 or avg_ram >= 92.0:
            sys_rating = SystemPressureRating.SATURATED
        elif avg_cpu >= 75.0 or avg_ram >= 80.0:
            sys_rating = SystemPressureRating.ELEVATED
        else:
            sys_rating = SystemPressureRating.NOMINAL

        # Performance Characteristic
        avg_gpu = sum(gpu_samples) / len(gpu_samples) if gpu_samples else None
        if avg_gpu is not None and avg_gpu >= 90.0 and avg_cpu < 65.0:
            char = SessionPerformanceCharacteristic.GPU_BOUND
        elif avg_cpu >= 85.0 and (avg_gpu is None or avg_gpu < 55.0):
            char = SessionPerformanceCharacteristic.CPU_BOUND
        elif net_rating in (NetworkStabilityRating.VOLATILE, NetworkStabilityRating.DEGRADED):
            char = SessionPerformanceCharacteristic.NETWORK_VOLATILE
        elif avg_ram >= 90.0:
            char = SessionPerformanceCharacteristic.MEMORY_CONSTRAINED
        elif stability_score >= 85.0:
            char = SessionPerformanceCharacteristic.STABLE
        else:
            char = SessionPerformanceCharacteristic.BALANCED

        summary = (
            f"Stability score {stability_score}/100. System pressure was {sys_rating.value.lower()}, "
            f"network was {net_rating.value.lower()}, dominant characteristic: {char.value}."
        )

        return GamingSessionDNA(
            stability_score=stability_score,
            performance_characteristic=char,
            network_stability=net_rating,
            system_pressure=sys_rating,
            bottlenecks_detected=bottlenecks,
            incident_types=incidents,
            sample_count=sample_count,
            summary=summary,
        )

    def compare_sessions(
        self,
        session_a: GamingSession,
        session_b: GamingSession
    ) -> GamingComparisonResult:
        """Compares two gaming sessions. Only compares compatible sessions."""
        # Compatibility check: if both sessions have identified games and they differ, note incompatibility
        if (
            session_a.game.name != "Unknown"
            and session_b.game.name != "Unknown"
            and session_a.game.name.lower() != session_b.game.name.lower()
        ):
            return GamingComparisonResult(
                session_a_id=session_a.session_id,
                session_b_id=session_b.session_id,
                metric_comparisons={},
                stability_change=0.0,
                summary=f"Incompatible sessions: {session_a.game.name} cannot be directly compared against {session_b.game.name}.",
                compatible=False,
                incompatibility_reason=f"Different games: '{session_a.game.name}' vs '{session_b.game.name}'",
            )

        metrics: Dict[str, Dict[str, Any]] = {}

        def comp_metric(name: str, val_a: Optional[float], val_b: Optional[float]):
            if val_a is not None and val_b is not None:
                diff = round(val_b - val_a, 2)
                pct_change = round((diff / val_a) * 100.0, 1) if val_a != 0.0 else 0.0
                metrics[name] = {
                    "session_a": val_a,
                    "session_b": val_b,
                    "difference": diff,
                    "percentage_change": pct_change,
                }

        comp_metric("avg_cpu_pct", session_a.avg_cpu_pct, session_b.avg_cpu_pct)
        comp_metric("avg_gpu_pct", session_a.avg_gpu_pct, session_b.avg_gpu_pct)
        comp_metric("avg_ram_pct", session_a.avg_ram_pct, session_b.avg_ram_pct)
        comp_metric("avg_latency_ms", session_a.avg_latency_ms, session_b.avg_latency_ms)
        comp_metric("packet_loss_pct", session_a.packet_loss_pct, session_b.packet_loss_pct)

        score_a = session_a.session_dna.stability_score if session_a.session_dna else 0.0
        score_b = session_b.session_dna.stability_score if session_b.session_dna else 0.0
        stab_diff = round(score_b - score_a, 1)

        if stab_diff > 5.0:
            summary = f"Session B improved in stability (+{stab_diff} points) compared to Session A."
        elif stab_diff < -5.0:
            summary = f"Session B degraded in stability ({stab_diff} points) compared to Session A."
        else:
            summary = f"Session B showed comparable stability ({stab_diff:+0.1f} points) to Session A."

        return GamingComparisonResult(
            session_a_id=session_a.session_id,
            session_b_id=session_b.session_id,
            metric_comparisons=metrics,
            stability_change=stab_diff,
            summary=summary,
            compatible=True,
        )

    def _persist_session(self, session: GamingSession) -> None:
        """Persists the session record into SQLite storage."""
        if not self.storage:
            return

        try:
            rec = GamingSessionRecord(
                session_id=session.session_id,
                game_name=session.game.name,
                executable=session.game.executable or "",
                process_id=session.game.process_id,
                status=session.state.value,
                started_at_utc=session.started_at_utc,
                ended_at_utc=session.ended_at_utc,
                duration_seconds=session.duration_seconds,
                fps_available=session.fps_telemetry is not None,
                avg_cpu_pct=session.avg_cpu_pct,
                avg_gpu_pct=session.avg_gpu_pct,
                avg_ram_pct=session.avg_ram_pct,
                avg_vram_pct=session.avg_vram_pct,
                avg_latency_ms=session.avg_latency_ms,
                packet_loss_pct=session.packet_loss_pct,
                incident_count=session.incident_count,
                bottleneck_candidates_json=json.dumps(session.bottleneck_candidates),
                session_dna_json=json.dumps(session.session_dna.to_dict()) if session.session_dna else "{}",
            )
            self.storage.save_gaming_session(rec)
        except Exception as e:
            logger.error(f"Failed to persist gaming session: {e}")
