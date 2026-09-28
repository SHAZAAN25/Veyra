"""
VEYRA System Collectors (CPU, Memory, Disk).
"""
from collectors.system.cpu import CpuCollector
from collectors.system.memory import MemoryCollector
from collectors.system.disk import DiskCollector

__all__ = ["CpuCollector", "MemoryCollector", "DiskCollector"]
