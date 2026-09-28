"""
VEYRA Safe Optimization Contracts.
Defines strongly-typed models for evidence-based optimization opportunities,
pre-change snapshots, deterministic state machines, verification outcomes, and rollback plans.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import uuid

from app.core.time import now_utc_iso


class OptimizationState(str, Enum):
    """Rigorous state machine for optimization lifecycle."""
    PROPOSED = "PROPOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    SNAPSHOTTING = "SNAPSHOTTING"
    APPLYING = "APPLYING"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    NO_CHANGE = "NO_CHANGE"
    REGRESSION = "REGRESSION"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class OptimizationCategory(str, Enum):
    """Subsystem categories for optimization opportunities."""
    SYSTEM = "SYSTEM"
    GPU = "GPU"
    NETWORK = "NETWORK"
    BACKGROUND_WORKLOAD = "BACKGROUND_WORKLOAD"
    GAMING = "GAMING"
    STORAGE = "STORAGE"


class OptimizationRiskLevel(str, Enum):
    """Risk classification explaining why the action is categorized as such."""
    SAFE = "SAFE"                # Zero system disruption, fully reversible, standard user privilege
    RECOMMENDED = "RECOMMENDED"  # Measurable benefit, fully reversible, low disruption
    ADVANCED = "ADVANCED"        # Targeted system configuration, strictly reversible, user confirmation required


class VerificationOutcome(str, Enum):
    """Deterministic conclusion of post-optimization measurement."""
    VERIFIED_IMPROVEMENT = "VERIFIED_IMPROVEMENT"
    NO_MEANINGFUL_CHANGE = "NO_MEANINGFUL_CHANGE"
    REGRESSION = "REGRESSION"
    VERIFICATION_INCONCLUSIVE = "VERIFICATION_INCONCLUSIVE"
    APPLICATION_FAILED = "APPLICATION_FAILED"


@dataclass
class OptimizationOpportunity:
    """An evidence-grounded, reversible optimization proposal."""
    id: str
    title: str
    description: str
    category: OptimizationCategory
    evidence: List[str]
    affected_subsystem: str
    risk: OptimizationRiskLevel
    expected_effect: str
    confidence: float
    current_state: Dict[str, Any]
    proposed_state: Dict[str, Any]
    reversible: bool = True
    requires_elevation: bool = False
    verification_plan: str = ""
    rollback_plan: str = ""
    target_metric: str = ""
    created_at: str = field(default_factory=now_utc_iso)
    user_approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "evidence": self.evidence,
            "affected_subsystem": self.affected_subsystem,
            "risk": self.risk.value,
            "expected_effect": self.expected_effect,
            "confidence": self.confidence,
            "current_state": self.current_state,
            "proposed_state": self.proposed_state,
            "reversible": self.reversible,
            "requires_elevation": self.requires_elevation,
            "verification_plan": self.verification_plan,
            "rollback_plan": self.rollback_plan,
            "target_metric": self.target_metric,
            "created_at": self.created_at,
            "user_approved": self.user_approved,
        }


@dataclass
class OptimizationSnapshot:
    """Captured subsystem state before change for deterministic rollback."""
    snapshot_id: str
    opportunity_id: str
    timestamp_utc: str
    subsystem: str
    pre_state: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "opportunity_id": self.opportunity_id,
            "timestamp_utc": self.timestamp_utc,
            "subsystem": self.subsystem,
            "pre_state": self.pre_state,
            "context": self.context,
        }


@dataclass
class VerificationResult:
    """Detailed verification outcome comparing pre and post measurements."""
    outcome: VerificationOutcome
    metric_name: str
    baseline_value: Optional[float]
    post_value: Optional[float]
    difference: Optional[float]
    percentage_change: Optional[float]
    confidence: float
    explanation: str
    should_rollback: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "post_value": self.post_value,
            "difference": self.difference,
            "percentage_change": self.percentage_change,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "should_rollback": self.should_rollback,
        }
