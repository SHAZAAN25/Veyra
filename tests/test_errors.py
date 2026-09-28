"""
Tests for VEYRA Error Handling and Resilience.
"""
import unittest
import time

from app.core.exceptions import (
    VeyraError,
    BrandingIntegrityError,
    CollectorUnavailableError,
    CollectorPermissionError
)
from app.core.logging import get_logger
from app.core.time import TimeTracker


class TestErrorsAndResilience(unittest.TestCase):
    def test_exception_inheritance(self):
        self.assertTrue(issubclass(BrandingIntegrityError, VeyraError))
        self.assertTrue(issubclass(CollectorUnavailableError, VeyraError))
        self.assertTrue(issubclass(CollectorPermissionError, VeyraError))

    def test_safe_logger_resilience(self):
        logger = get_logger("resilience_test")
        # Logging complex or unusual objects should never crash
        logger.info("TEST_EVENT", "Normal message", {"key": "value"})
        logger.error("TEST_ERROR", "Error message", {"bad_obj": object()})

    def test_time_tracker_gap_detection(self):
        tracker = TimeTracker()
        # Normal tiny step
        elapsed, sleep_detected = tracker.check_interval(expected_interval_seconds=1.0)
        self.assertFalse(sleep_detected)
        self.assertGreaterEqual(elapsed, 0.0)

        # Simulate sleep gap by adjusting last wall time far into the past
        tracker.last_wall_time -= 100.0
        elapsed, sleep_detected = tracker.check_interval(expected_interval_seconds=1.0)
        self.assertTrue(sleep_detected)


if __name__ == "__main__":
    unittest.main()
