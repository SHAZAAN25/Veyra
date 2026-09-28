"""
VEYRA Localhost API Authentication, Authorization & Rate Limiting.
Enforces zero-trust on localhost: requires cryptographically secure Bearer tokens,
constant-time verification, per-endpoint security levels, and rate limiting.
"""
from collections import defaultdict
from enum import Enum
import hmac
import logging
from pathlib import Path
import secrets
import time
from typing import Dict, List, Optional, Tuple

from app.core.exceptions import SecurityViolationError

logger = logging.getLogger("veyra.api.auth")


class ApiSecurityLevel(str, Enum):
    READ_ONLY = "READ_ONLY"             # Public operational status
    SENSITIVE_READ = "SENSITIVE_READ"   # Historical telemetry, incident logs, flight recorder
    MUTATING = "MUTATING"               # Configuration, mode switching
    PRIVILEGED = "PRIVILEGED"           # System optimizations, active diagnostics


class ApiAuthenticationError(SecurityViolationError):
    """Raised when an API request fails token authentication."""
    pass


class ApiAuthorizationError(SecurityViolationError):
    """Raised when an authenticated request lacks required authorization."""
    pass


class ApiRateLimitExceededError(SecurityViolationError):
    """Raised when client exceeds request rate limits."""
    pass


class ApiTokenManager:
    """
    Manages the lifecycle of the local API Bearer token.
    Generates, stores, rotates, and validates tokens using constant-time comparison.
    """

    def __init__(self, token_file: Optional[Path] = None):
        self.token_file = token_file or Path("config") / ".veyra_api_token"
        self._current_token: Optional[str] = None
        self._load_or_generate_token()

    def _load_or_generate_token(self) -> None:
        """Loads existing token or creates a new 256-bit cryptographically secure token."""
        try:
            if self.token_file.exists():
                token = self.token_file.read_text(encoding="utf-8").strip()
                if len(token) >= 32:
                    self._current_token = token
                    logger.info("Loaded existing API authentication token.")
                    return
        except Exception as e:
            logger.warning(f"Could not read existing API token file: {e}")

        self.rotate_token()

    def rotate_token(self) -> str:
        """Generates a new secure token, writes it to disk, and updates memory."""
        new_token = secrets.token_urlsafe(32)
        try:
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(new_token, encoding="utf-8")
            # Restrict permissions if on POSIX
            try:
                self.token_file.chmod(0o600)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to persist API token to disk: {e}")

        self._current_token = new_token
        logger.info("Rotated API authentication token successfully.")
        return new_token

    def revoke_token(self) -> None:
        """Revokes the current token immediately."""
        self._current_token = None
        try:
            if self.token_file.exists():
                self.token_file.unlink()
        except Exception as e:
            logger.warning(f"Error removing token file on revocation: {e}")

    def verify_token(self, provided_token: Optional[str]) -> bool:
        """Verifies provided token against active token in constant time."""
        if not provided_token or not self._current_token:
            return False
        return hmac.compare_digest(provided_token.strip(), self._current_token)

    @property
    def current_token(self) -> Optional[str]:
        return self._current_token


class ApiRateLimiter:
    """
    Sliding-window request rate limiter preventing request flooding and brute force.
    """

    # Default limits per 60-second window
    LIMITS: Dict[ApiSecurityLevel, int] = {
        ApiSecurityLevel.READ_ONLY: 180,
        ApiSecurityLevel.SENSITIVE_READ: 60,
        ApiSecurityLevel.MUTATING: 20,
        ApiSecurityLevel.PRIVILEGED: 10,
    }

    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        # client_ip -> level -> list of monotonic timestamps
        self._history: Dict[str, Dict[ApiSecurityLevel, List[float]]] = defaultdict(lambda: defaultdict(list))

    def check_rate_limit(self, client_ip: str, level: ApiSecurityLevel) -> None:
        """
        Records request and checks if request exceeds rate limit for the category.
        Raises ApiRateLimitExceededError if rate exceeded.
        """
        now = time.monotonic()
        limit = self.LIMITS.get(level, 60)
        bucket = self._history[client_ip][level]

        # Prune timestamps outside current window
        cutoff = now - self.window_seconds
        self._history[client_ip][level] = [t for t in bucket if t > cutoff]
        bucket = self._history[client_ip][level]

        if len(bucket) >= limit:
            logger.warning(f"Rate limit exceeded for {client_ip} on level {level.value} ({len(bucket)}/{limit})")
            raise ApiRateLimitExceededError(
                f"Rate limit exceeded for endpoint security level '{level.value}'. Limit: {limit} requests / {self.window_seconds}s."
            )

        bucket.append(now)


class EndpointPolicyManager:
    """Classifies API routes into security levels and enforces authentication."""

    ROUTE_LEVELS: Dict[Tuple[str, str], ApiSecurityLevel] = {
        # READ_ONLY
        ("GET", "/api/v1/status"): ApiSecurityLevel.READ_ONLY,
        ("GET", "/api/v1/telemetry/current"): ApiSecurityLevel.READ_ONLY,
        ("GET", "/api/v1/telemetry/assessment"): ApiSecurityLevel.READ_ONLY,

        # SENSITIVE_READ
        ("GET", "/api/v1/history/summaries"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/history/incidents"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/history/timeline"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/history/baseline"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/history/comparison"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/history/replay"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/diagnostics/history"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/gaming/sessions"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/gaming/session/current"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/optimization/opportunities"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/config"): ApiSecurityLevel.SENSITIVE_READ,
        ("GET", "/api/v1/auth/verify"): ApiSecurityLevel.SENSITIVE_READ,

        # MUTATING
        ("POST", "/api/v1/config/mode"): ApiSecurityLevel.MUTATING,
        ("POST", "/api/v1/auth/rotate"): ApiSecurityLevel.MUTATING,

        # PRIVILEGED
        ("POST", "/api/v1/diagnostics/investigate"): ApiSecurityLevel.PRIVILEGED,
        ("POST", "/api/v1/optimization/apply"): ApiSecurityLevel.PRIVILEGED,
        ("POST", "/api/v1/optimization/rollback"): ApiSecurityLevel.PRIVILEGED,
        ("POST", "/api/v1/ai/explain"): ApiSecurityLevel.SENSITIVE_READ,
        ("POST", "/api/v1/ai/ask"): ApiSecurityLevel.SENSITIVE_READ,
    }

    @classmethod
    def get_security_level(cls, method: str, path: str) -> ApiSecurityLevel:
        normalized = path.rstrip("/")
        if not normalized:
            normalized = "/api/v1/status"
        return cls.ROUTE_LEVELS.get((method.upper(), normalized), ApiSecurityLevel.SENSITIVE_READ)
