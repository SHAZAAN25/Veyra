"""
VEYRA Diagnostic Probes.
Implements safe, bounded, deterministic probes across:
1. Local PC System Resources
2. Network Adapter State & Link Speed
3. Wi-Fi Association & Signal
4. Local Gateway Reachability
5. DNS Resolution
6. Internet Upstream Reachability
"""
import logging
import os
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

import psutil

from app.core.time import now_utc_iso
from diagnostics.contracts import LayerStatus, TestItemResult

logger = logging.getLogger("veyra.diagnostics.probes")


class SystemResourceProbe:
    """Inspects local CPU, RAM, and Disk load to determine if local saturation exists."""

    def execute(self, timeout_seconds: float = 3.0) -> TestItemResult:
        start = time.perf_counter()
        try:
            cpu_pct = psutil.cpu_percent(interval=0.2)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            duration_ms = (time.perf_counter() - start) * 1000.0

            details = {
                "cpu_utilization_pct": cpu_pct,
                "ram_utilization_pct": mem.percent,
                "ram_available_mb": round(mem.available / (1024 * 1024), 1),
                "disk_utilization_pct": disk.percent,
            }

            if cpu_pct >= 95.0 or mem.percent >= 95.0:
                status = LayerStatus.FAILED
            elif cpu_pct >= 85.0 or mem.percent >= 85.0:
                status = LayerStatus.DEGRADED
            else:
                status = LayerStatus.HEALTHY

            return TestItemResult(
                test_name="System Resources",
                target="localhost",
                status=status,
                details=details,
                duration_ms=duration_ms,
            )
        except Exception as e:
            return TestItemResult(
                test_name="System Resources",
                target="localhost",
                status=LayerStatus.UNKNOWN,
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )


class AdapterProbe:
    """Inspects active network adapters, link states, and IP assignment."""

    def execute(self, timeout_seconds: float = 3.0) -> TestItemResult:
        start = time.perf_counter()
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            duration_ms = (time.perf_counter() - start) * 1000.0

            active_adapters = []
            for name, stat in stats.items():
                if stat.isup and not name.lower().startswith("loopback"):
                    ip_list = [
                        a.address for a in addrs.get(name, [])
                        if a.family == socket.AF_INET and not a.address.startswith("127.")
                    ]
                    if ip_list:
                        active_adapters.append({
                            "name": name,
                            "speed_mbps": stat.speed,
                            "duplex": stat.duplex,
                            "ip": ip_list[0],
                        })

            details = {
                "active_adapters_count": len(active_adapters),
                "adapters": active_adapters,
            }

            if not active_adapters:
                status = LayerStatus.FAILED
            else:
                status = LayerStatus.HEALTHY

            return TestItemResult(
                test_name="Network Adapter",
                target="local_interfaces",
                status=status,
                details=details,
                duration_ms=duration_ms,
            )
        except Exception as e:
            return TestItemResult(
                test_name="Network Adapter",
                target="local_interfaces",
                status=LayerStatus.UNKNOWN,
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )


