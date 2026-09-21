from __future__ import annotations

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
    VerificationStatus,
)
from packages.core.orchestration.tournament import TournamentOrchestrator
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.models import Base
from packages.persistence.repositories import SqlAlchemyUnitOfWork
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


@pytest.mark.asyncio
async def test_final_candidate_reaches_verified_lifecycle_state(
    session_factory: sessionmaker[Session],
) -> None:
    problem = Problem(title="Verification", prompt="Return a supported candidate.")
    run = Run(
        problem_id=problem.id,
        max_generations=1,
        population_size=4,
        survivor_count=2,
        critic_count=1,
        verification_enabled=True,
    )
    profile = ModelProfile(provider="fake", model="fake/verification")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="verification-worker")
    orchestrator = TournamentOrchestrator(uow_factory, queue)
    handler = BaselineJobHandler(
        uow_factory=uow_factory,
        orchestrator=orchestrator,
        provider=PhaseOneFakeProvider(),
        model_profile_id=profile.id,
        model_profile_name=profile.model,
    )
    queue.enqueue(
        JobType.CREATE_GENERATION,
        {"run_id": str(run.id)},
        idempotency_key=f"run:{run.id}:create-generation",
    )

    for _ in range(160):
        if not await run_once(queue, handler):
            break

    with uow_factory() as uow:
        generation = uow.generations.list_for_run(run.id)[0]
        states = uow.candidate_states.list_for_generation(generation.id)
        results = uow.verifications.list_for_generation(generation.id)

    assert results
    assert all(result.status == VerificationStatus.PASSED for result in results)
    assert any(state.status == CandidateLifecycle.VERIFIED for state in states)
