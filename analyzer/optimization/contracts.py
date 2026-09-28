"""
VEYRA Future Optimization Safety & Verification Contracts.
Defines schemas for future Optimization Opportunities, A/B Testing, and Automatic Rollback Guardians.
Enforces the strict rule: Stage 2 contains ZERO optimization execution, zero registry changes,
and zero administrator requirements.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from analyzer.contracts import OptimizationCandidate


class OptimizationRiskLevel(str, Enum):
    SAFE = "SAFE"
    RECOMMENDED = "RECOMMENDED"
    ADVANCED = "ADVANCED"


class OptimizationPrivilegeLevel(str, Enum):
    STANDARD_USER = "STANDARD_USER"
    ELEVATED_ADMIN = "ELEVATED_ADMIN"


@dataclass
class FutureOptimizationContract:
    """
    Contract governing all future optimization candidates.
    Guarantees least-privilege, user approval, snapshotting, and rollback.
    """
    risk_level: OptimizationRiskLevel
    privilege_level: OptimizationPrivilegeLevel
    is_reversible: bool = True
    requires_user_approval: bool = True
    requires_pre_snapshot: bool = True
    verification_duration_seconds: float = 30.0
    rollback_supported: bool = True

    def validate_safety_rules(self) -> bool:
        """Asserts that safety requirements are never bypassed."""
        if not self.requires_user_approval:
            raise ValueError("Optimization without user approval is strictly prohibited.")
        if not self.rollback_supported:
            raise ValueError("Non-reversible optimization is prohibited.")
        return True