class WifiProbe:
    """Inspects Wi-Fi association and signal quality safely on Windows."""

    def execute(self, timeout_seconds: float = 3.0) -> TestItemResult:
        start = time.perf_counter()
        try:
            # Query netsh wlan safely with array args and explicit timeout
            cmd = ["netsh", "wlan", "show", "interfaces"]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False
            )
            duration_ms = (time.perf_counter() - start) * 1000.0

            output = proc.stdout or ""
            if "There is no wireless interface" in output or proc.returncode != 0:
                return TestItemResult(
                    test_name="Wi-Fi Interface",
                    target="wlan",
                    status=LayerStatus.UNSUPPORTED,
                    details={"message": "No Wi-Fi interface detected or interface disabled."},
                    duration_ms=duration_ms,
                )

            # Parse signal and state
            state = "disconnected"
            signal_pct = None
            ssid = None

            for line in output.splitlines():
                line = line.strip()
                if line.startswith("State") and ":" in line:
                    state = line.split(":", 1)[1].strip()
                elif line.startswith("Signal") and ":" in line:
                    val = line.split(":", 1)[1].strip().replace("%", "")
                    try:
                        signal_pct = float(val)
                    except ValueError:
                        pass
                elif line.startswith("SSID") and not line.startswith("BSSID") and ":" in line:
                    ssid = line.split(":", 1)[1].strip()

            details = {
                "state": state,
                "ssid": ssid or "Unknown",
                "signal_pct": signal_pct,
            }

            if state.lower() == "connected":
                if signal_pct is not None and signal_pct < 35.0:
                    status = LayerStatus.DEGRADED
                else:
                    status = LayerStatus.HEALTHY
            elif state.lower() == "disconnected":
                status = LayerStatus.FAILED
            else:
                status = LayerStatus.UNKNOWN

            return TestItemResult(
                test_name="Wi-Fi Interface",
                target=ssid or "wlan",
                status=status,
                details=details,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            return TestItemResult(
                test_name="Wi-Fi Interface",
                target="wlan",
                status=LayerStatus.DEGRADED,
                error_message="Wi-Fi query timed out",
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )
        except Exception as e:
            return TestItemResult(
                test_name="Wi-Fi Interface",
                target="wlan",
                status=LayerStatus.UNKNOWN,
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )


class GatewayProbe:
    """Detects and tests reachability to the default local network gateway."""

    @staticmethod
    def _find_default_gateway_ip() -> Optional[str]:
        """Safely extracts default gateway on Windows using netstat/route command."""
        try:
            proc = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False
            )
            for line in proc.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    gateway = parts[2]
                    # Verify it's a valid IPv4
                    socket.inet_aton(gateway)
                    return gateway
        except Exception:
            pass
        return None

    def execute(self, gateway_ip: Optional[str] = None, timeout_seconds: float = 3.0) -> TestItemResult:
        start = time.perf_counter()
        target_ip = gateway_ip or self._find_default_gateway_ip() or "192.168.1.1"

        try:
            # Measure reachability using ping on Windows with 2 packets
            cmd = ["ping", "-n", "2", "-w", str(int(timeout_seconds * 500)), target_ip]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False
            )
            duration_ms = (time.perf_counter() - start) * 1000.0

            output = proc.stdout or ""
            latency_ms = None
            packet_loss_pct = 100.0

            # Parse ping output
            for line in output.splitlines():
                line = line.strip()
                if "loss" in line.lower() and "%" in line:
                    # e.g. "Packets: Sent = 2, Received = 2, Lost = 0 (0% loss)"
                    try:
                        loss_part = line.split("(")[1].split("%")[0].strip()
                        packet_loss_pct = float(loss_part)
                    except Exception:
                        pass
                elif "average =" in line.lower():
                    # e.g. "Minimum = 1ms, Maximum = 2ms, Average = 1ms"
                    try:
                        avg_str = line.split("Average =")[1].replace("ms", "").strip()
                        latency_ms = float(avg_str)
                    except Exception:
                        pass

            details = {
                "gateway_ip": target_ip,
                "latency_ms": latency_ms,
                "packet_loss_pct": packet_loss_pct,
            }

            if proc.returncode != 0 or packet_loss_pct >= 100.0:
                status = LayerStatus.FAILED
            elif packet_loss_pct > 0.0 or (latency_ms is not None and latency_ms > 20.0):
                status = LayerStatus.DEGRADED
            else:
                status = LayerStatus.HEALTHY

            return TestItemResult(
                test_name="Default Gateway",
                target=target_ip,
                status=status,
                latency_ms=latency_ms,
                packet_loss_pct=packet_loss_pct,
                details=details,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            return TestItemResult(
                test_name="Default Gateway",
                target=target_ip,
                status=LayerStatus.FAILED,
                packet_loss_pct=100.0,
                error_message="Gateway ping timed out",
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )
        except Exception as e:
            return TestItemResult(
                test_name="Default Gateway",
                target=target_ip,
                status=LayerStatus.UNKNOWN,
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )


class DnsProbe:
    """Tests DNS query resolution time and correctness against safe domains."""

    TEST_DOMAINS = ["one.one.one.one", "dns.google"]

    def execute(self, timeout_seconds: float = 3.0) -> TestItemResult:
        start = time.perf_counter()
        latencies = []
        resolved_ips = {}
        failed_count = 0

        for domain in self.TEST_DOMAINS:
            try:
                t0 = time.perf_counter()
                socket.setdefaulttimeout(timeout_seconds / len(self.TEST_DOMAINS))
                ip = socket.gethostbyname(domain)
                rtt = (time.perf_counter() - t0) * 1000.0
                latencies.append(rtt)
                resolved_ips[domain] = ip
            except Exception:
                failed_count += 1

        duration_ms = (time.perf_counter() - start) * 1000.0
        avg_latency = sum(latencies) / len(latencies) if latencies else None

        details = {
            "tested_domains": self.TEST_DOMAINS,
            "resolved_ips": resolved_ips,
            "failures": failed_count,
            "avg_query_time_ms": round(avg_latency, 2) if avg_latency else None,
        }

        if failed_count == len(self.TEST_DOMAINS):
            status = LayerStatus.FAILED
        elif failed_count > 0 or (avg_latency and avg_latency > 150.0):
            status = LayerStatus.DEGRADED
        else:
            status = LayerStatus.HEALTHY

        return TestItemResult(
            test_name="DNS Subsystem",
            target="system_resolver",
            status=status,
            latency_ms=round(avg_latency, 2) if avg_latency else None,
            packet_loss_pct=round((failed_count / len(self.TEST_DOMAINS)) * 100.0, 1),
            details=details,
            duration_ms=duration_ms,
        )


class InternetProbe:
    """Tests external upstream connectivity, latency, packet loss, and jitter."""

    SAFE_TARGETS = ["1.1.1.1", "8.8.8.8"]

    def execute(self, target: Optional[str] = None, timeout_seconds: float = 3.0) -> TestItemResult:
        start = time.perf_counter()
        primary_target = target or self.SAFE_TARGETS[0]

        try:
            cmd = ["ping", "-n", "3", "-w", str(int(timeout_seconds * 333)), primary_target]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False
            )
            duration_ms = (time.perf_counter() - start) * 1000.0

            output = proc.stdout or ""
            latency_ms = None
            packet_loss_pct = 100.0
            rtts = []

            for line in output.splitlines():
                line = line.strip()
                if "time=" in line.lower():
                    # e.g. "Reply from 1.1.1.1: bytes=32 time=14ms TTL=57"
                    try:
                        t_part = line.lower().split("time=")[1].split("ms")[0].strip()
                        rtts.append(float(t_part))
                    except Exception:
                        pass
                elif "loss" in line.lower() and "%" in line:
                    try:
                        loss_part = line.split("(")[1].split("%")[0].strip()
                        packet_loss_pct = float(loss_part)
                    except Exception:
                        pass
                elif "average =" in line.lower():
                    try:
                        avg_str = line.split("Average =")[1].replace("ms", "").strip()
                        latency_ms = float(avg_str)
                    except Exception:
                        pass

            jitter_ms = None
            if len(rtts) >= 2:
                diffs = [abs(rtts[i] - rtts[i - 1]) for i in range(1, len(rtts))]
                jitter_ms = round(sum(diffs) / len(diffs), 2)

            details = {
                "target": primary_target,
                "latency_ms": latency_ms,
                "packet_loss_pct": packet_loss_pct,
                "jitter_ms": jitter_ms,
                "sample_rtts": rtts,
            }

            if proc.returncode != 0 or packet_loss_pct >= 100.0:
                status = LayerStatus.FAILED
            elif packet_loss_pct > 0.0 or (latency_ms is not None and latency_ms > 80.0):
                status = LayerStatus.DEGRADED
            else:
                status = LayerStatus.HEALTHY

            return TestItemResult(
                test_name="Internet Reachability",
                target=primary_target,
                status=status,
                latency_ms=latency_ms,
                packet_loss_pct=packet_loss_pct,
                details=details,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            return TestItemResult(
                test_name="Internet Reachability",
                target=primary_target,
                status=LayerStatus.FAILED,
                packet_loss_pct=100.0,
                error_message="Internet probe timed out",
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )
        except Exception as e:
            return TestItemResult(
                test_name="Internet Reachability",
                target=primary_target,
                status=LayerStatus.UNKNOWN,
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )
