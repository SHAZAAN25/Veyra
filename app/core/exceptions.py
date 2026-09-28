"""
VEYRA Core Exception Hierarchy.
Provides typed exceptions for graceful error handling across all subsystems.
"""


class VeyraError(Exception):
    """Base exception for all VEYRA errors."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class BrandingIntegrityError(VeyraError):
    """Raised when locked branding assets are missing, modified, or corrupted."""
    pass


class ConfigurationError(VeyraError):
    """Raised when configuration values are missing, invalid, or violate security bounds."""
    pass


class SecurityViolationError(VeyraError):
    """Raised when an operation attempts to violate security policies (e.g. non-local binding)."""
    pass


class DataContractViolationError(VeyraError):
    """Raised when telemetry or contracts violate the absolute data integrity rule."""
    pass


class CollectorError(VeyraError):
    """Base exception for collector operations."""
    pass


class CollectorUnavailableError(CollectorError):
    """Raised when an underlying collector source or subsystem is unavailable."""
    pass


class CollectorPermissionError(CollectorError):
    """Raised when elevated or administrative permissions are required."""
    pass


class CollectorTimeoutError(CollectorError):
    """Raised when a collection attempt exceeds safe execution limits."""
    pass


class StorageError(VeyraError):
    """Raised when storage operations fail."""
    pass


class DiagnosticTimeoutError(VeyraError):
    """Raised when a diagnostic routine times out."""
    pass
