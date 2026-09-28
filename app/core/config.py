"""
VEYRA Configuration Engine.
Defines strongly-typed, domain-separated configuration structures with
strict validation and localhost-only security defaults.
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, Optional
import json

from app.core.exceptions import ConfigurationError, SecurityViolationError


# Allowed binding hosts for local-first architecture
ALLOWED_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass
class AppConfig:
    """Core application settings."""
    product_name: str = "VEYRA"
    version: str = "0.1.0"
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    debug: bool = False
    log_level: str = "INFO"

    def validate(self) -> None:
        if self.api_host not in ALLOWED_LOCAL_HOSTS:
            raise SecurityViolationError(
                f"Insecure API binding host '{self.api_host}'. VEYRA is local-first; API must bind to localhost (127.0.0.1). 0.0.0.0 is strictly forbidden."
            )
        if not (1024 <= self.api_port <= 65535):
            raise ConfigurationError(f"Invalid API port {self.api_port}. Must be between 1024 and 65535.")


@dataclass
class MonitoringConfig:
    """Network and system telemetry collection intervals."""
    poll_interval_seconds: float = 2.0
    ping_target: str = "1.1.1.1"
    dns_query_target: str = "google.com"
    latency_timeout_seconds: float = 1.5
    collect_wifi_metrics: bool = True
    collect_system_metrics: bool = True
    collect_gpu_metrics: bool = True

    def validate(self) -> None:
        if self.poll_interval_seconds < 0.2:
            raise ConfigurationError("Poll interval cannot be faster than 0.2s to prevent host saturation.")
        if self.latency_timeout_seconds <= 0:
            raise ConfigurationError("Latency timeout must be positive.")


@dataclass
class StorageConfig:
    """Historical aggregation and persistence parameters."""
    db_filename: str = "history.sqlite"
    ram_buffer_max_entries: int = 1800  # ~1 hour at 2s interval
    retention_tier1_minutes: int = 1440  # 0-24h: 1-min summaries
    retention_tier2_days: int = 7       # 1-7d: 5-min summaries
    retention_tier3_days: int = 30      # 7-30d: 30-min summaries
    retention_tier4_days: int = 365     # 30d-1yr: hourly summaries
    daily_retention_days: int = 730     # >1yr: daily summaries up to 2 years
    max_storage_size_mb: int = 50       # Configurable limits: 25, 50, 100, 250, 500, 1000 MB, custom
    wal_mode: bool = True
    busy_timeout_ms: int = 5000
    downsample_threshold_pct: float = 90.0  # Storage pressure trigger
    protect_critical_incidents: bool = True

    def validate(self) -> None:
        if self.ram_buffer_max_entries < 100:
            raise ConfigurationError("RAM buffer size too small to ensure aggregation stability.")
        if self.max_storage_size_mb < 10:
            raise ConfigurationError("Maximum storage size cannot be less than 10 MB.")
        if not (100 <= self.busy_timeout_ms <= 60000):
            raise ConfigurationError("Busy timeout must be between 100ms and 60000ms.")


@dataclass
class DiagnosticsConfig:
    """Safe limits for active diagnostics."""
    max_trace_hops: int = 30
    diagnostic_timeout_seconds: float = 15.0
    allow_raw_packet_capture: bool = False  # Strict privacy rule: packet capture disabled

    def validate(self) -> None:
        if self.allow_raw_packet_capture:
            raise SecurityViolationError("Raw packet capture violates VEYRA privacy contract.")
        if self.diagnostic_timeout_seconds <= 0:
            raise ConfigurationError("Diagnostic timeout must be positive.")


@dataclass
class GamingConfig:
    """Gaming Mode specific parameters."""
    high_polling_rate_seconds: float = 0.5
    alert_jitter_threshold_ms: float = 20.0
    alert_packet_loss_threshold_pct: float = 1.0
    overlay_enabled: bool = False


@dataclass
class UIPreferences:
    """User interface themes and view configurations."""
    theme: str = "dark"  # "dark", "light", "system"
    mode: str = "normal"  # "normal", "gaming"
    chart_window_minutes: int = 60

    def validate(self) -> None:
        if self.theme not in {"dark", "light", "system"}:
            raise ConfigurationError(f"Invalid theme '{self.theme}'. Must be 'dark', 'light', or 'system'.")
        if self.mode not in {"normal", "gaming"}:
            raise ConfigurationError(f"Invalid mode '{self.mode}'. Must be 'normal' or 'gaming'.")


@dataclass
class DevTestConfig:
    """Development and testing overrides."""
    simulate_network_disconnect: bool = False
    mock_hardware_sensors: bool = False
    strict_contracts_enforced: bool = True


@dataclass
class VeyraConfig:
    """Master configuration encapsulating all separated domains."""
    app: AppConfig = field(default_factory=AppConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    diagnostics: DiagnosticsConfig = field(default_factory=DiagnosticsConfig)
    gaming: GamingConfig = field(default_factory=GamingConfig)
    ui: UIPreferences = field(default_factory=UIPreferences)
    dev_test: DevTestConfig = field(default_factory=DevTestConfig)

    def validate(self) -> None:
        """Validate all sub-configurations."""
        self.app.validate()
        self.monitoring.validate()
        self.storage.validate()
        self.diagnostics.validate()
        self.ui.validate()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VeyraConfig":
        return cls(
            app=AppConfig(**data.get("app", {})),
            monitoring=MonitoringConfig(**data.get("monitoring", {})),
            storage=StorageConfig(**data.get("storage", {})),
            diagnostics=DiagnosticsConfig(**data.get("diagnostics", {})),
            gaming=GamingConfig(**data.get("gaming", {})),
            ui=UIPreferences(**data.get("ui", {})),
            dev_test=DevTestConfig(**data.get("dev_test", {})),
        )


def load_default_config() -> VeyraConfig:
    config = VeyraConfig()
    config.validate()
    return config
