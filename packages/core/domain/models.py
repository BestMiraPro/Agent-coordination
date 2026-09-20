from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class RunStatus(StrEnum):
    CREATED = "CREATED"
    RESEARCHING = "RESEARCHING"
    JUDGING = "JUDGING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


class AgentStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobType(StrEnum):
    CREATE_GENERATION = "create_generation"
    RUN_RESEARCH_AGENT = "run_research_agent"
    START_JUDGING = "start_judging"
    RUN_JUDGE = "run_judge"
    FINALIZE_RUN = "finalize_run"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRY = "RETRY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ModelCallStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RunEventType(StrEnum):
    RUN_STARTED = "RUN_STARTED"
    GENERATION_CREATED = "GENERATION_CREATED"
    AGENT_SPAWNED = "AGENT_SPAWNED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    JUDGING_STARTED = "JUDGING_STARTED"
    EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"


@dataclass(slots=True)
class Problem:
    title: str
    prompt: str
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Run:
    problem_id: UUID
    status: RunStatus = RunStatus.CREATED
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Generation:
    run_id: UUID
    index: int
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Agent:
    generation_id: UUID
    role: str
    status: AgentStatus = AgentStatus.PENDING
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ClaimDraft:
    statement: str
    confidence: float | None = None
    support: str | None = None


@dataclass(slots=True)
class Submission:
    agent_id: UUID
    summary: str
    approach: str
    claims: list[ClaimDraft] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    discoveries: list[str] = field(default_factory=list)
    failed_attempts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    final_answer: str | None = None
    raw_response: str = ""
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Evaluation:
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
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ModelProfile:
    provider: str
    model: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class ModelCall:
    model_profile_id: UUID
    task_type: str
    status: ModelCallStatus = ModelCallStatus.PENDING
    run_id: UUID | None = None
    agent_id: UUID | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: Decimal | None = None
    retry_count: int = 0
    request_metadata: dict[str, Any] = field(default_factory=dict)
    response_metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Job:
    job_type: JobType
    payload: dict[str, Any]
    idempotency_key: str
    status: JobStatus = JobStatus.PENDING
    attempt: int = 0
    max_attempts: int = 3
    available_at: datetime | None = None
    claimed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    claimed_by: str | None = None
    last_error: str | None = None
    completed_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class RunEvent:
    run_id: UUID
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
