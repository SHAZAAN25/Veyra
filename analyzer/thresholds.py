"""
VEYRA Centralized Incident & Anomaly Thresholds with Hysteresis.
Eliminates magic numbers. Defines explicit trigger, recovery, observation count,
cooldown, grouping, and evidence window parameters.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricHysteresisThreshold:
    """Trigger and recovery thresholds enforcing hysteresis to eliminate alert flapping."""
    trigger_value: float
    recovery_value: float
    min_consecutive_triggers: int = 1
    min_consecutive_recoveries: int = 1
    unit: str = ""


@dataclass
class DetectionThresholds:
    """Centralized, documented threshold parameters."""
    # Network Latency (ms)
    latency_ms: MetricHysteresisThreshold = MetricHysteresisThreshold(
        trigger_value=120.0,
        recovery_value=70.0,
        min_consecutive_triggers=2,
        min_consecutive_recoveries=2,
        unit="ms"
    )

    # Packet Loss (%)
    packet_loss_pct: MetricHysteresisThreshold = MetricHysteresisThreshold(
        trigger_value=5.0,
        recovery_value=1.0,
        min_consecutive_triggers=1,
        min_consecutive_recoveries=2,
        unit="%"
    )

    # Statistical Jitter (ms)
    jitter_ms: MetricHysteresisThreshold = MetricHysteresisThreshold(
        trigger_value=30.0,
        recovery_value=15.0,
        min_consecutive_triggers=2,
        min_consecutive_recoveries=2,
        unit="ms"
    )

    # Wi-Fi Signal Strength (%)
    wifi_signal_pct: MetricHysteresisThreshold = MetricHysteresisThreshold(
        trigger_value=45.0,  # Below 45% triggers degradation
        recovery_value=60.0,  # Must recover above 60%
        min_consecutive_triggers=2,
        min_consecutive_recoveries=2,
        unit="%"
    )

    # System CPU Pressure (%)
    cpu_utilization_pct: MetricHysteresisThreshold = MetricHysteresisThreshold(
        trigger_value=92.0,
        recovery_value=78.0,
        min_consecutive_triggers=2,
        min_consecutive_recoveries=2,
        unit="%"
    )

    # System RAM Pressure (%)
    ram_utilization_pct: MetricHysteresisThreshold = MetricHysteresisThreshold(
        trigger_value=93.0,
        recovery_value=85.0,
        min_consecutive_triggers=2,
        min_consecutive_recoveries=2,
        unit="%"
    )

    # GPU Temperature (C)
    gpu_temperature_c: MetricHysteresisThreshold = MetricHysteresisThreshold(
        trigger_value=86.0,
        recovery_value=75.0,
        min_consecutive_triggers=2,
        min_consecutive_recoveries=2,
        unit="C"
    )

    # DNS Resolution Latency (ms)
    dns_latency_ms: MetricHysteresisThreshold = MetricHysteresisThreshold(
        trigger_value=250.0,
        recovery_value=100.0,
        min_consecutive_triggers=2,
        min_consecutive_recoveries=1,
        unit="ms"
    )

    # Windows and Timers
    grouping_window_seconds: float = 15.0      # Window to merge related layer events
    cooldown_seconds: float = 10.0             # Minimum period before retriggering same type
    evidence_window_before_seconds: float = 30.0  # Context captured prior to event
    evidence_window_after_seconds: float = 30.0   # Context captured post-recovery
    max_evidence_observations: int = 60        # Maximum in-memory points retained per window
    freshness_max_age_seconds: float = 12.0    # Age beyond which observation is considered stale
    baseline_minimum_samples: int = 15         # Minimum observations required to establish baseline
    regression_threshold_multiplier: float = 1.5 # 50% deviation from baseline flags regression


def get_default_thresholds() -> DetectionThresholds:
    return DetectionThresholds()
