from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.core.domain.models import (
    AgentOrigin,
    AgentStatus,
    CandidateLifecycle,
    CrossPollinationKind,
    KnowledgeKind,
    KnowledgeStatus,
    MutationType,
    ResearchNiche,
    RunStatus,
    SelectionKind,
    VerificationKind,
    VerificationStatus,
)


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
    max_generations: int = Field(default=3, ge=1, le=20)
    population_size: int = Field(default=4, ge=2, le=12)
    survivor_count: int = Field(default=2, ge=1, le=11)
    fresh_agent_count: int = Field(default=1, ge=0, le=11)
    redundancy_threshold: float = Field(default=0.78, ge=0.0, le=1.0)
    critic_count: int = Field(default=1, ge=0, le=4)
    verification_enabled: bool = True

    @model_validator(mode="after")
    def validate_tournament_shape(self) -> "RunCreate":
        if self.survivor_count >= self.population_size:
            raise ValueError("survivor_count must be smaller than population_size")
        if self.fresh_agent_count >= self.population_size:
            raise ValueError("fresh_agent_count must be smaller than population_size")
        return self


class RunCreatedResponse(BaseModel):
    id: UUID
    problem_id: UUID
    status: RunStatus
    max_generations: int
    population_size: int
    survivor_count: int
    fresh_agent_count: int
    redundancy_threshold: float
    critic_count: int
    verification_enabled: bool


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


class SelectionResponse(BaseModel):
    id: UUID
    submission_id: UUID
    selected: bool
    rank: int
    score_vector: dict[str, float | bool]
    reason: str
    selection_kind: SelectionKind
    novelty_score: float
    redundant_with_submission_id: UUID | None


class LineageResponse(BaseModel):
    id: UUID
    child_agent_id: UUID
    parent_submission_id: UUID
    mutation_type: MutationType


class CandidateStateResponse(BaseModel):
    id: UUID
    submission_id: UUID
    status: CandidateLifecycle


class CriticFindingResponse(BaseModel):
    id: UUID
    critic_agent_id: UUID
    submission_id: UUID
    fatal_error: bool
    confidence: float
    critique: str
    counterexample: str | None


class VerificationResponse(BaseModel):
    id: UUID
    submission_id: UUID
    kind: VerificationKind
    status: VerificationStatus
    detail: str
    metadata: dict[str, Any]


class CrossPollinationResponse(BaseModel):
    id: UUID
    target_agent_id: UUID
    source_submission_id: UUID
    kind: CrossPollinationKind
    payload: dict[str, Any]


class KnowledgeResponse(BaseModel):
    id: UUID
    generation_id: UUID
    submission_id: UUID | None
    kind: KnowledgeKind
    content: str
    status: KnowledgeStatus
    confidence: float | None
    provenance: dict[str, Any]


class AgentResponse(BaseModel):
    id: UUID
    role: str
    status: AgentStatus
    niche: ResearchNiche
    origin: AgentOrigin


class GenerationResponse(BaseModel):
    id: UUID
    index: int
    agents: list[AgentResponse]
    submissions: list[SubmissionResponse]
    evaluations: list[EvaluationResponse]
    selections: list[SelectionResponse]
    lineages: list[LineageResponse]
    cross_pollination: list[CrossPollinationResponse]
    knowledge: list[KnowledgeResponse]
    candidate_states: list[CandidateStateResponse]
    critic_findings: list[CriticFindingResponse]
    verifications: list[VerificationResponse]


class RunDetailResponse(BaseModel):
    id: UUID
    status: RunStatus
    max_generations: int
    population_size: int
    survivor_count: int
    fresh_agent_count: int
    redundancy_threshold: float
    critic_count: int
    verification_enabled: bool
    problem: ProblemResponse
    generations: list[GenerationResponse]


class EventPayload(BaseModel):
    id: UUID
    type: str
    payload: dict[str, Any]
    created_at: str | None
