from __future__ import annotations

from dataclasses import dataclass, field
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
