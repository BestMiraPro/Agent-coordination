from __future__ import annotations

import os
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import (
    JobType,
    ModelProfile,
    MutationType,
    Problem,
    Run,
    RunEventType,
    RunStatus,
)
from packages.core.orchestration.tournament import TournamentOrchestrator
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.models import Base, ModelCallRecord
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
async def test_three_generation_tournament_runs_end_to_end(
    session_factory: sessionmaker[Session],
) -> None:
    problem = Problem(
        title="Tournament test",
        prompt="Evolve a synthetic candidate across three generations.",
    )
    run = Run(
        problem_id=problem.id,
        max_generations=3,
        population_size=4,
        survivor_count=2,
    )
    profile = ModelProfile(provider="fake", model="fake/phase-two")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="tournament-test-worker")
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

    for _ in range(128):
        processed = await run_once(queue, handler)
        if not processed:
            break
    else:
        raise AssertionError("Tournament queue did not drain")

    with uow_factory() as uow:
        stored_run = uow.runs.get(run.id)
        generations = uow.generations.list_for_run(run.id)
        events = uow.events.list_for_run(run.id)

        assert stored_run is not None
        assert stored_run.status == RunStatus.COMPLETED
        assert [generation.index for generation in generations] == [0, 1, 2]

        all_submission_ids: dict[int, set[UUID]] = {}
        for generation in generations:
            agents = uow.agents.list_for_generation(generation.id)
            researchers = [a for a in agents if a.role.startswith("researcher:")]
            judges = [a for a in agents if a.role.startswith("judge:")]
            submissions = uow.submissions.list_for_generation(generation.id)
            evaluations = uow.evaluations.list_for_generation(generation.id)

            assert len(researchers) == 4
            assert len(judges) == 2
            assert len(submissions) == 4
            assert len(evaluations) == 8
            all_submission_ids[generation.index] = {item.id for item in submissions}

            if generation.index < 2:
                decisions = uow.selections.list_for_generation(generation.id)
                assert len(decisions) == 4
                assert sum(decision.selected for decision in decisions) == 2
                assert [decision.rank for decision in decisions] == [1, 2, 3, 4]
            else:
                assert uow.selections.list_for_generation(generation.id) == []

            lineages = uow.lineages.list_for_generation(generation.id)
            if generation.index == 0:
                assert lineages == []
            else:
                assert len(lineages) == 4
                assert {
                    lineage.mutation_type for lineage in lineages
                } == {
                    MutationType.STRENGTHEN,
                    MutationType.FALSIFY,
                    MutationType.REDERIVE,
                    MutationType.GENERALIZE,
                }
                assert all(
                    lineage.parent_submission_id
                    in all_submission_ids[generation.index - 1]
                    for lineage in lineages
                )

    event_types = [event.event_type for event in events]
    assert event_types.count(RunEventType.GENERATION_CREATED.value) == 3
    assert event_types.count(RunEventType.SELECTION_COMPLETED.value) == 2
    assert event_types.count(RunEventType.AGENT_CLONED.value) == 8
    assert event_types.count(RunEventType.GENERATION_ADVANCED.value) == 2
    assert event_types.count(RunEventType.RUN_COMPLETED.value) == 1

    with session_factory() as session:
        calls = session.execute(select(ModelCallRecord)).scalars().all()

    mutation_calls = [
        call
        for call in calls
        if call.task_type == "research"
        and call.request_metadata.get("parent_submission_id")
    ]
    assert len(mutation_calls) == 8
    assert {
        call.request_metadata["mutation_type"] for call in mutation_calls
    } == {
        MutationType.STRENGTHEN.value,
        MutationType.FALSIFY.value,
        MutationType.REDERIVE.value,
        MutationType.GENERALIZE.value,
    }


@pytest.mark.asyncio
async def test_replaying_old_finalizer_does_not_create_extra_generation(
    session_factory: sessionmaker[Session],
) -> None:
    problem = Problem(title="Replay test", prompt="Check idempotent finalization.")
    run = Run(
        problem_id=problem.id,
        max_generations=2,
        population_size=4,
        survivor_count=2,
    )
    profile = ModelProfile(provider="fake", model="fake/replay")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="replay-test-worker")
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

    for _ in range(96):
        processed = await run_once(queue, handler)
        if not processed:
            break

    with uow_factory() as uow:
        generations = uow.generations.list_for_run(run.id)
        first_generation = generations[0]
        assert len(generations) == 2

    orchestrator.finalize_run(run.id, first_generation.id)

    with uow_factory() as uow:
        assert len(uow.generations.list_for_run(run.id)) == 2
