from __future__ import annotations

import json
from collections import deque

from packages.providers.base import ModelRequest, ModelResponse


class FakeProvider:
    """Deterministic scripted provider for unit tests."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = deque(responses or [])

    async def generate(self, request: ModelRequest) -> ModelResponse:
        text = self._responses.popleft() if self._responses else "{}"
        return ModelResponse(
            text=text,
            provider="fake",
            model=request.model_profile,
            latency_ms=0,
            estimated_cost=0.0,
        )


class PhaseOneFakeProvider:
    """Schema-valid deterministic provider for local tournament validation."""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if request.task_type == "research":
            niche = str(request.metadata.get("research_niche") or "CONSTRUCTIVE")
            origin = str(request.metadata.get("agent_origin") or "INITIAL")
            mutation = request.metadata.get("mutation_type")
            parent = request.metadata.get("parent_submission_id")
            mutation_suffix = (
                f" Mutation objective: {mutation}."
                if mutation is not None
                else ""
            )
            parent_suffix = (
                f" Builds from parent {str(parent)[:8]}."
                if parent is not None
                else ""
            )
            text = json.dumps(
                {
                    "summary": f"{niche.title()} research candidate",
                    "approach": (
                        f"Use the {niche.lower()} niche as a {origin.lower()} branch."
                        f"{mutation_suffix}{parent_suffix}"
                    ),
                    "claims": [
                        {
                            "statement": f"The {niche.lower()} branch produces a testable claim.",
                            "confidence": 0.75,
                            "support": f"Deterministic evidence from the {niche.lower()} niche.",
                        }
                    ],
                    "evidence": [f"synthetic {niche.lower()} evidence"],
                    "discoveries": [f"{niche.lower()} perspective remains represented"],
                    "failed_attempts": [],
                    "open_questions": [f"what would falsify the {niche.lower()} branch?"],
                    "final_answer": f"Synthetic {niche.lower()} answer.",
                }
            )
        elif request.task_type == "critic":
            text = json.dumps(
                {
                    "fatal_error": False,
                    "confidence": 0.8,
                    "critique": "No fatal flaw found by deterministic critic.",
                    "counterexample": None,
                }
            )
        elif request.task_type == "judge":
            candidate_ids = request.metadata.get("candidate_ids") or []
            text = json.dumps(
                {
                    "evaluations": [
                        {
                            "candidate_id": candidate_id,
                            "correctness": 0.8,
                            "rigor": 0.8,
                            "novelty": 0.6,
                            "research_progress": 0.7,
                            "verifiability": 0.9,
                            "fatal_error": False,
                            "judge_confidence": 0.85,
                            "critique": "Deterministic local blind evaluation.",
                        }
                        for candidate_id in candidate_ids
                    ]
                }
            )
        else:
            raise ValueError(f"Unsupported fake task type: {request.task_type}")

        return ModelResponse(
            text=text,
            provider="fake",
            model=request.model_profile,
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0.0,
        )
