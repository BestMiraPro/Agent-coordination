from __future__ import annotations

from collections import Counter
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

Score = Annotated[float, Field(ge=0.0, le=1.0)]


class ResearchClaimOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1)
    confidence: Score | None = None
    support: str | None = None


class ResearcherOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    approach: str = Field(min_length=1)
    claims: list[ResearchClaimOutput] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    discoveries: list[str] = Field(default_factory=list)
    failed_attempts: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    final_answer: str | None = None


class CandidateEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    correctness: Score
    rigor: Score
    novelty: Score
    research_progress: Score
    verifiability: Score
    fatal_error: bool
    judge_confidence: Score
    critique: str = Field(min_length=1)


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluations: list[CandidateEvaluationOutput] = Field(min_length=1)


class CriticOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fatal_error: bool
    confidence: Score
    critique: str = Field(min_length=1)
    counterexample: str | None = None


class StructuredOutputError(ValueError):
    def __init__(self, output_kind: str, detail: str) -> None:
        self.output_kind = output_kind
        self.detail = detail
        super().__init__(f"Invalid {output_kind} structured output: {detail}")


def parse_researcher_output(raw_response: str) -> ResearcherOutput:
    try:
        return ResearcherOutput.model_validate_json(raw_response)
    except ValidationError as exc:
        raise StructuredOutputError("researcher", str(exc)) from exc


def parse_judge_output(
    raw_response: str,
    expected_candidate_ids: set[str],
) -> JudgeOutput:
    try:
        output = JudgeOutput.model_validate_json(raw_response)
    except ValidationError as exc:
        raise StructuredOutputError("judge", str(exc)) from exc

    candidate_ids = [evaluation.candidate_id for evaluation in output.evaluations]
    duplicates = sorted(
        candidate_id
        for candidate_id, count in Counter(candidate_ids).items()
        if count > 1
    )
    if duplicates:
        raise StructuredOutputError(
            "judge",
            f"duplicate candidate ids: {duplicates}",
        )

    actual = set(candidate_ids)
    if actual != expected_candidate_ids:
        missing = sorted(expected_candidate_ids - actual)
        unexpected = sorted(actual - expected_candidate_ids)
        raise StructuredOutputError(
            "judge",
            f"candidate set mismatch; missing={missing}, unexpected={unexpected}",
        )

    return output


def parse_critic_output(raw_response: str) -> CriticOutput:
    try:
        return CriticOutput.model_validate_json(raw_response)
    except ValidationError as exc:
        raise StructuredOutputError("critic", str(exc)) from exc


class EngineeringPlanOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    tasks: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)


class EngineeringFileOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    content: str


class EngineeringImplementationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    files: list[EngineeringFileOutput] = Field(min_length=1)
    test_commands: list[str] = Field(default_factory=list)


class EngineeringReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    issues: list[str] = Field(default_factory=list)
    systemic_risks: list[str] = Field(default_factory=list)
    repair_instructions: list[str] = Field(default_factory=list)


def parse_engineering_plan(raw_response: str) -> EngineeringPlanOutput:
    try:
        return EngineeringPlanOutput.model_validate_json(raw_response)
    except ValidationError as exc:
        raise StructuredOutputError("engineering_plan", str(exc)) from exc


def parse_engineering_implementation(
    raw_response: str,
) -> EngineeringImplementationOutput:
    try:
        return EngineeringImplementationOutput.model_validate_json(raw_response)
    except ValidationError as exc:
        raise StructuredOutputError("engineering_implementation", str(exc)) from exc


def parse_engineering_review(raw_response: str) -> EngineeringReviewOutput:
    try:
        return EngineeringReviewOutput.model_validate_json(raw_response)
    except ValidationError as exc:
        raise StructuredOutputError("engineering_review", str(exc)) from exc
