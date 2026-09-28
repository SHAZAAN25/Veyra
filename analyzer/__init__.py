"""
VEYRA Analyzer Interfaces.
Establishes the contract for observation analysis, health scoring, and incident detection.
Analyzers operate strictly on verified observations from collectors.
"""
from abc import ABC, abstractmethod
from typing import List

from app.core.contracts import Observation, Assessment, Incident


class BaseAnalyzer(ABC):
    """Abstract base class for all VEYRA analyzers."""

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain analyzed (e.g. 'network', 'system', 'gaming')."""
        pass

    @abstractmethod
    def evaluate(self, observations: List[Observation]) -> Assessment:
        """Evaluates a batch of verified observations and produces an Assessment."""
        pass

    @abstractmethod
    def detect_incidents(self, assessment: Assessment) -> List[Incident]:
        """Identifies anomalies or degradation events requiring incident logging."""
        pass
