from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import (
    AgentOrigin,
    JobType,
    ModelProfile,
    Problem,
    ResearchNiche,
    Run,
    RunEventType,
    RunStatus,
    SelectionKind,
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
async def test_phase3_preserves_diversity_and_injects_fresh_agents(
    session_factory: sessionmaker[Session],
) -> None:
    problem = Problem(
        title="Diversity tournament",
        prompt="Preserve independent solution families while improving quality.",
    )
    run = Run(
        problem_id=problem.id,
        max_generations=3,
        population_size=6,
        survivor_count=3,
        fresh_agent_count=1,
        redundancy_threshold=0.72,
    )
    profile = ModelProfile(provider="fake", model="fake/phase-three")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="diversity-test-worker")
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

    for _ in range(196):
        processed = await run_once(queue, handler)
        if not processed:
            break
    else:
        raise AssertionError("Diversity tournament queue did not drain")

    with uow_factory() as uow:
        stored_run = uow.runs.get(run.id)
        generations = uow.generations.list_for_run(run.id)
        events = uow.events.list_for_run(run.id)

        assert stored_run is not None
        assert stored_run.status == RunStatus.COMPLETED
        assert len(generations) == 3

        for generation in generations:
            agents = uow.agents.list_for_generation(generation.id)
            researchers = [
                agent for agent in agents if agent.role.startswith("researcher:")
            ]
            assert len(researchers) == 6
            assert len({agent.niche for agent in researchers}) == 6
            assert all(isinstance(agent.niche, ResearchNiche) for agent in researchers)

            if generation.index == 0:
                assert all(agent.origin == AgentOrigin.INITIAL for agent in researchers)
                assert uow.lineages.list_for_generation(generation.id) == []
            else:
                assert sum(agent.origin == AgentOrigin.FRESH for agent in researchers) == 1
                assert sum(agent.origin == AgentOrigin.CLONED for agent in researchers) == 5
                assert len(uow.lineages.list_for_generation(generation.id)) == 5

            if generation.index < 2:
                decisions = uow.selections.list_for_generation(generation.id)
                assert len(decisions) == 6
                assert sum(decision.selected for decision in decisions) == 3
                kinds = {
                    decision.selection_kind
                    for decision in decisions
                    if decision.selected
                }
                assert SelectionKind.ELITE in kinds
                assert SelectionKind.NOVELTY in kinds
                assert SelectionKind.WILDCARD in kinds

    event_types = [event.event_type for event in events]
    assert event_types.count(RunEventType.DIVERSITY_ANALYZED.value) == 2
    assert event_types.count(RunEventType.WILDCARD_SELECTED.value) == 2
    assert event_types.count(RunEventType.FRESH_AGENT_INJECTED.value) == 2
    assert event_types.count(RunEventType.AGENT_CLONED.value) == 10

    with session_factory() as session:
        calls = session.execute(select(ModelCallRecord)).scalars().all()

    fresh_calls = [
        call
        for call in calls
        if call.task_type == "research"
        and call.request_metadata.get("agent_origin") == AgentOrigin.FRESH.value
    ]
    assert len(fresh_calls) == 2
    assert all(
        "parent_submission_id" not in call.request_metadata
        for call in fresh_calls
    )
