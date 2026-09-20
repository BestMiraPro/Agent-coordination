from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import (
    CandidateLifecycle,
    JobType,
    ModelProfile,
    Problem,
    Run,
    RunEventType,
)
from packages.core.orchestration.tournament import TournamentOrchestrator
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.models import Base
from packages.persistence.repositories import SqlAlchemyUnitOfWork
from packages.providers.base import ModelRequest, ModelResponse
from packages.providers.fake import PhaseOneFakeProvider
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


class FatalCriticProvider(PhaseOneFakeProvider):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        if request.task_type == "critic":
            return ModelResponse(
                text=json.dumps(
                    {
                        "fatal_error": True,
                        "confidence": 0.99,
                        "critique": "Injected fatal counterexample.",
                        "counterexample": "synthetic counterexample",
                    }
                ),
                provider="fake",
                model=request.model_profile,
            )
        return await super().generate(request)


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


async def _run(
    session_factory: sessionmaker[Session],
    provider: PhaseOneFakeProvider,
) -> tuple[Run, SqlAlchemyUnitOfWork]:
    problem = Problem(title="Critic test", prompt="Attack the leading candidate.")
    run = Run(
        problem_id=problem.id,
        max_generations=1,
        population_size=4,
        survivor_count=2,
        critic_count=1,
    )
    profile = ModelProfile(provider="fake", model="fake/critic")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="critic-worker")
    orchestrator = TournamentOrchestrator(uow_factory, queue)
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
    for _ in range(128):
        if not await run_once(queue, handler):
            break
    return run, uow_factory


@pytest.mark.asyncio
async def test_clean_candidate_survives_adversarial_attack(
    session_factory: sessionmaker[Session],
) -> None:
    run, uow_factory = await _run(session_factory, PhaseOneFakeProvider())

    with uow_factory() as uow:
        generation = uow.generations.list_for_run(run.id)[0]
        states = uow.candidate_states.list_for_generation(generation.id)
        findings = uow.critic_findings.list_for_generation(generation.id)
        events = uow.events.list_for_run(run.id)

    assert len(findings) == 1
    assert findings[0].fatal_error is False
    assert any(state.status == CandidateLifecycle.VERIFICATION for state in states)
    assert RunEventType.CRITIC_COMPLETED.value in {event.event_type for event in events}


@pytest.mark.asyncio
async def test_fatal_critic_refutes_leading_candidate(
    session_factory: sessionmaker[Session],
) -> None:
    run, uow_factory = await _run(session_factory, FatalCriticProvider())

    with uow_factory() as uow:
        generation = uow.generations.list_for_run(run.id)[0]
        states = uow.candidate_states.list_for_generation(generation.id)
        findings = uow.critic_findings.list_for_generation(generation.id)

    assert len(findings) == 1
    assert findings[0].fatal_error is True
    assert any(state.status == CandidateLifecycle.REFUTED for state in states)
