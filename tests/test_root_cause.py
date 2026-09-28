"""
Tests for VEYRA Layered Network Topology and Deterministic Root-Cause Evaluator.
"""
import unittest

from app.core.contracts import Observation, Measurement, MetricState, MetricUnit
from analyzer.contracts import (
    DetailedIncident,
    IncidentType,
    IncidentSeverity,
    IncidentStatus,
    RootCauseCategory
)
from analyzer.root_cause.topology import NetworkTopologyTracker, TopologyNodeState
from analyzer.root_cause.evaluator import RootCauseEvaluator


class TestRootCauseAnalysis(unittest.TestCase):
    def setUp(self):
        self.topology = NetworkTopologyTracker()
        self.evaluator = RootCauseEvaluator(self.topology)

    def test_gateway_failure_root_cause(self):
        # Topology: Gateway is FAILED
        self.topology.nodes["gateway"].state = TopologyNodeState.FAILED

        incident = DetailedIncident(
            incident_id="inc_01",
            incident_type=IncidentType.GATEWAY_UNREACHABLE,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.ACTIVE,
            started_at_utc="2026-09-28T00:00:00Z"
        )
        rc = self.evaluator.evaluate_incident_root_cause(incident, {})
        self.assertEqual(rc.primary_cause, RootCauseCategory.GATEWAY_LOCAL_NETWORK)
        self.assertEqual(rc.relationship, "OBSERVED")
        self.assertGreaterEqual(rc.confidence_score, 0.9)
        self.assertIn("cannot be reliably assessed", rc.explanation)

    def test_dns_failure_when_gateway_is_healthy(self):
        self.topology.nodes["gateway"].state = TopologyNodeState.HEALTHY
        self.topology.nodes["dns"].state = TopologyNodeState.FAILED

        incident = DetailedIncident(
            incident_id="inc_02",
            incident_type=IncidentType.DNS_FAILURE,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.ACTIVE,
            started_at_utc="2026-09-28T00:00:00Z"
        )
        rc = self.evaluator.evaluate_incident_root_cause(incident, {})
        self.assertEqual(rc.primary_cause, RootCauseCategory.DNS_SUBSYSTEM)
        self.assertEqual(rc.relationship, "OBSERVED")
        self.assertGreaterEqual(rc.confidence_score, 0.85)

    def test_upstream_internet_failure_when_gateway_healthy(self):
        self.topology.nodes["gateway"].state = TopologyNodeState.HEALTHY
        self.topology.nodes["internet"].state = TopologyNodeState.FAILED

        incident = DetailedIncident(
            incident_id="inc_03",
            incident_type=IncidentType.INTERNET_UNREACHABLE,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.ACTIVE,
            started_at_utc="2026-09-28T00:00:00Z"
        )
        rc = self.evaluator.evaluate_incident_root_cause(incident, {})
        self.assertEqual(rc.primary_cause, RootCauseCategory.UPSTREAM_INTERNET)
        self.assertEqual(rc.relationship, "PROBABLE")

    def test_cause_undetermined_is_valid_result(self):
        # All topology healthy, transient latency spike with no clear root fault
        self.topology.nodes["gateway"].state = TopologyNodeState.HEALTHY
        self.topology.nodes["internet"].state = TopologyNodeState.HEALTHY

        incident = DetailedIncident(
            incident_id="inc_04",
            incident_type=IncidentType.LATENCY_SPIKE,
            severity=IncidentSeverity.WARNING,
            status=IncidentStatus.ACTIVE,
            started_at_utc="2026-09-28T00:00:00Z"
        )
        rc = self.evaluator.evaluate_incident_root_cause(incident, {})
        self.assertEqual(rc.primary_cause, RootCauseCategory.CAUSE_UNDETERMINED)
        self.assertEqual(rc.relationship, "UNDETERMINED")
        self.assertLess(rc.confidence_score, 0.5)


if __name__ == "__main__":
    unittest.main()
