"""
VEYRA Evidence-Grounded AI Foundation Package.
Assembles verified deterministic evidence for 'Ask Veyra' and 'Explain My PC'.
STRICT INVARIANT: No LLM execution or decision-making in core analysis.
All answers are grounded strictly in Veyra's verified telemetry.
"""
from analyzer.ai.ask_veyra import AskVeyraEngine
from analyzer.ai.contracts import AIProvider, AIResponse, ResponseClassification
from analyzer.ai.evidence_package import AIEvidenceBuilder
from analyzer.ai.explain_my_pc import ExplainMyPCEngine, ExplainMyPCReport

__all__ = [
    "AIEvidenceBuilder",
    "AIProvider",
    "AIResponse",
    "ResponseClassification",
    "ExplainMyPCEngine",
    "ExplainMyPCReport",
    "AskVeyraEngine",
]
