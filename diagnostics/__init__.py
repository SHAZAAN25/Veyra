"""
VEYRA Diagnostics Subsystem.
Defines contracts and implementation for explicit, on-demand diagnostic operations,
cross-layer root-cause graphs, and failure-isolated diagnostic execution.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional

from diagnostics.contracts import (
    CrossLayerGraph,
    DiagnosticLayer,
    DiagnosticReport,
    DiagnosticStatus,
    GraphNode,
    LayerStatus,
    TestItemResult,
)
from diagnostics.investigator import CrossLayerInvestigator
from diagnostics.runner import DiagnosticRunner


@dataclass
class DiagnosticResult:
    diagnostic_name: str
    target: str
    is_successful: bool
    execution_duration_ms: float
    output_summary: str
    raw_details: Dict[str, Any]
    error_message: Optional[str] = None


class BaseDiagnosticTool(ABC):
    """Abstract base class for active diagnostic tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def execute(self, target: str, timeout_seconds: float = 15.0) -> DiagnosticResult:
        """Executes the diagnostic action against the target with strict timeout bounds."""
        pass


__all__ = [
    "DiagnosticResult",
    "BaseDiagnosticTool",
    "DiagnosticStatus",
    "LayerStatus",
    "DiagnosticLayer",
    "TestItemResult",
    "GraphNode",
    "CrossLayerGraph",
    "DiagnosticReport",
    "CrossLayerInvestigator",
    "DiagnosticRunner",
]
