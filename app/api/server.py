"""
VEYRA Localhost HTTP API Server.
Binds strictly to loopback (127.0.0.1) using ThreadingHTTPServer.
Rejects all non-localhost requests, validates Host headers (anti-DNS rebinding),
and enforces request body size limits to uphold local-first security invariants.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading
from typing import Optional

from app.core.config import VeyraConfig, ALLOWED_LOCAL_HOSTS
from app.core.exceptions import SecurityViolationError
from app.api.routes import ApiRouteDispatcher

logger = logging.getLogger("veyra.api.server")

# Maximum allowed incoming JSON request body size: 1 MB
MAX_REQUEST_BODY_BYTES = 1048576

ALLOWED_HOST_HEADERS = {
    "127.0.0.1",
    "localhost",
    "::1",
}


class _ApiRequestHandler(BaseHTTPRequestHandler):
    """Internal HTTP request handler enforcing localhost client verification."""

    dispatcher: ApiRouteDispatcher

    def _verify_localhost(self) -> bool:
        """Enforces that the client request originates strictly from loopback."""
        client_ip = self.client_address[0]
        if client_ip not in ALLOWED_LOCAL_HOSTS:
            logger.warning(f"Forbidden connection attempt from non-local address: {client_ip}")
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "error", "error": {"code": "FORBIDDEN", "message": "Access denied. Localhost only."}}')
            return False

        # DNS Rebinding Defense: Validate Host header
        host_header = self.headers.get("Host", "").split(":")[0].strip().lower()
        if host_header and host_header not in ALLOWED_HOST_HEADERS:
            logger.warning(f"DNS Rebinding attempt detected: Invalid Host header '{host_header}' from {client_ip}")
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "error", "error": {"code": "FORBIDDEN", "message": "Access denied. Invalid Host header."}}')
            return False

        return True

    def do_GET(self):
        if not self._verify_localhost():
            return
        status, response_dict = self.dispatcher.handle_request(
            method="GET",
            url_path=self.path,
            headers=dict(self.headers),
            client_ip=self.client_address[0]
        )
        self._send_json(status, response_dict)

    def do_POST(self):
        if not self._verify_localhost():
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_REQUEST_BODY_BYTES:
            logger.warning(f"Payload too large: {content_length} bytes > {MAX_REQUEST_BODY_BYTES}")
            self.send_response(413)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "error", "error": {"code": "PAYLOAD_TOO_LARGE", "message": "Request body exceeds 1 MB limit."}}')
            return

        body = self.rfile.read(content_length).decode("utf-8", errors="replace") if content_length > 0 else ""
        status, response_dict = self.dispatcher.handle_request(
            method="POST",
            url_path=self.path,
            body=body,
            headers=dict(self.headers),
            client_ip=self.client_address[0]
        )
        self._send_json(status, response_dict)

    def _send_json(self, status: int, data: dict):
        body_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, format, *args):
        # Suppress noisy standard HTTP access logs
        pass


class LocalApiServer:
    """Threaded localhost-only API server."""

    def __init__(self, config: VeyraConfig, dispatcher: ApiRouteDispatcher):
        if config.app.api_host not in ALLOWED_LOCAL_HOSTS:
            raise SecurityViolationError(f"API server host must be in {ALLOWED_LOCAL_HOSTS}. Got: {config.app.api_host}")

        self.config = config
        self.host = config.app.api_host
        self.port = config.app.api_port
        self.dispatcher = dispatcher

        # Configure custom handler with bound dispatcher
        handler_class = type("BoundApiHandler", (_ApiRequestHandler,), {"dispatcher": self.dispatcher})
        self._server = ThreadingHTTPServer((self.host, self.port), handler_class)
        self._server.daemon_threads = True
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Starts the server in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="veyra-api-server")
        self._thread.start()
        logger.info(f"Localhost API server listening on http://{self.host}:{self.port}")

    def stop(self) -> None:
        """Stops the server gracefully."""
        if not self._running:
            return
        self._running = False
        self._server.shutdown()
        self._server.server_close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
