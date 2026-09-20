from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import (
    JobType,
    ModelProfile,
    Problem,
    Run,
    RunEventType,
    RunStatus,
)
from packages.core.orchestration.baseline import BaselineOrchestrator
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.models import Base
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


class SchemaAwareFakeProvider:
    async def generate(self, request: ModelRequest) -> ModelResponse:
        if request.task_type == "research":
            text = json.dumps(
                {
                    "summary": "Independent candidate",
                    "approach": "Analyze the problem directly",
                    "claims": [
                        {
                            "statement": "A testable claim",
                            "confidence": 0.75,
                            "support": "Synthetic test support",
                        }
                    ],
                    "evidence": ["synthetic evidence"],
                    "discoveries": ["synthetic discovery"],
                    "failed_attempts": [],
                    "open_questions": [],
                    "final_answer": "synthetic answer",
                }
            )
        elif request.task_type == "judge":
            candidate_ids = request.metadata["candidate_ids"]
            text = json.dumps(
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
                            "critique": "Synthetic blind evaluation",
                        }
                        for candidate_id in candidate_ids
                    ]
                }
            )
        else:
            raise AssertionError(f"Unexpected task type {request.task_type}")

        return ModelResponse(
            text=text,
            provider="fake",
            model=request.model_profile,
            latency_ms=1,
            input_tokens=10,
            output_tokens=20,
            estimated_cost=0.0,
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


@pytest.mark.asyncio
async def test_baseline_flow_reaches_completed(
    session_factory: sessionmaker[Session],
) -> None:
    problem = Problem(
        title="Synthetic research problem",
        prompt="Find a defensible synthetic answer.",
    )
    run = Run(problem_id=problem.id)
    profile = ModelProfile(provider="fake", model="fake-research")

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    with uow_factory() as uow:
        uow.problems.add(problem)
        uow.runs.add(run)
        uow.model_profiles.add(profile)
        uow.commit()

    queue = DurableJobQueue(session_factory, worker_id="integration-worker")
    orchestrator = BaselineOrchestrator(uow_factory, queue)
    handler = BaselineJobHandler(
        uow_factory=uow_factory,
        orchestrator=orchestrator,
        provider=SchemaAwareFakeProvider(),
        model_profile_id=profile.id,
        model_profile_name=profile.model,
    )

    queue.enqueue(
        JobType.CREATE_GENERATION,
        {"run_id": str(run.id)},
        idempotency_key=f"run:{run.id}:create-generation",
    )

    for _ in range(32):
        processed = await run_once(queue, handler)
        if not processed:
            break

    with uow_factory() as uow:
        stored_run = uow.runs.get(run.id)
        generation = uow.generations.get_for_run(run.id, 0)
        assert generation is not None
        agents = uow.agents.list_for_generation(generation.id)
        submissions = uow.submissions.list_for_generation(generation.id)
        evaluations = uow.evaluations.list_for_generation(generation.id)
        events = uow.events.list_for_run(run.id)

    assert stored_run is not None
    assert stored_run.status == RunStatus.COMPLETED
    assert len([agent for agent in agents if agent.role.startswith("researcher:")]) == 4
    assert len([agent for agent in agents if agent.role.startswith("judge:")]) == 2
    assert len(submissions) == 4
    assert len(evaluations) == 8
    assert all(submission.raw_response for submission in submissions)

    event_types = [event.event_type for event in events]
    assert RunEventType.RUN_STARTED.value in event_types
    assert RunEventType.JUDGING_STARTED.value in event_types
    assert RunEventType.RUN_COMPLETED.value in event_types
    assert event_types.count(RunEventType.EVALUATION_COMPLETED.value) == 8
