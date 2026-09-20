from __future__ import annotations

import json

from packages.core.domain.models import Problem
from packages.core.orchestration.baseline import BlindedSubmission
from packages.core.structured_outputs import JudgeOutput, ResearcherOutput
from packages.providers.base import ModelRequest


def build_research_request(problem: Problem, model_profile: str) -> ModelRequest:
    schema = ResearcherOutput.model_json_schema()
    return ModelRequest(
        model_profile=model_profile,
        task_type="research",
        temperature=0.7,
        max_tokens=6000,
        response_schema=schema,
        metadata={"problem_id": str(problem.id)},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an independent research agent. Solve the problem from first "
                    "principles. Do not assume access to other agents. Return only valid JSON "
                    "matching the supplied schema, with no markdown fences or commentary."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title": problem.title,
                        "problem": problem.prompt,
                        "output_schema": schema,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )


def build_judge_request(
    problem: Problem,
    blinded: list[BlindedSubmission],
    model_profile: str,
) -> ModelRequest:
    schema = JudgeOutput.model_json_schema()
    candidates = [
        {
            "candidate_id": item.candidate_id,
            "summary": item.submission.summary,
            "approach": item.submission.approach,
            "claims": [
                {
                    "statement": claim.statement,
                    "confidence": claim.confidence,
                    "support": claim.support,
                }
                for claim in item.submission.claims
            ],
            "evidence": item.submission.evidence,
            "discoveries": item.submission.discoveries,
            "failed_attempts": item.submission.failed_attempts,
            "open_questions": item.submission.open_questions,
            "final_answer": item.submission.final_answer,
        }
        for item in blinded
    ]
    candidate_ids = [item.candidate_id for item in blinded]
    return ModelRequest(
        model_profile=model_profile,
        task_type="judge",
        temperature=0.1,
        max_tokens=6000,
        response_schema=schema,
        metadata={
            "problem_id": str(problem.id),
            "candidate_ids": candidate_ids,
        },
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an independent blind research judge. You do not know which model "
                    "or agent produced any candidate. Evaluate every candidate separately. "
                    "Prioritize correctness and explicit fatal errors over style or consensus. "
                    "Return only valid JSON matching the supplied schema."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title": problem.title,
                        "problem": problem.prompt,
                        "candidates": candidates,
                        "required_candidate_ids": candidate_ids,
                        "output_schema": schema,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
