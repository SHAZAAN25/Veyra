"""
VEYRA Structured Logging Engine.
Provides JSON-structured and formatted logging with automatic redaction of sensitive
tokens, secrets, and credentials. Logging failures never crash the application.
"""
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|secret|token|api[_-]?key|auth|bearer)[\s:=]+['\"]?([^\s'\",&]+)"),
    re.compile(r"(?i)(private[_-]?key|certificate)[\s:=]+['\"]?([^\s'\",&]+)"),
]


def redact_sensitive_data(text: str) -> str:
    """Masks tokens, secrets, and credentials found in strings."""
    if not isinstance(text, str):
        return text
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1=***REDACTED***", redacted)
    return redacted


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON entries."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp_utc = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        component = getattr(record, "component", record.name)
        event = getattr(record, "event", "GENERIC_LOG")
        details = getattr(record, "details", {})

        # Redact message and details
        msg = redact_sensitive_data(record.getMessage())
        safe_details = {}
        if isinstance(details, dict):
            for k, v in details.items():
                if isinstance(v, str):
                    safe_details[k] = redact_sensitive_data(v)
                else:
                    safe_details[k] = v
        else:
            safe_details = {"raw": str(details)}

        payload = {
            "timestamp": timestamp_utc,
            "severity": record.levelname,
            "component": component,
            "event": event,
            "message": msg,
        }

        if safe_details:
            payload["details"] = safe_details

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        try:
            return json.dumps(payload)
        except Exception:
            # Fallback that will never raise
            return f'{{"timestamp": "{timestamp_utc}", "severity": "{record.levelname}", "component": "{component}", "message": "{msg}"}}'


class SafeLogger:
    """Wrapper around logging.Logger ensuring logging calls never crash the application."""

    def __init__(self, logger: logging.Logger, component: str):
        self._logger = logger
        self.component = component

    def log(self, level: int, event: str, message: str, details: Optional[Dict[str, Any]] = None, exc_info=None):
        try:
            extra = {"component": self.component, "event": event, "details": details or {}}
            self._logger.log(level, message, extra=extra, exc_info=exc_info)
        except Exception as e:
            try:
                # Emergency standard error write
                sys.stderr.write(f"[VEYRA LOGGING FAILURE] {e}\n")
            except Exception:
                pass

    def debug(self, event: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.log(logging.DEBUG, event, message, details)

    def info(self, event: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.log(logging.INFO, event, message, details)

    def warning(self, event: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.log(logging.WARNING, event, message, details)

    def error(self, event: str, message: str, details: Optional[Dict[str, Any]] = None, exc_info=None):
        self.log(logging.ERROR, event, message, details, exc_info=exc_info)

    def critical(self, event: str, message: str, details: Optional[Dict[str, Any]] = None, exc_info=None):
        self.log(logging.CRITICAL, event, message, details, exc_info=exc_info)


def get_logger(component: str = "core") -> SafeLogger:
    """Factory to get a configured SafeLogger instance."""
    logger = logging.getLogger(f"veyra.{component}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return SafeLogger(logger, component)
