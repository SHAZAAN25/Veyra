"""
VEYRA Localhost API Route Handlers.
Implements the exact JSON response envelopes and endpoints defined in API_CONTRACT.md.
Provides secure, authenticated, and rate-limited access to telemetry and diagnostics.
"""
import json
import logging
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from app.api.auth import (
    ApiAuthenticationError,
    ApiRateLimitExceededError,
    ApiRateLimiter,
    ApiSecurityLevel,
    ApiTokenManager,
    EndpointPolicyManager,
)
from app.core.config import VeyraConfig
from app.core.time import now_utc_iso
from storage.engine import StorageEngine

logger = logging.getLogger("veyra.api.routes")


def success_envelope(data: Any, version: str = "0.1.0") -> Dict[str, Any]:
    """Wraps data in standard API_CONTRACT.md success envelope."""
    return {
        "status": "success",
        "data": data,
        "error": None,
        "timestamp_utc": now_utc_iso(),
        "server_version": version,
    }


def error_envelope(
    code: str, message: str, details: Optional[Dict[str, Any]] = None, version: str = "0.1.0"
) -> Dict[str, Any]:
    """Wraps error in standard API_CONTRACT.md error envelope."""
    return {
        "status": "error",
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "timestamp_utc": now_utc_iso(),
        "server_version": version,
    }


