from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import (
    EngineeringRun,
    EngineeringStage,
    EngineeringStatus,
    ModelProfile,
)
from packages.core.engineering.orchestration import EngineeringOrchestrator
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.models import Base, ModelCallRecord
from packages.persistence.repositories import SqlAlchemyUnitOfWork
from packages.providers.base import ModelRequest, ModelResponse
from packages.providers.fake import PhaseOneFakeProvider
from services.worker.worker.handlers.engineering import EngineeringJobHandler
from services.worker.worker.runtime import run_once

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
    ),
]


class BrokenThenRepairProvider(PhaseOneFakeProvider):
    async def generate(self, request: ModelRequest) -> ModelResponse:
        if (
            request.task_type == "engineering_implement"
            and request.metadata.get("engineering_role") == "primary"
        ):
            return ModelResponse(
                text=json.dumps(
                    {
                        "summary": "Broken initial implementation.",
                        "files": [
                            {
                                "path": "src/app.py",
                                "content": "def solve(:\n    return 'broken'\n",
                            }
                        ],
                        "test_commands": ["pytest -q"],
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


async def _execute(
    session_factory: sessionmaker[Session],
    provider: PhaseOneFakeProvider,
) -> tuple[EngineeringRun, callable]:
    run = EngineeringRun(
        title="Engineering factory test",
        objective="Create a minimal tested Python vertical slice.",
        max_repairs=2,
    )
    profile = ModelProfile(provider="fake", model="fake/engineering")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.engineering_runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="engineering-test-worker")
    orchestrator = EngineeringOrchestrator(uow_factory, queue)
    handler = EngineeringJobHandler(
        uow_factory=uow_factory,
        orchestrator=orchestrator,
        provider=provider,
        model_profile_id=profile.id,
        model_profile_name=profile.model,
    )
    orchestrator.start(run.id)

    for _ in range(128):
        if not await run_once(queue, handler):
            break
    else:
        raise AssertionError("Engineering queue did not drain")

    return run, uow_factory


@pytest.mark.asyncio
async def test_engineering_factory_completes_plan_implement_test_review(
    session_factory: sessionmaker[Session],
) -> None:
    run, uow_factory = await _execute(session_factory, PhaseOneFakeProvider())

    with uow_factory() as uow:
        stored = uow.engineering_runs.get(run.id)
        artifacts = uow.engineering_artifacts.list_for_run(run.id)
        checks = uow.engineering_checks.list_for_run(run.id)

    assert stored is not None
    assert stored.status == EngineeringStatus.COMPLETED
    assert stored.repair_count == 0
    assert {artifact.stage for artifact in artifacts} >= {
        EngineeringStage.PLAN,
        EngineeringStage.IMPLEMENTATION,
        EngineeringStage.REVIEW,
    }
    assert sum(
        artifact.stage == EngineeringStage.IMPLEMENTATION
        for artifact in artifacts
    ) == 2
    assert checks and all(check.passed for check in checks)

    with session_factory() as session:
        calls = session.execute(
            select(ModelCallRecord).where(
                ModelCallRecord.engineering_run_id == run.id
            )
        ).scalars().all()
    assert {call.task_type for call in calls} >= {
        "engineering_plan",
        "engineering_implement",
        "engineering_review",
    }


@pytest.mark.asyncio
async def test_engineering_factory_repairs_failed_deterministic_checks(
    session_factory: sessionmaker[Session],
) -> None:
    run, uow_factory = await _execute(
        session_factory,
        BrokenThenRepairProvider(),
    )

    with uow_factory() as uow:
        stored = uow.engineering_runs.get(run.id)
        artifacts = uow.engineering_artifacts.list_for_run(run.id)
        checks = uow.engineering_checks.list_for_run(run.id)

    assert stored is not None
    assert stored.status == EngineeringStatus.COMPLETED
    assert stored.repair_count == 1
    assert any(
        artifact.stage == EngineeringStage.REPAIR
        for artifact in artifacts
    )
    first_cycle = [check for check in checks if check.repair_cycle == 0]
    repaired_cycle = [check for check in checks if check.repair_cycle == 1]
    assert any(not check.passed for check in first_cycle)
    assert repaired_cycle and all(check.passed for check in repaired_cycle)
