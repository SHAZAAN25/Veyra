# VEYRA — Telemetry Data Contract

> **Contract Version:** 1.0.0  
> **Integrity Status:** FROZEN & MANDATORY

---

## 1. The Core Lifecycle

Telemetry flows through five distinct stages in VEYRA:

1. **Measurement (`Measurement`):** An atomic metric reading produced directly by a collector.
2. **Observation (`Observation`):** A synchronized batch of validated measurements for a single sampling interval.
3. **Assessment (`Assessment`):** An operational evaluation by an analyzer determining stability, health, and threshold crossings.
4. **Incident (`Incident`):** A persistent record of a detected outage, jitter spike, packet loss burst, or system bottleneck.
5. **Historical Summary (`HistoricalSummary`):** A time-bucket rollup (1-min, 5-min, 30-min, 1-hour) persisted long-term.

---

## 2. The Five Pillars of Traceability

Every single metric captured in VEYRA must be traceable across five dimensions:

| Dimension | Field | Description | Example |
|---|---|---|---|
| **WHAT** | `metric_name` | Canonical identifier of the metric | `network_rtt_ms` |
| **WHEN** | `timestamp_utc` | Precise ISO 8601 UTC timestamp | `2026-09-28T15:30:00.123456Z` |
| **WHERE** | `source_collector` + `provenance` | Exact collector and execution command / interface | `icmp_ping` / `target:1.1.1.1` |
| **WHETHER VALID** | `state` + `is_valid` | Explicit operational state | `AVAILABLE` (True) or `NOT_SUPPORTED` |
| **HOW FRESH** | `monotonic_timestamp` | Steady elapsed seconds immune to system clock shifts | `124583.42` |

---

## 3. Explicit Metric States

When a measurement cannot be obtained, it is **strictly forbidden** to emit fake numbers, dummy placeholders, or zero masquerading as valid data.

The system enforces seven explicit states:

```python
class MetricState(str, Enum):
    AVAILABLE = "AVAILABLE"                      # Successfully measured with valid reading
    UNAVAILABLE = "UNAVAILABLE"                  # Temporarily unreachable (e.g. gateway down)
    NOT_SUPPORTED = "NOT_SUPPORTED"              # Hardware/OS does not support metric (e.g. Wi-Fi on Ethernet-only)
    STALE = "STALE"                              # Measurement age exceeds freshness threshold
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"  # Requires elevated or admin privileges
    COLLECTOR_UNAVAILABLE = "COLLECTOR_UNAVAILABLE" # Underlying tool or subsystem missing
    MEASUREMENT_FAILED = "MEASUREMENT_FAILED"    # Subprocess or API error during collection
```

### Invalidation & Validation Invariants

1. If `state == MetricState.AVAILABLE`: `value` **MUST NOT** be `None`.
2. If `state != MetricState.AVAILABLE`: `value` **MUST** be `None`. Any numeric or fabricated value attached to a non-AVAILABLE state causes immediate `DataContractViolationError`.
3. `confidence`: A floating-point number between `0.0` and `1.0` representing collector precision.

---

## 4. Standardized Units (`MetricUnit`)

- `ms`: Latency, round-trip time, jitter, DNS query time.
- `%`: Packet loss percentage, CPU usage, RAM utilization, Wi-Fi link quality.
- `Mbps`: Network throughput (ingress/egress), interface link speed.
- `MB` / `GB`: Memory allocations, disk capacity.
- `C`: Temperatures (CPU, GPU).
- `dBm`: Wi-Fi Received Signal Strength Indicator (RSSI).
- `Hz`: Clock frequencies.
- `count`: Packet count, error count, retransmission count.
- `string`: SSID, BSSID, gateway IP, interface name.
- `bool`: Connection status, flag indicators.

---

## 5. Historical Summary Data Quality (`DataQuality`)

Historical summaries produced by the statistical aggregation engine evaluate sample validity and assign one of six explicit quality classifications:

```python
class DataQuality(str, Enum):
    VALID = "VALID"                      # >=95% samples valid with full statistical rigor
    PARTIAL = "PARTIAL"                  # Some valid readings, some unavailable
    DEGRADED = "DEGRADED"                # High volatility or collector reported degraded
    STALE = "STALE"                      # Timestamp gap or stale telemetry
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Too few samples to form a defensible statistic
    UNAVAILABLE = "UNAVAILABLE"          # 0 valid samples in the bucket
```

---

## 6. Persistence Invariants

1. **Non-Fabrication in Aggregates:** When `data_quality == UNAVAILABLE`, all statistical aggregates (`min_value`, `max_value`, `mean_value`, `median_value`, `p95_value`, `std_dev`) **MUST** be `None`. No zeroes are inserted as fallbacks.
2. **Missing != Zero:** 0.0% packet loss is a valid measurement; missing packet loss is `None` with `unavailable_count > 0`.
3. **Anti-Contamination Baseline Policy:** Measurements recorded during active incidents are strictly segregated and prohibited from altering established Personal PC Baselines.
4. **Local Isolation:** Historical SQLite records are stored locally with zero external network transmission.
