"""
VEYRA Network Collectors (Adapter info & Throughput).
"""
from collectors.network.adapter import AdapterCollector
from collectors.network.throughput import ThroughputCollector

__all__ = ["AdapterCollector", "ThroughputCollector"]
