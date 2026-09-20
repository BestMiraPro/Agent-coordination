from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import JobStatus, JobType
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.models import Base


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


def test_job_queue_is_idempotent_and_retry_safe(
    session_factory: sessionmaker[Session],
) -> None:
    queue = DurableJobQueue(session_factory, worker_id="test-worker")
    first = queue.enqueue(
        JobType.RUN_RESEARCH_AGENT,
        {"agent_id": "a"},
        idempotency_key="research:a",
        max_attempts=2,
    )
    duplicate = queue.enqueue(
        JobType.RUN_RESEARCH_AGENT,
        {"agent_id": "a"},
        idempotency_key="research:a",
        max_attempts=2,
    )
    assert duplicate.id == first.id

    claimed = queue.claim_next()
    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status == JobStatus.RUNNING
    assert claimed.attempt == 1

    retried = queue.fail(claimed.id, "transient", retry_delay=0)
    assert retried.status == JobStatus.RETRY

    claimed_again = queue.claim_next()
    assert claimed_again is not None
    assert claimed_again.id == first.id
    assert claimed_again.attempt == 2

    assert queue.complete(claimed_again.id) is True
    completed = queue.get(claimed_again.id)
    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
