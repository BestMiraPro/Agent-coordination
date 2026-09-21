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
async def test_later_clones_receive_compact_memory_but_fresh_explorer_stays_blind(
    session_factory: sessionmaker[Session],
) -> None:
    problem = Problem(title="Memory test", prompt="Preserve useful research.")
    run = Run(
        problem_id=problem.id,
        max_generations=2,
        population_size=4,
        survivor_count=2,
        fresh_agent_count=1,
    )
    profile = ModelProfile(provider="fake", model="fake/memory")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="memory-worker")
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
        if not await run_once(queue, handler):
            break

    with uow_factory() as uow:
        generations = uow.generations.list_for_run(run.id)
        assert len(uow.knowledge.list_for_run(run.id)) > 0
        second_agents = [
            agent
            for agent in uow.agents.list_for_generation(generations[1].id)
            if agent.role.startswith("researcher:")
        ]
        fresh_ids = {
            agent.id for agent in second_agents if agent.origin == AgentOrigin.FRESH
        }

    with session_factory() as session:
        calls = session.execute(select(ModelCallRecord)).scalars().all()

    second_research_calls = [
        call
        for call in calls
        if call.task_type == "research"
        and call.agent_id in {agent.id for agent in second_agents}
    ]
    assert second_research_calls
    for call in second_research_calls:
        raw = call.response_metadata.get("raw_text", "")
        assert raw
        if call.agent_id in fresh_ids:
            assert call.request_metadata["agent_origin"] == "FRESH"
            assert "parent_submission_id" not in call.request_metadata
        else:
            assert call.request_metadata["agent_origin"] == "CLONED"
            assert "parent_submission_id" in call.request_metadata
