"""
VEYRA Future Optimization Safety & Contracts Package.
Defines contracts for future optimization opportunities.
STRICT INVARIANT: No optimization execution, system modification, or UI exists in this stage.
"""
from analyzer.contracts import OptimizationCandidate

__all__ = ["OptimizationCandidate"]
