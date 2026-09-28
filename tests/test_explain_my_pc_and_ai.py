"""
Stage 5 Unit Tests: Explain My PC & Ask Veyra AI Architecture.
Verifies deterministic report generation, offline QA capability, intent parsing,
citation traceability, unknown facts handling, and strict hallucination prevention.
"""
from pathlib import Path
import tempfile
import unittest

from analyzer.ai.ask_veyra import AskVeyraEngine
from analyzer.ai.contracts import AIProvider, ResponseClassification
from analyzer.ai.explain_my_pc import ExplainMyPCEngine
from analyzer.contracts import (
    BottleneckCandidate,
    ChangeEvent,
    DetailedIncident,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)
from app.core.contracts import Measurement, MetricState, MetricUnit, Observation
from storage.engine import StorageEngine


def make_obs(metrics: dict) -> Observation:
    measurements = {}
    for k, v in metrics.items():
        measurements[k] = Measurement(
            metric_name=k,
            state=MetricState.AVAILABLE if v is not None else MetricState.UNAVAILABLE,
            value=v,
            unit=MetricUnit.PERCENTAGE,
            source_collector="test",
            provenance="test",
        )
    return Observation(
        observation_id="obs_ai_test",
        timestamp_utc="2026-09-28T12:00:00Z",
        collector_name="test",
        measurements=measurements,
        collector_healthy=True,
    )


class MockCustomAIProvider(AIProvider):
    """Optional adapter mock."""
    def generate_grounded_answer(self, package, user_question: str):
        return f"Enhanced by local LLM: {package.summary}"


class TestExplainMyPcAndAi(unittest.TestCase):
    """Tests Explain My PC and Ask Veyra."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_ai.sqlite")
        self.storage = StorageEngine(self.db_path)
        self.explain_engine = ExplainMyPCEngine()
        self.ask_engine = AskVeyraEngine(storage=self.storage)

    def tearDown(self):
        self.storage.sqlite.close()
        self.temp_dir.cleanup()

    def test_explain_my_pc_structure(self):
        obs = {
            "cpu": make_obs({"cpu_utilization_pct": 92.0}),
            "memory": make_obs({"ram_utilization_pct": 75.0}),
            "internet": make_obs({"internet_latency_ms": 18.0, "internet_packet_loss_pct": 0.0}),
        }
        baselines = {"cpu_utilization_pct": 40.0, "internet_latency_ms": 15.0}
        bottlenecks = [
            BottleneckCandidate(
                component="CPU",
                classification="OBSERVED",
                confidence=0.85,
                rationale="CPU at 92%",
            )
        ]

        report = self.explain_engine.generate_explanation(
            observations=obs,
            baselines=baselines,
            bottlenecks=bottlenecks,
        )

        self.assertIn("CURRENT STATE", report.raw_markdown)
        self.assertIn("OBSERVED CHANGES", report.raw_markdown)
        self.assertIn("IMPORTANT EVENTS", report.raw_markdown)
        self.assertIn("LIKELY CONTRIBUTING FACTORS", report.raw_markdown)
        self.assertIn("EVIDENCE", report.raw_markdown)
        self.assertIn("WHAT IS UNKNOWN", report.raw_markdown)
        self.assertGreater(len(report.evidence_points), 0)
        # Missing thermal sensor must be listed in what_is_unknown
        self.assertTrue(any("thermal" in u.lower() for u in report.what_is_unknown))

    def test_ask_veyra_latency_query_with_citations(self):
        obs = {
            "internet": make_obs({"internet_latency_ms": 78.5, "internet_packet_loss_pct": 1.0})
        }
        baselines = {"internet_latency_ms": 25.0}

        resp = self.ask_engine.answer_question(
            user_question="What is my current latency?",
            observations=obs,
            baselines=baselines,
        )

        self.assertEqual(resp.response_type, ResponseClassification.OBSERVED)
        self.assertIn("78.5 ms", resp.answer)
        self.assertIn("higher than your established baseline", resp.answer)
        self.assertGreater(len(resp.citations), 0)
        self.assertTrue(any("78.5 ms" in c for c in resp.citations))

    def test_ask_veyra_bottleneck_query(self):
        obs = {
            "cpu": make_obs({"cpu_utilization_pct": 95.0}),
            "memory": make_obs({"ram_utilization_pct": 60.0}),
        }
        bottlenecks = [
            BottleneckCandidate(
                component="CPU",
                classification="OBSERVED",
                confidence=0.88,
                rationale="Processor is saturated at 95%",
            )
        ]

        resp = self.ask_engine.answer_question(
            user_question="Is my PC experiencing a bottleneck?",
            observations=obs,
            bottlenecks=bottlenecks,
        )

        self.assertEqual(resp.response_type, ResponseClassification.CORRELATED)
        self.assertIn("CPU", resp.answer)
        self.assertTrue(any("CPU" in c for c in resp.citations))

    def test_ask_veyra_incident_query(self):
        incident = DetailedIncident(
            incident_id="inc_4321",
            incident_type=IncidentType.GATEWAY_UNREACHABLE,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.ACTIVE,
            started_at_utc="2026-09-28T12:00:00Z",
            summary="Default gateway is unresponsive",
        )

        resp = self.ask_engine.answer_question(
            user_question="What incidents happened recently?",
            observations={},
            active_incidents=[incident],
        )

        self.assertEqual(resp.response_type, ResponseClassification.OBSERVED)
        self.assertIn("GATEWAY_UNREACHABLE", resp.answer)
        self.assertTrue(any("inc_4321" in c for c in resp.citations))

    def test_ask_veyra_unsupported_question_hallucination_protection(self):
        resp = self.ask_engine.answer_question(
            user_question="Who will win the World Cup in 2026?",
            observations={},
        )
        # Must refuse and state lack of evidence; no hallucination
        self.assertEqual(resp.response_type, ResponseClassification.UNSUPPORTED)
        self.assertIn("I don't have enough evidence to determine that", resp.answer)
        self.assertGreater(len(resp.unknowns), 0)

    def test_ask_veyra_optional_provider_hook(self):
        mock_provider = MockCustomAIProvider()
        engine_with_provider = AskVeyraEngine(storage=self.storage, optional_provider=mock_provider)

        obs = {"internet": make_obs({"internet_latency_ms": 20.0})}
        resp = engine_with_provider.answer_question("latency query", obs)
        self.assertIn("Enhanced by local LLM", resp.answer)


if __name__ == "__main__":
    unittest.main()
