from __future__ import annotations

import json
import os
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import (
    Job,
    JobType,
    ModelCallStatus,
    ModelProfile,
    Problem,
    Run,
    RunEventType,
    RunStatus,
)
from packages.core.orchestration.baseline import BaselineOrchestrator
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.models import Base, ModelCallRecord
from packages.persistence.repositories import SqlAlchemyUnitOfWork
from packages.providers.base import ModelRequest, ModelResponse
from services.worker.worker.handlers.baseline import BaselineJobHandler
from services.worker.worker.runtime import run_once


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
    ),
]


@dataclass
class FaultPlan:
    research_failures: int = 0
    malformed_research: int = 0
    judge_failures: int = 0


class FaultInjectingProvider:
    def __init__(self, plan: FaultPlan) -> None:
        self.plan = plan

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if request.task_type == "research":
            if self.plan.research_failures > 0:
                self.plan.research_failures -= 1
                raise RuntimeError("injected researcher provider failure")
            if self.plan.malformed_research > 0:
                self.plan.malformed_research -= 1
                return self._response(request, "not valid json")
            return self._response(request, _research_json())

        if request.task_type == "judge":
            if self.plan.judge_failures > 0:
                self.plan.judge_failures -= 1
                raise RuntimeError("injected judge provider failure")
            candidate_ids = request.metadata["candidate_ids"]
            return self._response(request, _judge_json(candidate_ids))

        raise AssertionError(f"Unexpected task type: {request.task_type}")

    @staticmethod
    def _response(request: ModelRequest, text: str) -> ModelResponse:
        return ModelResponse(
            text=text,
            provider="fault-injecting",
            model=request.model_profile,
            latency_ms=1,
            input_tokens=10,
            output_tokens=20,
            estimated_cost=0.0,
        )


def _research_json() -> str:
    return json.dumps(
        {
            "summary": "Recovered research candidate",
            "approach": "Independent analysis",
            "claims": [],
            "evidence": [],
            "discoveries": ["recovery path validated"],
            "failed_attempts": [],
            "open_questions": [],
            "final_answer": "synthetic answer",
        }
    )


def _judge_json(candidate_ids: list[str]) -> str:
    return json.dumps(
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
                    "critique": "Synthetic evaluation",
                }
                for candidate_id in candidate_ids
            ]
        }
    )


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _build_system(
    session_factory: sessionmaker[Session],
    provider: FaultInjectingProvider,
) -> tuple[
    UUID,
    DurableJobQueue,
    BaselineJobHandler,
    callable,
]:
    problem = Problem(title="Failure-path test", prompt="Exercise the worker retry path.")
    run = Run(problem_id=problem.id)
    profile = ModelProfile(provider="test", model="test-model")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="failure-test-worker")
    orchestrator = BaselineOrchestrator(uow_factory, queue)
    handler = BaselineJobHandler(
        uow_factory=uow_factory,
        orchestrator=orchestrator,
        provider=provider,
        model_profile_id=profile.id,
        model_profile_name=profile.model,
    )
    queue.enqueue(
        JobType.CREATE_GENERATION,
        {"run_id": str(run.id)},
        idempotency_key=f"run:{run.id}:create-generation",
    )
    return run.id, queue, handler, uow_factory


async def _drain(queue: DurableJobQueue, handler: BaselineJobHandler) -> None:
    for _ in range(128):
        processed = await run_once(
            queue,
            handler,
            failure_retry_delay_seconds=0,
        )
        if not processed:
            return
    raise AssertionError("Queue did not become idle within 128 jobs")


def _run_status(uow_factory, run_id: UUID) -> RunStatus:
    with uow_factory() as uow:
        run = uow.runs.get(run_id)
        assert run is not None
        return run.status


