from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from packages.core.domain.models import AgentStatus, RunStatus


class ProblemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    prompt: str = Field(min_length=1)


class ProblemResponse(BaseModel):
    id: UUID
    title: str
    prompt: str


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: UUID


class RunCreatedResponse(BaseModel):
    id: UUID
    problem_id: UUID
    status: RunStatus


class ClaimResponse(BaseModel):
    statement: str
    confidence: float | None = None
    support: str | None = None


class SubmissionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    summary: str
    approach: str
    claims: list[ClaimResponse]
    evidence: list[str]
    discoveries: list[str]
    failed_attempts: list[str]
    open_questions: list[str]
    final_answer: str | None
    raw_response: str


class EvaluationResponse(BaseModel):
    id: UUID
    submission_id: UUID
    judge_agent_id: UUID
    correctness: float
    rigor: float
    novelty: float
    research_progress: float
    verifiability: float
    fatal_error: bool
    judge_confidence: float
    critique: str


class AgentResponse(BaseModel):
    id: UUID
    role: str
    status: AgentStatus


class GenerationResponse(BaseModel):
    id: UUID
    index: int
    agents: list[AgentResponse]
    submissions: list[SubmissionResponse]
    evaluations: list[EvaluationResponse]


class RunDetailResponse(BaseModel):
    id: UUID
    status: RunStatus
    problem: ProblemResponse
    generations: list[GenerationResponse]


class EventPayload(BaseModel):
    id: UUID
    type: str
    payload: dict[str, Any]
    created_at: str | None
