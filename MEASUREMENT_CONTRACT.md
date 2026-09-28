# VEYRA — Measurement Contract

> **Contract Version:** 1.0.0  
> **Applicability:** All metric collectors in Stage 1 and beyond.

---

## 1. General Collector Principles

Collectors are the sole interface between the real physical host/network and the VEYRA platform.

Every collector must strictly adhere to the following invariants:

1. **Absolute Real Telemetry:** Only genuine readings from the operating system, hardware sensors, network stacks, or ICMP/DNS responses may be emitted.
2. **Deterministic Timeouts:** Every network and subprocess call must specify a bounded timeout (e.g., maximum 1.5s for ping, 15s for diagnostics). Hanging collectors are strictly prohibited.
3. **Explicit Failure Modeling:** Inability to obtain a reading must result in an explicit `MetricState` with an informative `error_message`, never a silent fallback to `0.0`.
4. **Health Reporting:** Collectors must implement `check_health()` to inform the coordinator of failure counts, operational status, and degradation.
5. **Safe Isolation:** A failure in one collector (e.g. GPU sensor failure) must never crash or prevent execution of other collectors (e.g. network ping).

---

## 2. Defined Metric Domains

### A. Network Latency & Quality
- **`latency_ms`**: Measured via real ICMP echo requests or TCP handshake to defined targets (`1.1.1.1`, gateway).
- **`packet_loss_pct`**: Calculated over a sliding window of sequential ping transmissions (e.g., last 20 probes).
- **`jitter_ms`**: Statistical jitter computed as Mean Absolute Deviation (RFC 3550 / 1889) of consecutive RTT samples.
- **`dns_response_ms`**: Real resolution time of target hostnames using system or specified resolver.

### B. Wi-Fi & Physical Layer
- **`wifi_signal_pct` / `wifi_rssi_dbm`**: Extracted from OS WLAN subsystem (`netsh wlan show interfaces` on Windows).
- **`wifi_ssid` & `wifi_bssid`**: Genuine active connection identity.
- **`wifi_band` & `wifi_channel`**: e.g., 2.4 GHz, 5 GHz, 6 GHz, Channel number.
- **`wifi_link_speed_mbps`**: Real TX/RX link rate negotiated with the access point.
- *Handling on Ethernet:* If the active interface is Ethernet, Wi-Fi metrics must explicitly report `MetricState.NOT_SUPPORTED`.

### C. System & Hardware Telemetry
- **`cpu_usage_pct`**: Overall and per-core processor utilization from OS performance counters or `psutil`.
- **`ram_usage_pct` & `ram_used_mb`**: Physical RAM allocation and commit charge.
- **`disk_usage_pct` & `disk_io_mbps`**: System drive occupancy and read/write throughput.
- **`network_throughput_rx_mbps` / `tx_mbps`**: Interface delta bytes over sampling interval.

### D. GPU & Gaming Telemetry
- **`gpu_usage_pct`**: GPU core computing engine utilization.
- **`gpu_memory_used_mb`**: Dedicated video memory (VRAM) allocated.
- **`gpu_temperature_c`**: Die temperature from vendor API (NVIDIA NVML, AMD ADL, or OS WMI).
- *Unsupported Hardware:* If no compatible dedicated GPU or sensor is present, GPU metrics must report `MetricState.NOT_SUPPORTED`.

---

## 3. Collector Error Handling Table

| Condition | Assigned State | Value | Error Detail |
|---|---|---|---|
| Target does not respond within timeout | `UNAVAILABLE` | `None` | `"Request timed out after Xs"` |
| Interface is disabled / down | `UNAVAILABLE` | `None` | `"Network adapter is disconnected"` |
| Administrator / elevated privilege missing | `PERMISSION_REQUIRED` | `None` | `"Administrative permissions required to read sensor"` |
| No dedicated GPU / no Wi-Fi card | `NOT_SUPPORTED` | `None` | `"Hardware sensor not present on host"` |
| Sensor driver crashed or returned invalid string | `MEASUREMENT_FAILED` | `None` | `"Malformed command output"` |
