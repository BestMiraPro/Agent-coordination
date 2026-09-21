from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import Agent, Generation, Problem, Run, RunStatus
from packages.persistence.models import Base
from packages.persistence.repositories import SqlAlchemyUnitOfWork

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


def test_unit_of_work_persists_phase_one_entities(
    session_factory: sessionmaker[Session],
) -> None:
    problem = Problem(title="Test", prompt="Solve the test problem")
    run = Run(problem_id=problem.id)
    generation = Generation(run_id=run.id, index=0)
    agents = [
        Agent(generation_id=generation.id, role=f"researcher:{index}")
        for index in range(4)
    ]

    with SqlAlchemyUnitOfWork(session_factory) as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.generations.add(generation)
        uow.agents.add_many(agents)
        uow.runs.update_status(run.id, RunStatus.RESEARCHING)
        uow.commit()

    with SqlAlchemyUnitOfWork(session_factory) as uow:
        stored_run = uow.runs.get(run.id)
        stored_agents = uow.agents.list_for_generation(generation.id)

    assert stored_run is not None
    assert stored_run.status == RunStatus.RESEARCHING
    assert len(stored_agents) == 4
