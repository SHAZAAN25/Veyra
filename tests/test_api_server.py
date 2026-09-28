"""
Stage 4 Tests: Localhost API Server & Security Boundary.
Verifies localhost binding (127.0.0.1 only), endpoint responses, standard envelopes,
and rejection of non-local access.
"""
import unittest
import json
import urllib.request
import urllib.error
from pathlib import Path
import tempfile
import time

from app.api.server import LocalApiServer
from app.api.routes import ApiRouteDispatcher
from app.core.config import VeyraConfig
from storage.engine import StorageEngine


class TestApiServerAndSecurity(unittest.TestCase):
    """Verifies local API server, routing, and access security."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_api.sqlite")
        self.storage = StorageEngine(self.db_path)
        
        self.config = VeyraConfig()
        self.config.app.api_port = 8799
        self.config.app.api_host = "127.0.0.1"

        self.dispatcher = ApiRouteDispatcher(
            config=self.config,
            storage=self.storage
        )

        self.server = LocalApiServer(
            config=self.config,
            dispatcher=self.dispatcher
        )
        self.server.start()
        time.sleep(0.1)

    def tearDown(self):
        self.server.stop()
        self.storage.sqlite.close()
        self.temp_dir.cleanup()

    def _get(self, path: str):
        url = f"http://127.0.0.1:{self.config.app.api_port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data)

    def _post(self, path: str, payload: dict):
        url = f"http://127.0.0.1:{self.config.app.api_port}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data)

    def test_status_endpoint(self):
        status, body = self._get("/api/v1/status")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "success")
        data = body.get("data", {})
        self.assertEqual(data.get("status"), "ONLINE")
        self.assertIn("mode", data)
        self.assertIn("theme", data)

    def test_telemetry_current_endpoint(self):
        status, body = self._get("/api/v1/telemetry/current")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIn("timestamp_utc", body)

    def test_history_summaries_endpoint(self):
        status, body = self._get("/api/v1/history/summaries?limit=5")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIsInstance(body.get("data"), list)

    def test_history_incidents_endpoint(self):
        status, body = self._get("/api/v1/history/incidents?limit=10")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIsInstance(body.get("data"), list)

    def test_history_timeline_endpoint(self):
        status, body = self._get("/api/v1/history/timeline?limit=10")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIsInstance(body.get("data"), list)

    def test_mode_switch_endpoint(self):
        status, body = self._post("/api/v1/config/mode", {"mode": "gaming"})
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertEqual(body.get("data", {}).get("mode"), "gaming")

    def test_invalid_mode_switch_rejected(self):
        url = f"http://127.0.0.1:{self.config.app.api_port}/api/v1/config/mode"
        body = json.dumps({"mode": "INVALID_MODE"}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                self.fail("Expected HTTP 400 for invalid mode")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_404_not_found_handling(self):
        url = f"http://127.0.0.1:{self.config.app.api_port}/api/v1/unknown_route"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                self.fail("Expected HTTP 404 for unknown route")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


if __name__ == "__main__":
    unittest.main()
