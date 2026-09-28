"""
VEYRA Security & Privacy Protection Foundation.
Enforces local-first constraints, safe execution policies, path traversal defense,
subprocess execution hardening, and privacy boundaries.
"""
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from app.core.exceptions import SecurityViolationError

ALLOWED_LOCALHOST_IPS: Set[str] = {"127.0.0.1", "localhost", "::1"}

# Approved executable commands that VEYRA subsystems are permitted to invoke
ALLOWED_EXECUTABLES: Set[str] = {
    "ping",
    "ping.exe",
    "powershell",
    "powershell.exe",
    "netsh",
    "netsh.exe",
    "ipconfig",
    "ipconfig.exe",
    "systeminfo",
    "systeminfo.exe",
    "powercfg",
    "powercfg.exe",
    "nvidia-smi",
    "nvidia-smi.exe",
    "wmic",
    "wmic.exe",
    "python",
    "python.exe",
}

# Maximum allowed subprocess stdout/stderr capture size (64 KB)
MAX_SUBPROCESS_OUTPUT_BYTES = 65536

# Dangerous shell characters that indicate potential command injection
SHELL_INJECTION_PATTERN = re.compile(r"[\x00\r\n;&|`$<>]")

# CSV formula injection prefixes
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def validate_local_binding(host: str) -> None:
    """Ensures server bindings never expose VEYRA to external networks."""
    if host not in ALLOWED_LOCALHOST_IPS:
        raise SecurityViolationError(
            f"Binding to '{host}' is forbidden. VEYRA is strictly local-first and must bind only to 127.0.0.1 or localhost."
        )


def validate_safe_path(target_path: Path, base_directory: Path) -> Path:
    """
    Prevents directory traversal attacks by verifying that target_path
    resolves strictly within base_directory.
    Rejects null bytes, directory escape attempts, and traversal markers.
    """
    raw_str = str(target_path)
    if "\x00" in raw_str:
        raise SecurityViolationError("Path contains prohibited null byte.")

    try:
        resolved_base = base_directory.resolve(strict=True)
    except FileNotFoundError:
        resolved_base = base_directory.resolve()

    resolved_target = target_path.resolve()

    try:
        resolved_target.relative_to(resolved_base)
    except ValueError:
        raise SecurityViolationError(
            f"Path traversal detected: '{target_path}' escapes base directory '{base_directory}'."
        )

    return resolved_target


def safe_resolve_path(base_directory: Union[str, Path], user_path: Union[str, Path]) -> Path:
    """
    Safely resolves a user- or API-supplied path relative to a trusted base directory.
    Strictly forbids directory escapes (../), UNC paths, alternate data streams, and null bytes.
    """
    path_str = str(user_path)
    if "\x00" in path_str:
        raise SecurityViolationError("Path contains prohibited null byte.")

    # Reject UNC paths (\\server\share)
    if path_str.startswith("\\\\") or path_str.startswith("//"):
        raise SecurityViolationError(f"UNC network paths are prohibited: '{user_path}'")

    # Reject alternate data streams (e.g., file.txt:stream)
    # Exclude drive letter colon (e.g., C:\)
    stripped = path_str
    if len(stripped) >= 2 and stripped[1] == ":" and stripped[0].isalpha():
        stripped = stripped[2:]
    if ":" in stripped:
        raise SecurityViolationError(f"Alternate data streams are prohibited: '{user_path}'")

    base = Path(base_directory)
    target = Path(user_path)

    if target.is_absolute():
        resolved_target = target.resolve()
    else:
        resolved_target = (base / target).resolve()

    return validate_safe_path(resolved_target, base)


def sanitize_csv_cell(value: Any) -> str:
    """
    Sanitizes values exported to CSV to prevent spreadsheet formula injection.
    Prefixes values starting with =, +, -, @, tab, or carriage return with a single quote.
    """
    val_str = str(value) if value is not None else ""
    if val_str.startswith(CSV_FORMULA_PREFIXES):
        return f"'{val_str}"
    return val_str


def sanitize_log_string(text: str) -> str:
    """
    Sanitizes untrusted strings (process names, SSIDs, targets) before logging
    to prevent log injection and terminal escape sequence manipulation.
    """
    if not isinstance(text, str):
        text = str(text)
    # Strip carriage returns and line feeds
    sanitized = text.replace("\r", " ").replace("\n", " ")
    # Strip control characters (ASCII 0-31 except tab)
    sanitized = "".join(ch if (ord(ch) >= 32 or ch == "\t") else "?" for ch in sanitized)
    return sanitized


