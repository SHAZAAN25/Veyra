"""
VEYRA Safe Optimization Subsystem Package.
"""
from optimization.ab_testing import ABExperimentReport, ConfounderEvaluation, OptimizationABTestingEngine
from optimization.actions import (
    BaseOptimizationAction,
    DnsCacheFlushAction,
    PowerSchemeOptimizationAction,
    ProcessPriorityHintAction,
)
from optimization.contracts import (
    OptimizationCategory,
    OptimizationOpportunity,
    OptimizationRiskLevel,
    OptimizationSnapshot,
    OptimizationState,
    VerificationOutcome,
    VerificationResult,
)
from optimization.executor import OptimizationExecutor
from optimization.opportunities import OptimizationOpportunityEngine
from optimization.rollback_guardian import AutomaticRollbackGuardian
from optimization.snapshots import SnapshotManager
from optimization.verification import VerificationEngine

__all__ = [
    "OptimizationState",
    "OptimizationCategory",
    "OptimizationRiskLevel",
    "VerificationOutcome",
    "OptimizationOpportunity",
    "OptimizationSnapshot",
    "VerificationResult",
    "BaseOptimizationAction",
    "DnsCacheFlushAction",
    "ProcessPriorityHintAction",
    "PowerSchemeOptimizationAction",
    "SnapshotManager",
    "OptimizationOpportunityEngine",
    "VerificationEngine",
    "AutomaticRollbackGuardian",
    "ABExperimentReport",
    "ConfounderEvaluation",
    "OptimizationABTestingEngine",
    "OptimizationExecutor",
]
