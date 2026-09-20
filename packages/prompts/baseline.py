from __future__ import annotations

import json

from packages.core.domain.models import (
    AgentOrigin,
    MutationType,
    Problem,
    ResearchNiche,
    Submission,
)
from packages.core.orchestration.baseline import BlindedSubmission
from packages.core.structured_outputs import CriticOutput, JudgeOutput, ResearcherOutput
from packages.providers.base import ModelRequest


_MUTATION_INSTRUCTIONS: dict[MutationType, str] = {
    MutationType.STRENGTHEN: (
        "Strengthen the parent idea. Repair weak steps, add missing support, and make "
        "the argument more rigorous without merely paraphrasing it."
    ),
    MutationType.FALSIFY: (
        "Actively try to falsify the parent idea. Search for counterexamples, hidden "
        "assumptions, or contradictions. If it survives, produce a repaired version."
    ),
    MutationType.REDERIVE: (
        "Re-derive the problem independently while using the parent only as a hypothesis "
        "to compare against. Prefer a distinct derivation or formulation."
    ),
    MutationType.GENERALIZE: (
        "Generalize the parent idea where justified, then check whether the generalization "
        "reveals a simpler proof, stronger result, or failure boundary."
    ),
}

_NICHE_INSTRUCTIONS: dict[ResearchNiche, str] = {
    ResearchNiche.CONSTRUCTIVE: (
        "Seek a direct constructive solution with explicit intermediate steps."
    ),
    ResearchNiche.SKEPTICAL: (
        "Challenge assumptions aggressively and look for hidden failure modes before "
        "accepting any conclusion."
    ),
    ResearchNiche.COUNTEREXAMPLE: (
        "Prioritize counterexamples, boundary cases, and attempts to disprove plausible claims."
    ),
    ResearchNiche.COMPUTATIONAL: (
        "Prefer computable formulations, small experiments, enumerations, or algorithmic checks "
        "that can expose structure."
    ),
    ResearchNiche.SPECIAL_CASES: (
        "Solve informative special cases first and use them to constrain or build the general solution."
    ),
    ResearchNiche.GENERALIZATION: (
        "Search for a stronger or more general formulation whose structure clarifies the original problem."
    ),
    ResearchNiche.ALTERNATIVE_FORMULATION: (
        "Reframe the problem using a materially different representation, formalism, or decomposition."
    ),
    ResearchNiche.LEMMA_DECOMPOSITION: (
        "Decompose the problem into minimal lemmas or subclaims and attack the bottleneck first."
    ),
}


def _submission_payload(submission: Submission) -> dict[str, object]:
    return {
        "summary": submission.summary,
        "approach": submission.approach,
        "claims": [
            {
                "statement": claim.statement,
                "confidence": claim.confidence,
                "support": claim.support,
            }
            for claim in submission.claims
        ],
        "evidence": submission.evidence,
        "discoveries": submission.discoveries,
        "failed_attempts": submission.failed_attempts,
        "open_questions": submission.open_questions,
        "final_answer": submission.final_answer,
    }


def build_research_request(
    problem: Problem,
    model_profile: str,
    *,
    niche: ResearchNiche = ResearchNiche.CONSTRUCTIVE,
    origin: AgentOrigin = AgentOrigin.INITIAL,
    parent_submission: Submission | None = None,
    mutation_type: MutationType | None = None,
    memory_context: list[dict[str, object]] | None = None,
    cross_pollination: list[dict[str, object]] | None = None,
) -> ModelRequest:
    schema = ResearcherOutput.model_json_schema()
    metadata: dict[str, object] = {
        "problem_id": str(problem.id),
        "research_niche": niche.value,
        "agent_origin": origin.value,
    }
    task: dict[str, object] = {
        "title": problem.title,
        "problem": problem.prompt,
        "research_niche": niche.value,
        "niche_objective": _NICHE_INSTRUCTIONS[niche],
        "output_schema": schema,
    }
    if memory_context:
        task["research_memory"] = memory_context
    if cross_pollination:
        task["cross_pollination"] = cross_pollination

    if parent_submission is None:
        if origin == AgentOrigin.FRESH:
            system_instruction = (
                "You are a fresh blind research explorer injected to prevent premature "
                "convergence. You have no access to prior tournament candidates. Solve the "
                "problem independently while following your assigned research niche. Return "
                "only valid JSON matching the supplied schema, with no markdown fences."
            )
        else:
            system_instruction = (
                "You are an independent research agent. Solve the problem from first "
                "principles while following your assigned research niche. Do not assume "
                "access to other agents. Return only valid JSON matching the supplied schema, "
                "with no markdown fences or commentary."
            )
    else:
        if mutation_type is None:
            raise ValueError("mutation_type is required for a cloned research agent")
        metadata.update(
            {
                "parent_submission_id": str(parent_submission.id),
                "mutation_type": mutation_type.value,
            }
        )
        task["parent_candidate"] = _submission_payload(parent_submission)
        task["mutation_objective"] = _MUTATION_INSTRUCTIONS[mutation_type]
        system_instruction = (
            "You are a cloned research branch in an evolutionary tournament. You receive "
            "one parent candidate, a mutation objective, and an explicit research niche. "
            "Build a new candidate, not a summary of the parent. Preserve useful discoveries "
            "but independently check every important claim. Return only valid JSON matching "
            "the supplied schema, with no markdown fences or commentary."
        )

    return ModelRequest(
        model_profile=model_profile,
        task_type="research",
        temperature=0.7,
        max_tokens=6000,
        response_schema=schema,
        metadata=metadata,
        messages=[
            {"role": "system", "content": system_instruction},
            {
                "role": "user",
                "content": json.dumps(task, ensure_ascii=False),
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
            **_submission_payload(item.submission),
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
                    "You are an independent blind research judge. You do not know which model, "
                    "niche, lineage, or agent produced any candidate. Evaluate every candidate "
                    "separately. Prioritize correctness and explicit fatal errors over style or "
                    "consensus. Return only valid JSON matching the supplied schema."
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


def build_critic_request(
    problem: Problem,
    submission: Submission,
    model_profile: str,
) -> ModelRequest:
    schema = CriticOutput.model_json_schema()
    return ModelRequest(
        model_profile=model_profile,
        task_type="critic",
        temperature=0.1,
        max_tokens=3500,
        response_schema=schema,
        metadata={
            "problem_id": str(problem.id),
            "submission_id": str(submission.id),
        },
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an adversarial research critic. Your reward is for finding "
                    "a real fatal flaw, counterexample, hidden assumption, or unsupported "
                    "step in the candidate. Do not manufacture objections. If the candidate "
                    "survives, say so. Return only JSON matching the supplied schema."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title": problem.title,
                        "problem": problem.prompt,
                        "candidate": _submission_payload(submission),
                        "output_schema": schema,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