def run_safe_subprocess(
    command_args: List[str],
    timeout_seconds: float = 10.0,
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    enforce_allowlist: bool = True
) -> subprocess.CompletedProcess:
    """
    Executes an external system command safely.
    - Forces shell=False to prevent shell injection.
    - Requires command_args as a list of strings.
    - Enforces binary allowlist validation.
    - Inspects arguments for dangerous shell injection characters.
    - Truncates oversized stdout/stderr to eliminate memory exhaustion.
    - Enforces strict execution timeout.
    """
    if not isinstance(command_args, list) or not command_args:
        raise SecurityViolationError("Command must be a non-empty list of argument strings.")

    for arg in command_args:
        if not isinstance(arg, str):
            raise SecurityViolationError(f"Command argument must be a string, got: {type(arg)}")
        if "\x00" in arg:
            raise SecurityViolationError("Command argument contains prohibited null byte.")

    executable_token = command_args[0].strip()
    exe_name = Path(executable_token).name.lower()

    if enforce_allowlist and exe_name not in ALLOWED_EXECUTABLES:
        raise SecurityViolationError(
            f"Executable '{exe_name}' is not in the approved VEYRA subprocess allowlist: {sorted(ALLOWED_EXECUTABLES)}"
        )

    # Check for shell metacharacters in subsequent arguments
    for arg in command_args[1:]:
        if SHELL_INJECTION_PATTERN.search(arg):
            raise SecurityViolationError(f"Potential shell injection metacharacter detected in argument: {arg}")

    try:
        proc = subprocess.Popen(
            command_args,
            shell=False,  # STRICT: never allow shell interpretation
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(cwd) if cwd else None,
            env=env
        )

        try:
            stdout_data, stderr_data = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as e:
            proc.kill()
            proc.communicate()
            raise SecurityViolationError(
                f"Command '{command_args[0]}' exceeded execution timeout limit of {timeout_seconds}s."
            ) from e

        # Truncate output if exceeding maximum safe buffer size
        if stdout_data and len(stdout_data.encode("utf-8", errors="ignore")) > MAX_SUBPROCESS_OUTPUT_BYTES:
            stdout_data = stdout_data[:MAX_SUBPROCESS_OUTPUT_BYTES] + "\n[OUTPUT_TRUNCATED_BY_SECURITY_GUARD]"

        if stderr_data and len(stderr_data.encode("utf-8", errors="ignore")) > MAX_SUBPROCESS_OUTPUT_BYTES:
            stderr_data = stderr_data[:MAX_SUBPROCESS_OUTPUT_BYTES] + "\n[OUTPUT_TRUNCATED_BY_SECURITY_GUARD]"

        return subprocess.CompletedProcess(
            args=command_args,
            returncode=proc.returncode,
            stdout=stdout_data,
            stderr=stderr_data
        )

    except FileNotFoundError as e:
        raise SecurityViolationError(
            f"Command executable '{command_args[0]}' not found on host."
        ) from e


class SecretScanner:
    """
    Centralized scanner for detecting and redacting credentials, tokens,
    API keys, cookies, and private cryptographic keys from data structures.
    """

    SECRET_KEYS: Set[str] = {
        "password", "passwd", "token", "secret", "auth", "credential",
        "private_key", "access_key", "api_key", "cookie", "session_id", "jwt"
    }

    SECRET_PATTERNS = [
        re.compile(r"(?i)(bearer\s+[a-zA-Z0-9_\-\.]{12,})"),
        re.compile(r"(?i)(password\s*[:=]\s*[^\s,;]+)"),
        re.compile(r"(?i)(api[_-]?key\s*[:=]\s*[^\s,;]+)"),
        re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
    ]

    @classmethod
    def scan_string(cls, text: str) -> bool:
        """Returns True if any secret pattern or keyword match is detected."""
        if not text or not isinstance(text, str):
            return False
        for pattern in cls.SECRET_PATTERNS:
            if pattern.search(text):
                return True
        return False

    @classmethod
    def redact_data(cls, data: Any) -> Any:
        """
        Recursively redacts sensitive keys and values from dictionaries,
        lists, and strings, replacing secrets with '[REDACTED]'.
        """
        if isinstance(data, dict):
            redacted_dict = {}
            for k, v in data.items():
                k_str = str(k).lower()
                if any(sec in k_str for sec in cls.SECRET_KEYS):
                    redacted_dict[k] = "[REDACTED]"
                else:
                    redacted_dict[k] = cls.redact_data(v)
            return redacted_dict

        elif isinstance(data, (list, tuple)):
            res = [cls.redact_data(item) for item in data]
            return tuple(res) if isinstance(data, tuple) else res

        elif isinstance(data, str):
            val = data
            for pattern in cls.SECRET_PATTERNS:
                val = pattern.sub("[REDACTED]", val)
            return val

        return data
