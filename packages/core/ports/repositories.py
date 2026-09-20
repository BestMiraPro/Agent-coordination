from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol, Self
from uuid import UUID

from packages.core.domain.models import (
    Agent,
    AgentStatus,
    Evaluation,
    Generation,
    Job,
    JobType,
    ModelCall,
    ModelProfile,
    Problem,
    Run,
    RunEvent,
    RunStatus,
    Submission,
)


class ProblemRepository(Protocol):
    def add(self, problem: Problem) -> Problem: ...
    def get(self, problem_id: UUID) -> Problem | None: ...


class RunRepository(Protocol):
    def add(self, run: Run) -> Run: ...
    def get(self, run_id: UUID) -> Run | None: ...
    def update_status(self, run_id: UUID, status: RunStatus) -> Run: ...


class GenerationRepository(Protocol):
    def add(self, generation: Generation) -> Generation: ...
    def get_for_run(self, run_id: UUID, index: int) -> Generation | None: ...
    def list_for_run(self, run_id: UUID) -> list[Generation]: ...


class AgentRepository(Protocol):
    def add_many(self, agents: Iterable[Agent]) -> list[Agent]: ...
    def get(self, agent_id: UUID) -> Agent | None: ...
    def list_for_generation(self, generation_id: UUID) -> list[Agent]: ...
    def update_status(self, agent_id: UUID, status: AgentStatus) -> Agent: ...


class SubmissionRepository(Protocol):
    def add(self, submission: Submission) -> Submission: ...
    def get(self, submission_id: UUID) -> Submission | None: ...
    def list_for_generation(self, generation_id: UUID) -> list[Submission]: ...


class EvaluationRepository(Protocol):
    def add(self, evaluation: Evaluation) -> Evaluation: ...
    def list_for_submission(self, submission_id: UUID) -> list[Evaluation]: ...
    def list_for_generation(self, generation_id: UUID) -> list[Evaluation]: ...


class ModelProfileRepository(Protocol):
    def add(self, profile: ModelProfile) -> ModelProfile: ...
    def get(self, profile_id: UUID) -> ModelProfile | None: ...
    def find(self, provider: str, model: str) -> ModelProfile | None: ...


class ModelCallRepository(Protocol):
    def add(self, call: ModelCall) -> ModelCall: ...
    def get(self, call_id: UUID) -> ModelCall | None: ...


class RunEventRepository(Protocol):
    def append(self, event: RunEvent) -> RunEvent: ...
    def list_for_run(self, run_id: UUID, after_id: UUID | None = None) -> list[RunEvent]: ...


class JobQueue(Protocol):
    def enqueue(
        self,
        job_type: JobType,
        payload: dict[str, Any],
        idempotency_key: str,
        max_attempts: int = 3,
    ) -> Job: ...


class UnitOfWork(Protocol):
    problems: ProblemRepository
    runs: RunRepository
    generations: GenerationRepository
    agents: AgentRepository
    submissions: SubmissionRepository
    evaluations: EvaluationRepository
    model_profiles: ModelProfileRepository
    model_calls: ModelCallRepository
    events: RunEventRepository

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