class ApiRouteDispatcher:
    """Dispatches HTTP requests to appropriate VEYRA telemetry and historical services."""

    def __init__(
        self,
        config: VeyraConfig,
        storage: Optional[StorageEngine] = None,
        latest_observation_fn: Optional[Any] = None,
        latest_assessment_fn: Optional[Any] = None,
        token_manager: Optional[ApiTokenManager] = None,
        rate_limiter: Optional[ApiRateLimiter] = None,
        require_auth: bool = False,
    ):
        self.config = config
        self.storage = storage or StorageEngine()
        self._get_latest_obs = latest_observation_fn or (lambda: None)
        self._get_latest_assessment = latest_assessment_fn or (lambda: None)
        self.token_manager = token_manager or ApiTokenManager()
        self.rate_limiter = rate_limiter or ApiRateLimiter()
        self.require_auth = require_auth or getattr(config.app, "api_auth_required", False)

    def handle_request(
        self,
        method: str,
        url_path: str,
        body: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        client_ip: str = "127.0.0.1",
    ) -> Tuple[int, Dict[str, Any]]:
        """Routes HTTP request to handler and returns (status_code, response_dict)."""
        parsed = urlparse(url_path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)
        headers = headers or {}

        # Case-insensitive header dictionary
        norm_headers = {k.lower(): v for k, v in headers.items()}

        sec_level = EndpointPolicyManager.get_security_level(method, path)

        # 1. Enforce Rate Limiting
        try:
            self.rate_limiter.check_rate_limit(client_ip, sec_level)
        except ApiRateLimitExceededError as e:
            return 429, error_envelope("RATE_LIMIT_EXCEEDED", str(e))

        # 2. Extract Token if present
        auth_header = norm_headers.get("authorization", "")
        token = None
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        elif "x-veyra-token" in norm_headers:
            token = norm_headers["x-veyra-token"].strip()

        # 3. Enforce Authentication if required or if token header is present
        if self.require_auth and sec_level in (
            ApiSecurityLevel.SENSITIVE_READ,
            ApiSecurityLevel.MUTATING,
            ApiSecurityLevel.PRIVILEGED,
        ):
            if not self.token_manager.verify_token(token):
                return 401, error_envelope(
                    "UNAUTHORIZED",
                    "Missing or invalid API authentication token. Localhost endpoints require Bearer token.",
                )
        elif token and not self.token_manager.verify_token(token):
            return 401, error_envelope("UNAUTHORIZED", "Invalid API token provided.")

        try:
            if method == "GET":
                if path in ("", "/api/v1/status"):
                    return 200, success_envelope({
                        "product": "VEYRA",
                        "status": "ONLINE",
                        "mode": self.config.ui.mode,
                        "theme": self.config.ui.theme,
                    })

                elif path == "/api/v1/auth/verify":
                    is_valid = self.token_manager.verify_token(token)
                    return 200, success_envelope({"authenticated": is_valid})

                elif path == "/api/v1/telemetry/current":
                    obs = self._get_latest_obs()
                    if not obs:
                        return 200, success_envelope({"observation": None, "state": "INITIALIZING"})
                    meas_dict = {
                        name: m.to_dict()
                        for name, m in obs.measurements.items()
                    }
                    return 200, success_envelope({
                        "observation_id": obs.observation_id,
                        "timestamp_utc": obs.timestamp_utc,
                        "measurements": meas_dict,
                        "collector_healthy": obs.collector_healthy,
                        "status_summary": obs.status_summary,
                    })

                elif path == "/api/v1/telemetry/assessment":
                    assessment = self._get_latest_assessment()
                    if not assessment:
                        return 200, success_envelope({
                            "health": "UNKNOWN",
                            "score": None,
                            "findings": ["Awaiting initial telemetry cycle"],
                        })
                    return 200, success_envelope({
                        "health": assessment.overall_health,
                        "score": assessment.score,
                        "findings": assessment.findings,
                        "timestamp_utc": assessment.timestamp_utc,
                    })

                elif path == "/api/v1/history/summaries":
                    metric = params.get("metric", [None])[0]
                    res_sec = int(params.get("resolution", [60])[0])
                    limit = int(params.get("limit", [100])[0])
                    records = self.storage.sqlite.query_measurement_summaries(
                        metric_name=metric,
                        resolution_seconds=res_sec,
                        limit=limit,
                    )
                    return 200, success_envelope([r.to_dict() for r in records])

                elif path == "/api/v1/history/incidents":
                    limit = int(params.get("limit", [50])[0])
                    incidents = self.storage.sqlite.query_incident_records(limit=limit)
                    return 200, success_envelope([inc.to_dict() for inc in incidents])

                elif path == "/api/v1/history/timeline":
                    limit = int(params.get("limit", [100])[0])
                    events = self.storage.timeline.query_timeline(limit=limit)
                    return 200, success_envelope([e.to_dict() for e in events])

                elif path == "/api/v1/history/baseline":
                    metric = params.get("metric", [None])[0]
                    if not metric:
                        baselines = self.storage.sqlite.list_all_baselines()
                        return 200, success_envelope([b.to_dict() for b in baselines])
                    baseline = self.storage.baselines.get_baseline(metric)
                    if not baseline:
                        return 404, error_envelope("NOT_FOUND", f"Baseline for '{metric}' not found.")
                    return 200, success_envelope({
                        "metric_name": baseline.metric_name,
                        "sample_count": baseline.sample_count,
                        "mean": baseline.mean,
                        "median": baseline.median,
                        "p95": baseline.p95,
                        "min": baseline.min_value,
                        "max": baseline.max_value,
                        "std_dev": baseline.std_dev,
                        "quality": baseline.quality.value,
                    })

                elif path == "/api/v1/history/comparison":
                    metric = params.get("metric", [None])[0]
                    comp_type = params.get("type", ["yesterday"])[0]
                    if not metric:
                        return 400, error_envelope("INVALID_PARAM", "Parameter 'metric' is required.")
                    if comp_type == "yesterday":
                        res = self.storage.comparison.compare_current_vs_yesterday(metric)
                    else:
                        res = self.storage.comparison.compare_current_vs_baseline(metric)
                    return 200, success_envelope(res)

                elif path == "/api/v1/history/replay":
                    inc_id = params.get("incident_id", [None])[0]
                    if not inc_id:
                        return 400, error_envelope("INVALID_PARAM", "Parameter 'incident_id' is required.")
                    replay = self.storage.replay.reconstruct_replay(inc_id)
                    if not replay:
                        return 404, error_envelope("NOT_FOUND", f"Incident '{inc_id}' not found.")
                    return 200, success_envelope(replay)

                elif path == "/api/v1/diagnostics/history":
                    limit = int(params.get("limit", [20])[0])
                    runs = self.storage.get_diagnostic_runs(limit=limit)
                    return 200, success_envelope([r.to_dict() for r in runs])

                elif path == "/api/v1/gaming/sessions":
                    limit = int(params.get("limit", [20])[0])
                    sessions = self.storage.get_gaming_sessions(limit=limit)
                    return 200, success_envelope([s.to_dict() for s in sessions])

                elif path == "/api/v1/config":
                    return 200, success_envelope({
                        "theme": self.config.ui.theme,
                        "mode": self.config.ui.mode,
                        "poll_interval_seconds": self.config.monitoring.poll_interval_seconds,
                        "max_storage_size_mb": self.config.storage.max_storage_size_mb,
                    })

            elif method == "POST":
                if path == "/api/v1/auth/rotate":
                    new_tok = self.token_manager.rotate_token()
                    return 200, success_envelope({"message": "Token rotated", "token": new_tok})

                elif path == "/api/v1/config/mode":
                    data = json.loads(body or "{}")
                    new_mode = data.get("mode")
                    if new_mode not in ("normal", "gaming"):
                        return 400, error_envelope("INVALID_MODE", "Mode must be 'normal' or 'gaming'.")
                    self.config.ui.mode = new_mode
                    return 200, success_envelope({"mode": self.config.ui.mode})

                elif path == "/api/v1/optimization/apply":
                    data = json.loads(body or "{}")
                    if not data.get("confirmed_by_user", False):
                        return 403, error_envelope(
                            "USER_APPROVAL_REQUIRED",
                            "Optimization execution requires explicit confirmed_by_user=True flag."
                        )
                    opp_id = data.get("opportunity_id")
                    if not opp_id:
                        return 400, error_envelope("INVALID_PARAM", "Parameter 'opportunity_id' is required.")
                    return 200, success_envelope({"opportunity_id": opp_id, "status": "QUEUED_FOR_EXECUTION"})

                elif path == "/api/v1/optimization/rollback":
                    data = json.loads(body or "{}")
                    run_id = data.get("run_id")
                    if not run_id:
                        return 400, error_envelope("INVALID_PARAM", "Parameter 'run_id' is required.")
                    return 200, success_envelope({"run_id": run_id, "status": "ROLLBACK_INITIATED"})

            return 404, error_envelope("NOT_FOUND", f"Route '{method} {path}' not found.")

        except json.JSONDecodeError:
            return 400, error_envelope("MALFORMED_JSON", "Request body must be valid JSON.")
        except Exception as e:
            logger.error(f"API routing error for {method} {path}: {e}")
            # Structured internal error without leaking internal filesystem paths or stack traces
            return 500, error_envelope("INTERNAL_ERROR", "An unexpected internal server error occurred.")
