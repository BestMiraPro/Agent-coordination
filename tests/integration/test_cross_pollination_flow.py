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
    Run,
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
async def test_cross_pollination_is_selective_and_never_sent_to_fresh_agents(
    session_factory: sessionmaker[Session],
) -> None:
    problem = Problem(title="Cross pollination", prompt="Combine useful partial routes.")
    run = Run(
        problem_id=problem.id,
        max_generations=2,
        population_size=6,
        survivor_count=3,
        fresh_agent_count=1,
    )
    profile = ModelProfile(provider="fake", model="fake/cross")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="cross-worker")
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

    for _ in range(180):
        if not await run_once(queue, handler):
            break

    with uow_factory() as uow:
        generations = uow.generations.list_for_run(run.id)
        second = generations[1]
        researchers = [
            agent
            for agent in uow.agents.list_for_generation(second.id)
            if agent.role.startswith("researcher:")
        ]
        packets = uow.cross_pollination.list_for_generation(second.id)

    assert len(packets) == 5
    assert len({packet.target_agent_id for packet in packets}) == 5
    fresh_ids = {
        agent.id for agent in researchers if agent.origin == AgentOrigin.FRESH
    }
    assert fresh_ids
    assert all(packet.target_agent_id not in fresh_ids for packet in packets)

    with session_factory() as session:
        calls = session.execute(select(ModelCallRecord)).scalars().all()
    cloned_ids = {
        agent.id for agent in researchers if agent.origin == AgentOrigin.CLONED
    }
    cloned_calls = [
        call
        for call in calls
        if call.task_type == "research" and call.agent_id in cloned_ids
    ]
    assert len(cloned_calls) == 5
