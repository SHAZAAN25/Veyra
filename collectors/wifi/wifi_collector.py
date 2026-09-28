"""
VEYRA Real Wi-Fi Collector (Layer 1 Physical Wireless).
Inspects wireless interface states, connected SSID, BSSID, RSSI/signal quality, radio type, and channel.
Gracefully handles Ethernet-only machines and disconnected states by reporting NOT_SUPPORTED or UNAVAILABLE.
"""
import re
import time
from typing import Dict, Optional

from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from app.core.security import run_safe_subprocess
from collectors.common import StatefulCollector, NetworkLayer


class WifiCollector(StatefulCollector):
    def __init__(self):
        super().__init__("network_wifi")
        self._cmd = ["netsh", "wlan", "show", "interfaces"]

    def collect(self) -> Observation:
        start_time = time.perf_counter()
        measurements: Dict[str, Measurement] = {}

        try:
            res = run_safe_subprocess(self._cmd, timeout_seconds=3.0)
            if res.returncode != 0:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self._mark_unsupported("netsh wlan interface query failed or host has no Wi-Fi subsystem.")
                return self._build_unsupported_observation("WLAN service not running or no wireless adapter present")

            stdout = res.stdout

            # Check if there are no wireless interfaces
            if "There is no wireless interface on the system" in stdout or "There are no wireless interfaces" in stdout:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self._mark_unsupported("No wireless interface on system (Host is likely pure Ethernet).")
                return self._build_unsupported_observation("No wireless hardware adapter present")

            # Parse key-value lines: "    Name                   : Wi-Fi"
            parsed: Dict[str, str] = {}
            for line in stdout.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    parsed[key.strip().lower()] = val.strip()

            state = parsed.get("state", "disconnected").lower()
            is_connected = (state == "connected")

            # 1. Connected state
            measurements["wifi_connected"] = Measurement(
                metric_name="wifi_connected",
                state=MetricState.AVAILABLE,
                value=is_connected,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:state"
            )

            if not is_connected:
                # Connected=False, other Wi-Fi metrics unavailable
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                self._mark_degraded("Wi-Fi adapter is present but not connected to an access point.", duration_ms)
                measurements["wifi_ssid"] = Measurement(
                    metric_name="wifi_ssid",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.STRING,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:ssid",
                    error_message="Wireless adapter is not connected"
                )
                measurements["wifi_signal_pct"] = Measurement(
                    metric_name="wifi_signal_pct",
                    state=MetricState.UNAVAILABLE,
                    value=None,
                    unit=MetricUnit.PERCENTAGE,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:signal",
                    error_message="Wireless adapter is not connected"
                )
                return self.create_observation(measurements, healthy=True, status_summary="DISCONNECTED")

            # 2. SSID
            ssid = parsed.get("ssid")
            if ssid:
                measurements["wifi_ssid"] = Measurement(
                    metric_name="wifi_ssid",
                    state=MetricState.AVAILABLE,
                    value=ssid,
                    unit=MetricUnit.STRING,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:ssid"
                )

            # 3. BSSID (Sanitized access point MAC)
            bssid = parsed.get("bssid") or parsed.get("ap bssid")
            if bssid:
                measurements["wifi_bssid"] = Measurement(
                    metric_name="wifi_bssid",
                    state=MetricState.AVAILABLE,
                    value=bssid,
                    unit=MetricUnit.STRING,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:bssid"
                )

            # 4. Signal Percentage (%)
            signal_raw = parsed.get("signal", "")
            signal_match = re.search(r"(\d+)%", signal_raw)
            if signal_match:
                signal_pct = float(signal_match.group(1))
                measurements["wifi_signal_pct"] = Measurement(
                    metric_name="wifi_signal_pct",
                    state=MetricState.AVAILABLE,
                    value=signal_pct,
                    unit=MetricUnit.PERCENTAGE,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:signal"
                )

            # 5. RSSI (dBm)
            rssi_raw = parsed.get("rssi", "")
            rssi_match = re.search(r"(-?\d+)", rssi_raw)
            if rssi_match:
                rssi_dbm = float(rssi_match.group(1))
                measurements["wifi_rssi_dbm"] = Measurement(
                    metric_name="wifi_rssi_dbm",
                    state=MetricState.AVAILABLE,
                    value=rssi_dbm,
                    unit=MetricUnit.DBM,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:rssi"
                )

            # 6. Band & Channel
            band = parsed.get("band")
            if band:
                measurements["wifi_band"] = Measurement(
                    metric_name="wifi_band",
                    state=MetricState.AVAILABLE,
                    value=band,
                    unit=MetricUnit.STRING,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:band"
                )

            channel_raw = parsed.get("channel")
            if channel_raw and channel_raw.isdigit():
                measurements["wifi_channel"] = Measurement(
                    metric_name="wifi_channel",
                    state=MetricState.AVAILABLE,
                    value=int(channel_raw),
                    unit=MetricUnit.COUNT,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:channel"
                )

            # 7. Radio Type (e.g. 802.11ax)
            radio = parsed.get("radio type")
            if radio:
                measurements["wifi_radio_type"] = Measurement(
                    metric_name="wifi_radio_type",
                    state=MetricState.AVAILABLE,
                    value=radio,
                    unit=MetricUnit.STRING,
                    source_collector=self.name,
                    provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:radio"
                )

            # 8. Receive / Transmit Link Rates
            rx_raw = parsed.get("receive rate (mbps)")
            if rx_raw:
                try:
                    measurements["wifi_link_rate_rx_mbps"] = Measurement(
                        metric_name="wifi_link_rate_rx_mbps",
                        state=MetricState.AVAILABLE,
                        value=float(rx_raw),
                        unit=MetricUnit.MEGABITS_PER_SECOND,
                        source_collector=self.name,
                        provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:rx_rate"
                    )
                except ValueError:
                    pass

            tx_raw = parsed.get("transmit rate (mbps)")
            if tx_raw:
                try:
                    measurements["wifi_link_rate_tx_mbps"] = Measurement(
                        metric_name="wifi_link_rate_tx_mbps",
                        state=MetricState.AVAILABLE,
                        value=float(tx_raw),
                        unit=MetricUnit.MEGABITS_PER_SECOND,
                        source_collector=self.name,
                        provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:netsh_wlan:tx_rate"
                    )
                except ValueError:
                    pass

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_success(duration_ms)
            return self.create_observation(measurements, healthy=True, status_summary="CONNECTED")

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self._mark_failed(str(e), duration_ms)
            measurements["wifi_connected"] = Measurement(
                metric_name="wifi_connected",
                state=MetricState.MEASUREMENT_FAILED,
                value=None,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:wifi",
                error_message=f"Wi-Fi collection failed: {e}"
            )
            return self.create_observation(measurements, healthy=False, status_summary=f"ERROR: {e}")

    def _build_unsupported_observation(self, reason: str) -> Observation:
        measurements: Dict[str, Measurement] = {
            "wifi_connected": Measurement(
                metric_name="wifi_connected",
                state=MetricState.NOT_SUPPORTED,
                value=None,
                unit=MetricUnit.BOOLEAN,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:wifi",
                error_message=reason
            ),
            "wifi_signal_pct": Measurement(
                metric_name="wifi_signal_pct",
                state=MetricState.NOT_SUPPORTED,
                value=None,
                unit=MetricUnit.PERCENTAGE,
                source_collector=self.name,
                provenance=f"{NetworkLayer.LAYER_1_ADAPTER.value}:wifi",
                error_message=reason
            )
        }
        return self.create_observation(measurements, healthy=False, status_summary="NOT_SUPPORTED")