@pytest.mark.asyncio
async def test_researcher_provider_failure_retries_and_recovers(
    session_factory: sessionmaker[Session],
) -> None:
    run_id, queue, handler, uow_factory = _build_system(
        session_factory,
        FaultInjectingProvider(FaultPlan(research_failures=1)),
    )

    await _drain(queue, handler)

    assert _run_status(uow_factory, run_id) == RunStatus.COMPLETED
    with session_factory() as session:
        calls = session.execute(select(ModelCallRecord)).scalars().all()

    assert any(
        call.task_type == "research" and call.status == ModelCallStatus.FAILED.value
        for call in calls
    )


@pytest.mark.asyncio
async def test_malformed_research_output_retries_and_recovers(
    session_factory: sessionmaker[Session],
) -> None:
    run_id, queue, handler, uow_factory = _build_system(
        session_factory,
        FaultInjectingProvider(FaultPlan(malformed_research=1)),
    )

    await _drain(queue, handler)

    assert _run_status(uow_factory, run_id) == RunStatus.COMPLETED
    with session_factory() as session:
        calls = session.execute(select(ModelCallRecord)).scalars().all()

    assert any(
        call.task_type == "research"
        and call.status == ModelCallStatus.FAILED.value
        and "Invalid researcher structured output" in (call.error or "")
        for call in calls
    )


@pytest.mark.asyncio
async def test_malformed_research_output_exhausts_retries_and_fails_run(
    session_factory: sessionmaker[Session],
) -> None:
    run_id, queue, handler, uow_factory = _build_system(
        session_factory,
        FaultInjectingProvider(FaultPlan(malformed_research=99)),
    )

    await _drain(queue, handler)

    assert _run_status(uow_factory, run_id) == RunStatus.FAILED
    with uow_factory() as uow:
        events = uow.events.list_for_run(run_id)

    event_types = [event.event_type for event in events]
    assert RunEventType.AGENT_FAILED.value in event_types
    assert RunEventType.RUN_FAILED.value in event_types


@pytest.mark.asyncio
async def test_judge_provider_failure_retries_and_recovers(
    session_factory: sessionmaker[Session],
) -> None:
    run_id, queue, handler, uow_factory = _build_system(
        session_factory,
        FaultInjectingProvider(FaultPlan(judge_failures=1)),
    )

    await _drain(queue, handler)

    assert _run_status(uow_factory, run_id) == RunStatus.COMPLETED
    with session_factory() as session:
        calls = session.execute(select(ModelCallRecord)).scalars().all()

    assert any(
        call.task_type == "judge" and call.status == ModelCallStatus.FAILED.value
        for call in calls
    )


@pytest.mark.asyncio
async def test_duplicate_agent_jobs_do_not_duplicate_durable_artifacts(
    session_factory: sessionmaker[Session],
) -> None:
    run_id, queue, handler, uow_factory = _build_system(
        session_factory,
        FaultInjectingProvider(FaultPlan()),
    )

    await _drain(queue, handler)

    with uow_factory() as uow:
        generation = uow.generations.get_for_run(run_id, 0)
        assert generation is not None
        agents = uow.agents.list_for_generation(generation.id)
        researcher = next(agent for agent in agents if agent.role.startswith("researcher:"))
        judge = next(agent for agent in agents if agent.role.startswith("judge:"))

    await handler.handle(
        Job(
            job_type=JobType.RUN_RESEARCH_AGENT,
            payload={
                "run_id": str(run_id),
                "generation_id": str(generation.id),
                "agent_id": str(researcher.id),
            },
            idempotency_key="manual-duplicate-research",
            attempt=1,
        )
    )
    await handler.handle(
        Job(
            job_type=JobType.RUN_JUDGE,
            payload={
                "run_id": str(run_id),
                "generation_id": str(generation.id),
                "agent_id": str(judge.id),
            },
            idempotency_key="manual-duplicate-judge",
            attempt=1,
        )
    )

    with uow_factory() as uow:
        submissions = uow.submissions.list_for_generation(generation.id)
        evaluations = uow.evaluations.list_for_generation(generation.id)
        events = uow.events.list_for_run(run_id)

    assert len(submissions) == 4
    assert len(evaluations) == 8
    assert (
        sum(
            event.event_type == RunEventType.EVALUATION_COMPLETED.value
            for event in events
        )
        == 8
    )
