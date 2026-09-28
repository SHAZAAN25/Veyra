"""
VEYRA 'What Changed?' Engine Foundation.
Tracks and reports genuine environment and configuration transitions across network and hardware states.
Never creates fabricated changes; only reports differences supported by verified observations.
"""
from typing import Dict, Any, List, Optional
import uuid

from app.core.contracts import Observation, MetricState
from analyzer.contracts import ChangeEvent


class ChangeDetector:
    """
    Compares successive observations to detect meaningful network and hardware changes.
    """
    def __init__(self):
        self._last_state: Dict[str, Any] = {}

    def detect_changes(self, observations: Dict[str, Observation]) -> List[ChangeEvent]:
        """
        Extracts current network and configuration parameters and compares with previous snapshot.
        """
        changes: List[ChangeEvent] = []
        current_state: Dict[str, Any] = {}

        # 1. Adapter state
        adapter_obs = observations.get("adapter")
        if adapter_obs:
            for key in ["adapter_name", "adapter_ipv4_address", "adapter_link_speed_mbps", "adapter_is_up"]:
                m = adapter_obs.get_metric(key)
                if m and m.state == MetricState.AVAILABLE:
                    current_state[key] = m.value

        # 2. Wi-Fi state
        wifi_obs = observations.get("wifi")
        if wifi_obs:
            for key in ["wifi_ssid", "wifi_bssid", "wifi_channel", "wifi_band", "wifi_radio_type", "wifi_connected"]:
                m = wifi_obs.get_metric(key)
                if m and m.state == MetricState.AVAILABLE:
                    current_state[key] = m.value

        # 3. Gateway state
        gw_obs = observations.get("gateway")
        if gw_obs:
            m = gw_obs.get_metric("gateway_ip")
            if m and m.state == MetricState.AVAILABLE:
                current_state["gateway_ip"] = m.value

        # Compare with last state
        if self._last_state:
            for key, new_val in current_state.items():
                if key in self._last_state:
                    old_val = self._last_state[key]
                    if old_val != new_val:
                        # Determine category and significance
                        category = "NETWORK"
                        significance = "NORMAL"
                        if "wifi" in key:
                            category = "WIFI"
                            if key in {"wifi_ssid", "wifi_bssid"}:
                                significance = "SUSPICIOUS"
                        elif "gateway" in key:
                            category = "GATEWAY"
                            significance = "SUSPICIOUS"

                        changes.append(ChangeEvent(
                            change_id=f"chg_{uuid.uuid4().hex[:8]}",
                            category=category,
                            attribute_name=key,
                            old_value=old_val,
                            new_value=new_val,
                            significance=significance
                        ))

        # Update last known state
        self._last_state = current_state
        return changes
