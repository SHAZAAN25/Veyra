"""
VEYRA Evidence-Grounded AI Contracts.
Defines response formats, citation references, and optional AI provider interfaces.
Strictly prohibits ungrounded claims or hallucinated telemetry.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from analyzer.contracts import AIEvidencePackage


class ResponseClassification(str, Enum):
    """Classification of certainty in AI statements."""
    OBSERVED = "OBSERVED"        # Direct physical measurement from active collector
    CALCULATED = "CALCULATED"    # Deterministic statistical calculation
    HISTORICAL = "HISTORICAL"    # Retrieved from verified SQLite history
    CORRELATED = "CORRELATED"    # Cross-subsystem coincidence backed by evidence
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNSUPPORTED = "UNSUPPORTED"  # Question outside PC observability scope


@dataclass
class AIResponse:
    """Traceable, evidence-backed answer."""
    question: str
    answer: str
    confidence: float
    response_type: ResponseClassification
    citations: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    evidence_package: Optional[AIEvidencePackage] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "confidence": self.confidence,
            "response_type": self.response_type.value,
            "citations": self.citations,
            "unknowns": self.unknowns,
            "evidence_package_id": self.evidence_package.package_id if self.evidence_package else None,
        }


class AIProvider(ABC):
    """Optional adapter interface for local or external LLMs. Completely optional."""

    @abstractmethod
    def generate_grounded_answer(
        self,
        package: AIEvidencePackage,
        user_question: str
    ) -> Optional[str]:
        """Synthesizes natural language backed strictly by the supplied evidence package."""
        pass
