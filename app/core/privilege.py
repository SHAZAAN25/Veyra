"""
VEYRA Stage 6 Privilege Separation & Helper Architecture.
Enforces least privilege: runs main VEYRA process without admin rights and
isolates operations requiring elevation behind an explicit allowlist and
one-time authorization tokens.
"""
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Any, Callable, Dict, Optional, Set
import uuid

from app.core.exceptions import SecurityViolationError
from app.core.security import run_safe_subprocess
from app.core.time import now_utc_iso

logger = logging.getLogger("veyra.core.privilege")


class PrivilegedOperationId(str, Enum):
    DNS_CACHE_FLUSH = "OP_DNS_CACHE_FLUSH"
    PROCESS_PRIORITY_HINT = "OP_PROCESS_PRIORITY_HINT"
    POWER_SCHEME_TUNE = "OP_POWER_SCHEME_TUNE"


@dataclass
class PrivilegeAuthorizationToken:
    """One-time authorization token for a bounded privileged operation."""
    token_id: str
    nonce: str
    operation_id: PrivilegedOperationId
    parameters: Dict[str, Any]
    timestamp_utc: str
    expires_at_monotonic: float
    user_approved: bool = False
    caller_process_id: Optional[int] = None


class PrivilegeError(SecurityViolationError):
    """Raised when a privileged operation violates security or authorization policies."""
    pass


def _validate_dns_flush_params(params: Dict[str, Any]) -> None:
    # DNS flush accepts zero or empty parameters
    if params and any(params.values()):
        raise PrivilegeError("DNS Cache Flush accepts no additional parameters.")


def _validate_process_priority_params(params: Dict[str, Any]) -> None:
    if "process_name" not in params:
        raise PrivilegeError("Parameter 'process_name' is required.")
    proc = str(params["process_name"]).lower()
    # Reject critical system processes
    protected = {"csrss.exe", "lsass.exe", "smss.exe", "services.exe", "explorer.exe", "winlogon.exe"}
    if proc in protected:
        raise PrivilegeError(f"Cannot adjust priority of protected system process: '{proc}'")
    priority = params.get("priority", "below_normal").lower()
    if priority not in ("idle", "below_normal", "normal", "above_normal", "high"):
        raise PrivilegeError(f"Invalid priority class: '{priority}'")


def _validate_power_scheme_params(params: Dict[str, Any]) -> None:
    scheme = params.get("scheme_guid", "").strip().lower()
    # Known Windows standard GUIDs
    allowed_guids = {
        "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",  # High Performance
        "381b4222-f694-41f0-9685-ff5bb260df2e",  # Balanced
        "a1841308-3541-4fab-bc81-f71556f20b4a",  # Power Saver
    }
    if scheme not in allowed_guids and scheme not in ("high", "balanced", "powersaver"):
        raise PrivilegeError(f"Invalid or untrusted power scheme GUID/name: '{scheme}'")


# Strict Allowlist of privileged operations with validation rules
PRIVILEGED_ALLOWLIST: Dict[PrivilegedOperationId, Dict[str, Any]] = {
    PrivilegedOperationId.DNS_CACHE_FLUSH: {
        "description": "Flushes local Windows DNS resolver cache",
        "validator": _validate_dns_flush_params,
        "command_generator": lambda params: ["ipconfig", "/flushdns"],
    },
    PrivilegedOperationId.PROCESS_PRIORITY_HINT: {
        "description": "Adjusts priority of a background non-system worker process",
        "validator": _validate_process_priority_params,
        "command_generator": lambda params: [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"Get-Process -Name {params['process_name']} -ErrorAction SilentlyContinue | ForEach-Object {{ $_.PriorityClass = '{params.get('priority', 'BelowNormal')}' }}"
        ],
    },
    PrivilegedOperationId.POWER_SCHEME_TUNE: {
        "description": "Sets active Windows power scheme",
        "validator": _validate_power_scheme_params,
        "command_generator": lambda params: [
            "powercfg",
            "/setactive",
            params.get("scheme_guid", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
        ],
    },
}


class PrivilegedHelper:
    """
    Isolated helper for executing allowlisted, pre-authorized system operations.
    Enforces single-use token consumption (anti-replay) and parameter validation.
    """

    TOKEN_TTL_SECONDS = 60.0

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self._consumed_nonces: Set[str] = set()

    def issue_authorization_token(
        self,
        operation_id: PrivilegedOperationId,
        parameters: Dict[str, Any],
        user_approved: bool = True,
        caller_process_id: Optional[int] = None,
    ) -> PrivilegeAuthorizationToken:
        """Issues a one-time authorization token with strict TTL and nonce."""
        if not user_approved:
            raise PrivilegeError("Cannot issue privilege authorization without explicit user approval.")

        if operation_id not in PRIVILEGED_ALLOWLIST:
            raise PrivilegeError(f"Operation '{operation_id}' is not in the privileged allowlist.")

        # Run pre-validation on parameters
        validator = PRIVILEGED_ALLOWLIST[operation_id]["validator"]
        validator(parameters)

        token = PrivilegeAuthorizationToken(
            token_id=f"privtok_{uuid.uuid4().hex[:12]}",
            nonce=uuid.uuid4().hex,
            operation_id=operation_id,
            parameters=parameters,
            timestamp_utc=now_utc_iso(),
            expires_at_monotonic=time.monotonic() + self.TOKEN_TTL_SECONDS,
            user_approved=user_approved,
            caller_process_id=caller_process_id,
        )
        logger.info(f"Issued privilege authorization token {token.token_id} for op {operation_id}")
        return token

    def execute_operation(self, token: PrivilegeAuthorizationToken) -> Dict[str, Any]:
        """
        Executes the privileged operation if authorization token is valid and unused.
        """
        if not token.user_approved:
            raise PrivilegeError("Execution denied: User approval is required.")

        # Anti-replay check
        if token.nonce in self._consumed_nonces:
            raise PrivilegeError(f"Replay attack detected: Nonce '{token.nonce}' has already been consumed.")

        # Expiration check
        if time.monotonic() > token.expires_at_monotonic:
            raise PrivilegeError(f"Authorization token '{token.token_id}' has expired.")

        # Consume nonce immediately
        self._consumed_nonces.add(token.nonce)

        # Allowlist check
        if token.operation_id not in PRIVILEGED_ALLOWLIST:
            raise PrivilegeError(f"Operation '{token.operation_id}' is not in the privileged allowlist.")

        spec = PRIVILEGED_ALLOWLIST[token.operation_id]
        spec["validator"](token.parameters)

        cmd = spec["command_generator"](token.parameters)
        logger.info(f"Executing privileged helper operation {token.operation_id} (dry_run={self.dry_run})")

        if self.dry_run:
            return {
                "status": "success",
                "operation_id": token.operation_id.value,
                "executed_command": cmd,
                "dry_run": True,
                "message": "Sandboxed dry-run simulation completed successfully.",
            }

        proc = run_safe_subprocess(cmd, timeout_seconds=10.0)
        return {
            "status": "success",
            "operation_id": token.operation_id.value,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "dry_run": False,
        }
