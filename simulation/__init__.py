"""
VEYRA Simulation & Chaos Engineering Framework
Stage 7 Automated Testing, Fault Injection & QA Harnesses

MANDATORY ISOLATION NOTICE (Rule 9):
Simulation telemetry and test mocks are strictly isolated to prevent
contaminating production storage or masquerading as real hardware measurements.
"""

from simulation.contracts import (
    ChaosExperiment,
    FaultScenario,
    FaultType,
    ChaosReport,
    SimulationTarget,
)
from simulation.chaos_engine import ChaosEngine
from simulation.fault_injectors import (
    GpuFaultInjector,
    StorageFaultInjector,
    ProcessFaultInjector,
    TimeChaosInjector,
)
from simulation.network_chaos import NetworkChaosSimulator
from simulation.soak_harness import SoakHarness, SoakTestResult

__all__ = [
    "ChaosExperiment",
    "FaultScenario",
    "FaultType",
    "ChaosReport",
    "SimulationTarget",
    "ChaosEngine",
    "GpuFaultInjector",
    "StorageFaultInjector",
    "ProcessFaultInjector",
    "TimeChaosInjector",
    "NetworkChaosSimulator",
    "SoakHarness",
    "SoakTestResult",
]
