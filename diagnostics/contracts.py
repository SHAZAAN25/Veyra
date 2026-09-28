"""
VEYRA Advanced Diagnostics Contracts.
Defines strongly-typed models for diagnostic runs, test items, cross-layer root-cause graphs,
and evidence-backed diagnostic reports.
"""
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional
import uuid

from app.core.time import now_utc_iso


class DiagnosticStatus(str, Enum):
    """Lifecycle states of a diagnostic run."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class LayerStatus(str, Enum):
    """Health classification for nodes in the cross-layer diagnostic graph."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class DiagnosticLayer(str, Enum):
    """Hierarchical layers of the diagnostic topology."""
    LOCAL_PC = "LOCAL_PC"
    ADAPTER = "ADAPTER"
    WIFI = "WIFI"
    GATEWAY = "GATEWAY"
    DNS = "DNS"
    INTERNET = "INTERNET"


@dataclass
class TestItemResult:
    """Individual diagnostic probe measurement."""
    test_name: str
    target: str
    status: LayerStatus
    latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    created_at_utc: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "target": self.target,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "packet_loss_pct": self.packet_loss_pct,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "created_at_utc": self.created_at_utc,
        }


@dataclass
class GraphNode:
    """Node in the Cross-Layer Root Cause Graph."""
    node_id: str
    name: str
    layer: DiagnosticLayer
    status: LayerStatus
    details: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "layer": self.layer.value,
            "status": self.status.value,
            "details": self.details,
            "metrics": self.metrics,
            "evidence": self.evidence,
        }


@dataclass
class CrossLayerGraph:
    """Directed topological graph showing health from PC to Internet."""
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    primary_root_cause_node: Optional[str] = None
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "primary_root_cause_node": self.primary_root_cause_node,
            "summary": self.summary,
        }


@dataclass
class DiagnosticReport:
    """Complete diagnostic investigation result."""
    run_id: str
    target: str
    run_type: str
    status: DiagnosticStatus
    started_at_utc: str
    ended_at_utc: Optional[str] = None
    duration_seconds: float = 0.0
    graph: CrossLayerGraph = field(default_factory=CrossLayerGraph)
    assessment: str = ""
    confidence: float = 0.0
    affected_layers: List[str] = field(default_factory=list)
    test_results: List[TestItemResult] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    related_incident_ids: List[str] = field(default_factory=list)
    historical_context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "target": self.target,
            "run_type": self.run_type,
            "status": self.status.value,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": self.ended_at_utc,
            "duration_seconds": self.duration_seconds,
            "graph": self.graph.to_dict(),
            "assessment": self.assessment,
            "confidence": self.confidence,
            "affected_layers": self.affected_layers,
            "test_results": [t.to_dict() for t in self.test_results],
            "evidence": self.evidence,
            "recommendations": self.recommendations,
            "related_incident_ids": self.related_incident_ids,
            "historical_context": self.historical_context,
        }
